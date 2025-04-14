from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Awaitable, Callable

import pymongo
from bson import ObjectId
from nonebot.adapters.onebot.v11 import (GroupMessageEvent, Message,
                                         MessageEvent)

from src.ext import MessageSegment as ExtMessageSegment
from src.ext import logger_wrapper

from ..persistence import Collection, Mongo

logger = logger_wrapper(__name__)


@dataclass
class MessageData:
    session_id: str
    message_id: int
    time: datetime
    recalled: bool
    content: Message


Sink = Callable[[ObjectId, MessageData], Awaitable[Any]]


class SentMessageTracker:
    """Tracks bot sent messages for recall and deletion."""

    SESSION_GROUP = "group_{group_id}_{user_id}"
    SESSION_GROUP_PREFIX = "group_{group_id}_"
    SESSION_USER = "{user_id}"

    TTL = timedelta(days=1)

    KEY = "sent_messages"

    sent: Collection[dict, MessageData] = Mongo.collection(KEY)

    sinks: list[Sink] = []

    @classmethod
    def on_send(cls, sink: Sink) -> None:
        logger.info(f"Registering {sink} to receive sent messages")
        cls.sinks.append(sink)

    @classmethod
    async def _maintain(cls, session_id: str) -> None:
        """Maintain the sent message list by removing outdated messages."""
        now = datetime.now()
        expire = now - cls.TTL
        await cls.sent.delete_many({
            "session_id": session_id,
            "time": {
                "$lt": expire
            }
        })

    @classmethod
    async def add(
        cls,
        session_id: str,
        message_id: int,
        content: Message,
    ) -> None:
        """Add a message to the sent message list."""
        await cls._maintain(session_id)
        data = MessageData(
            session_id=session_id,
            message_id=message_id,
            time=datetime.now(),
            recalled=False,
            content=content.copy(),
        )
        result = await cls.sent.insert_one(data)
        for sink in cls.sinks:
            await sink(result.inserted_id, data)

    @classmethod
    async def remove(cls,
                     session_id: str,
                     message_id: int | None = None) -> int | None:
        """Remove a message from the sent message list.

        If message_id is None, remove the last message.

        Returns the removed message_id if successful, otherwise None.
        """
        await cls._maintain(session_id)
        if message_id is None:
            cursor = cls.sent.find({
                "session_id": session_id,
                "recalled": False
            }).sort("time", pymongo.DESCENDING).limit(1)
            if doc := await cursor.to_list(1):
                message_id = doc[0]["message_id"]
                await cls.sent.update_one(
                    filter={
                        "session_id": session_id,
                        "message_id": message_id,
                    },
                    update={"$set": {
                        "recalled": True
                    }},
                )
                return message_id
        else:
            update = await cls.sent.update_one(
                filter={
                    "session_id": session_id,
                    "message_id": message_id,
                },
                update={"$set": {
                    "recalled": True
                }},
            )
            if update.matched_count:
                return message_id

    @classmethod
    async def remove_prefix(cls, prefix: str, message_id: int) -> int | None:
        """Remove a message from the sent message list by prefix.

        Returns the removed message_id if successful, otherwise None.
        """
        update = await cls.sent.update_one(
            filter={
                "session_id": {
                    "$regex": f"^{prefix}"
                },
                "message_id": message_id,
            },
            update={"$set": {
                "recalled": True
            }},
        )
        if update.matched_count:
            return message_id

    @classmethod
    def get_session_id_or_prefix(cls, event: MessageEvent) -> tuple[str, str]:
        if isinstance(event, GroupMessageEvent):
            return (cls.SESSION_GROUP.format(group_id=event.group_id,
                                             user_id=event.user_id),
                    cls.SESSION_GROUP_PREFIX.format(group_id=event.group_id))
        return cls.SESSION_USER.format(user_id=event.user_id), ""

    @classmethod
    def get_prefix(cls, group_id: int) -> str:
        return cls.SESSION_GROUP_PREFIX.format(group_id=group_id)

    @classmethod
    def get_session_id(cls, data: dict[str, Any]) -> str:
        user_id = data.get("user_id")
        group_id = data.get("group_id")
        if group_id is not None:
            return cls.SESSION_GROUP.format(group_id=group_id, user_id=user_id)
        return cls.SESSION_USER.format(user_id=user_id)

    @classmethod
    async def find(
        cls,
        *,
        group_id: int | None = None,
        user_id: int | None = None,
        recalled: bool | None = None,
        since: datetime | None = None,
    ) -> list[MessageData]:
        filter = {}
        if group_id is not None and user_id is not None:
            filter["session_id"] = cls.SESSION_GROUP.format(group_id=group_id,
                                                            user_id=user_id)
        elif group_id is not None:
            filter["session_id"] = {
                "$regex":
                f"^{cls.SESSION_GROUP_PREFIX.format(group_id=group_id)}"
            }
        elif user_id is not None:
            filter["session_id"] = cls.SESSION_USER.format(user_id=user_id)
        if since:
            filter["time"] = {"$gte": since}
        if recalled is not None:
            filter["recalled"] = recalled
        return [data async for data in cls.sent.find_all(filter=filter)]

    @classmethod
    async def count(
        cls,
        *,
        group_id: int | None = None,
        recalled: bool | None = None,
        since: datetime | None = None,
    ) -> int:
        filter = {}
        if group_id is not None:
            filter["session_id"] = {
                "$regex":
                f"^{cls.SESSION_GROUP_PREFIX.format(group_id=group_id)}"
            }
        if since:
            filter["time"] = {"$gte": since}
        if recalled is not None:
            filter["recalled"] = recalled
        return await cls.sent.collection.count_documents(filter)


@SentMessageTracker.sent.serialize()
def serialize(data: MessageData) -> dict:
    segments = ExtMessageSegment.serialize(data.content)
    return {
        "session_id": data.session_id,
        "message_id": data.message_id,
        "time": data.time,
        "recalled": data.recalled,
        "content": segments,
    }


@SentMessageTracker.sent.deserialize(drop_id=True)
def deserialize(data: dict) -> MessageData:
    message = ExtMessageSegment.deserialize(data["content"])
    return MessageData(
        session_id=data["session_id"],
        message_id=data["message_id"],
        time=data["time"],
        recalled=data["recalled"],
        content=message,
    )


@SentMessageTracker.sent.filter()
def _(data: MessageData) -> dict:
    return {
        "session_id": data.session_id,
        "message_id": data.message_id,
    }
