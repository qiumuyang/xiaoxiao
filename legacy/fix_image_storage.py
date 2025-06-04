import asyncio
from io import BytesIO

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket
from PIL import Image, UnidentifiedImageError


async def validate_and_fix_images(db_name="files"):
    client = AsyncIOMotorClient()
    db = client[db_name]
    fs_bucket = AsyncIOMotorGridFSBucket(db)

    cursor = db.fs.files.find({})
    async for doc in cursor:
        file_id = doc["_id"]
        filename = doc["filename"]
        metadata = doc.get("metadata", {})

        try:
            grid_out = await fs_bucket.open_download_stream(file_id)
            content = await grid_out.read()
            Image.open(BytesIO(content))  # 试图打开图像
        except (UnidentifiedImageError, OSError, Exception) as e:
            print(f"[删除] 无法打开图片 {filename}: {e}")
            await fs_bucket.delete(file_id)
            continue

        if not metadata.get("ready"):
            await db.fs.files.update_one({"_id": file_id},
                                         {"$set": {
                                             "metadata.ready": True
                                         }})
            print(f"[更新] 设置 ready=True: {filename}")

    print("✅ 检查与修复完成。")


if __name__ == "__main__":
    asyncio.run(validate_and_fix_images())
