import asyncio
import re
from datetime import datetime, timedelta, timezone
from typing import NamedTuple

import aiohttp
from motor.core import AgnosticDatabase
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket
from pymongo.errors import DuplicateKeyError

from src.ext import logger_wrapper
from src.utils.env import inject_env


class StorageStat(NamedTuple):
    ephemeral_file_count: int
    ephemeral_file_size: int
    persistent_file_count: int
    persistent_file_size: int


logger = logger_wrapper("storage")

pattern = re.compile(r'(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?')


def _parse_timedelta(tm: str) -> timedelta:
    match = pattern.fullmatch(tm)

    if not match:
        raise ValueError(f"Invalid time string format: {tm}")

    days = int(match.group(1) or 0)
    hours = int(match.group(2) or 0)
    minutes = int(match.group(3) or 0)
    seconds = int(match.group(4) or 0)
    return timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)


@inject_env()
class FileStorage:
    """
    Temporary or long-term storage for files using MongoDB and GridFS.

    Files are downloaded from URLs and stored with specific filenames.
    The initial storage is ephemeral, but can be promoted to persistent.
    - If ephemeral, the file will be deleted after a certain period of time.
    - If persistent, a reference count is kept to prevent deletion.
      Persistent files are not deleted until the reference count is zero.
    """

    FILE_STORAGE_CONCURRENCY: int = 10
    FILE_STORAGE_TTL: str = "7d"

    _instances: dict[str, "FileStorage"] = {}
    _lock = asyncio.Lock()

    def __init__(self, db: AgnosticDatabase):
        self.db = db
        self.fs_bucket = AsyncIOMotorGridFSBucket(self.db)
        self.semaphore = asyncio.Semaphore(self.FILE_STORAGE_CONCURRENCY)
        self.ttl = _parse_timedelta(self.FILE_STORAGE_TTL)

    @classmethod
    async def get_instance(cls, db_name: str = "files"):
        async with cls._lock:
            if db_name in cls._instances:
                return cls._instances[db_name]
            client = AsyncIOMotorClient()
            instance = cls(client[db_name])
            await instance._ensure_index()
            cls._instances[db_name] = instance
            return instance

    async def _ensure_index(self):
        await self.db.fs.files.create_index([("metadata.expire_at", 1)],
                                            expireAfterSeconds=0)
        await self.db.fs.files.create_index([("filename", 1)], unique=True)

    async def _download(self,
                        url: str,
                        filename: str,
                        retries: int = 3) -> bool:
        for attempt in range(retries + 1):
            try:
                async with self.semaphore:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url) as resp:
                            if resp.status != 200:
                                raise ValueError(f"HTTP {resp.status}")
                            await self._store_temp(resp.content, filename)
                return True
            except DuplicateKeyError:
                logger.info(f"File already exists: {filename}")
                return True
            except Exception as e:
                if attempt < retries:
                    await asyncio.sleep(min(2**(attempt + 1), 30))
                    continue
                logger.info(f"Download failed [{filename}] from {url}: {e}")
        return False

    async def _store_temp(self, content: aiohttp.StreamReader, filename: str):
        existing = await self.db.fs.files.find_one({"filename": filename})
        if existing:
            try:
                await self.fs_bucket.delete(existing["_id"])
            except Exception as e:
                logger.warning(
                    f"Failed to delete existing file '{filename}': {e}")

        grid_in = self.fs_bucket.open_upload_stream(
            filename,
            metadata={
                "storage_type": "ephemeral",
                "expire_at": datetime.now(timezone.utc) + self.ttl,
                "created_at": datetime.now(timezone.utc),
                "references": 0,
            },
        )
        async for chunk in content.iter_chunked(1024 * 1024):  # 1MB
            await grid_in.write(chunk)  # type: ignore
        await grid_in.close()  # type: ignore
        return filename

    async def promote(self, filename: str) -> bool:
        result = await self.db.fs.files.update_one(
            {
                "filename": filename,
                "metadata.storage_type": "ephemeral"
            },
            {
                "$set": {
                    "metadata.storage_type": "persistent"
                },
                "$unset": {
                    "metadata.expire_at": 1
                },
                "$inc": {
                    "metadata.references": 1
                }
            },
        )
        return result.modified_count > 0

    async def load(self, url: str, filename: str) -> bytes | None:
        try:
            doc = await self.db.fs.files.find_one({"filename": filename})
            if not doc:
                await self._download(url, filename)
            grid_out = await self.fs_bucket.open_download_stream_by_name(
                filename)
            return await grid_out.read()  # type: ignore
        except Exception as e:
            logger.info(f"Load file failed: {e}")
            return None

    async def load_metadata(self, filename: str) -> dict | None:
        doc = await self.db.fs.files.find_one({"filename": filename})
        return doc["metadata"] if doc else None

    async def add_reference(self, filename: str) -> bool:
        result = await self.db.fs.files.update_one(
            {
                "filename": filename,
                "metadata.storage_type": "persistent"
            }, {"$inc": {
                "metadata.references": 1
            }})
        return result.modified_count > 0

    async def remove_reference(self, filename: str) -> bool:
        doc = await self.db.fs.files.find_one_and_update(
            {
                "filename": filename,
                "metadata.storage_type": "persistent"
            }, {"$inc": {
                "metadata.references": -1
            }},
            return_document=True)
        if not doc:
            return False
        if doc["metadata"]["references"] <= 0:
            await self.fs_bucket.delete(doc["_id"])
            return True
        return False

    async def get_stats(self) -> StorageStat | None:
        """Returns total number of files and cumulative size in bytes."""
        pipeline = [{
            "$group": {
                "_id": "$metadata.storage_type",
                "total_files": {
                    "$sum": 1
                },
                "total_bytes": {
                    "$sum": "$length"
                }
            }
        }]
        result = await self.db.fs.files.aggregate(pipeline).to_list(length=1)
        if result:
            ephemeral, persistent = None, None
            for entry in result:
                if entry["_id"] == "ephemeral":
                    ephemeral = entry
                elif entry["_id"] == "persistent":
                    persistent = entry
            return StorageStat(
                ephemeral["total_files"] if ephemeral else 0,
                ephemeral["total_bytes"] if ephemeral else 0,
                persistent["total_files"] if persistent else 0,
                persistent["total_bytes"] if persistent else 0,
            )
