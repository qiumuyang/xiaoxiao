#!/usr/bin/env python3
"""清理 GridFS 孤儿 chunk。

孤儿 chunk 的 files_id 在 fs.files 中已不存在。
这是因为 MongoDB TTL 索引删除 fs.files 时不会级联删除 fs.chunks。

Usage:
    python scripts/cleanup_orphan_chunks.py --help
    python scripts/cleanup_orphan_chunks.py --db files --limit 100
    python scripts/cleanup_orphan_chunks.py --db cache --dry-run
    python scripts/cleanup_orphan_chunks.py --db all --limit 0
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import traceback
from pathlib import Path

# allow importing from src/ when run from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from pymongo import AsyncMongoClient
    from pymongo.asynchronous.database import AsyncDatabase
except ImportError as e:
    AsyncMongoClient = None  # type: ignore
    AsyncDatabase = None  # type: ignore
    _import_error = e


BATCH_SIZE = 500


async def get_orphan_stats(db: AsyncDatabase) -> dict:
    """Return diagnostic info without modifying data.

    'chunks_sample' only counts chunks for the first BATCH_SIZE orphans.
    Use the orphan_files count to estimate total impact.
    """
    file_ids = set(await db.fs.files.distinct("_id"))
    chunk_file_ids = await db.fs.chunks.distinct("files_id")
    orphan_ids = [fid for fid in chunk_file_ids if fid not in file_ids]

    sample_chunks = 0
    if orphan_ids:
        pipeline = [
            {"$match": {"files_id": {"$in": orphan_ids[:BATCH_SIZE]}}},
            {"$group": {"_id": "$files_id", "count": {"$sum": 1}}},
        ]
        cursor = await db.fs.chunks.aggregate(pipeline)
        result = await cursor.to_list(None)
        sample_chunks = sum(doc["count"] for doc in result)

    return {
        "files": len(file_ids),
        "chunk_files": len(chunk_file_ids),
        "orphan_files": len(orphan_ids),
        "chunks_sample": sample_chunks,
    }


async def cleanup_db(
    db: AsyncDatabase,
    limit: int,
    dry_run: bool,
) -> dict:
    """Delete orphan chunks from a single database.

    Returns summary dict with deleted chunks / bytes count.
    """
    file_ids = set(await db.fs.files.distinct("_id"))
    chunk_file_ids = await db.fs.chunks.distinct("files_id")
    orphan_ids = [fid for fid in chunk_file_ids if fid not in file_ids]

    if not orphan_ids:
        return {"deleted_files": 0, "deleted_chunks": 0, "orphans_remaining": 0}

    to_process = orphan_ids[:limit] if limit > 0 else orphan_ids

    deleted_files = 0
    deleted_chunks = 0

    for i, file_id in enumerate(to_process):
        chunk_count = await db.fs.chunks.count_documents({"files_id": file_id})

        if dry_run:
            print(
                f"  [{i + 1}/{len(to_process)}] Would delete id={file_id} "
                f"({chunk_count} chunks)"
            )
            deleted_files += 1
            deleted_chunks += chunk_count
        else:
            try:
                result = await db.fs.chunks.delete_many({"files_id": file_id})
                deleted_files += 1
                deleted_chunks += result.deleted_count
                print(
                    f"  [{i + 1}/{len(to_process)}] Deleted id={file_id} "
                    f"({result.deleted_count} chunks)"
                )
            except Exception:
                print(
                    f"  [{i + 1}/{len(to_process)}] FAILED id={file_id}: "
                    f"{traceback.format_exc().strip().splitlines()[-1]}"
                )

    return {
        "deleted_files": deleted_files,
        "deleted_chunks": deleted_chunks,
        "orphans_remaining": len(orphan_ids) - deleted_files,
    }


async def main():
    parser = argparse.ArgumentParser(
        description="清理 GridFS 孤儿 chunk（chunks 的 files_id 在 fs.files 中不存在）",
    )
    parser.add_argument(
        "--db",
        choices=["files", "cache", "all"],
        default="all",
        help="目标数据库 (default: all)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="最多清理几个孤儿文件（不是 chunk 数）(0=不限制, default: 100)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅预览，不实际删除",
    )
    args = parser.parse_args()

    if AsyncMongoClient is None:
        print(f"Missing dependencies: {_import_error}")
        print("Install: pip install pymongo gridfs")
        sys.exit(1)

    dbs = ["files", "cache"] if args.db == "all" else [args.db]
    client = AsyncMongoClient()

    print(f"=== GridFS Orphan Chunk Cleanup ===\n")
    if args.dry_run:
        print("[DRY-RUN MODE — no actual deletion]\n")

    for db_name in dbs:
        database = client[db_name]

        stats = await get_orphan_stats(database)
        print(f"--- Database: {db_name} ---")
        print(f"  fs.files: {stats['files']} documents")
        print(f"  distinct files_id in chunks: {stats['chunk_files']}")
        print(
            f"  orphan files (chunks with no fs.files entry): {stats['orphan_files']}"
        )

        if stats["orphan_files"] == 0:
            print(f"  No orphan chunks, skipping.\n")
            continue

        print(
            f"  Processing up to {'ALL' if args.limit == 0 else args.limit} orphans..."
        )

        result = await cleanup_db(database, args.limit, args.dry_run)

        if args.dry_run:
            print(
                f"  Would delete {result['deleted_files']} files "
                f"({result['deleted_chunks']} chunks)"
            )
        else:
            print(
                f"  Deleted {result['deleted_files']} files "
                f"({result['deleted_chunks']} chunks)"
            )
        print(f"  Orphans remaining: {result['orphans_remaining']}\n")

    await client.close()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
