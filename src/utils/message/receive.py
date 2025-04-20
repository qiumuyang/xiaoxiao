from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Awaitable, Callable

from bson import ObjectId
from nonebot.adapters.onebot.v11 import Message

from src.ext.message import MessageSegment as ExtMessageSegment

from ..log import logger_wrapper
from ..persistence import Collection, Mongo

logger = logger_wrapper(__name__)


@dataclass
class MessageData:
    time: datetime
    user_id: int
    group_id: int
    message_id: int
    content: Message
    handled: bool


MessageCollection = Collection[dict, MessageData]
Sink = Callable[[ObjectId | None, MessageData], Awaitable[Any]]


class ReceivedMessageTracker:
    """Tracks bot GROUP received messages."""

    KEY = "received_group_messages"

    received: MessageCollection = Mongo.collection(KEY)

    sinks: list[Sink] = []

    @classmethod
    def on_receive(cls, sink: Sink) -> None:
        """Register a sink to receive messages."""
        logger.info(f"Registering {sink} to receive messages")
        cls.sinks.append(sink)

    @classmethod
    async def add(
        cls,
        user_id: int,
        group_id: int,
        message_id: int,
        content: Message,
        handled: bool,
    ) -> None:
        """Add a message to the received message tracker."""
        data = MessageData(
            time=datetime.now(),
            user_id=user_id,
            group_id=group_id,
            message_id=message_id,
            content=content,
            handled=handled,
        )
        result = await cls.received.insert_if_not_exists(data)
        if not result:
            await cls.received.update_one(
                filter={
                    "group_id": group_id,
                    "message_id": message_id
                },
                update={"$set": {
                    "handled": handled
                }},
            )
        for sink in cls.sinks:
            await sink(result.inserted_id if result else None, data)

    @classmethod
    async def find(
        cls,
        group_id: int | list[int] = [],
        *,
        user_id: int | list[int] = [],
        since: datetime | None = None,
        until: datetime | None = None,
        handled: bool | None = None,
    ) -> list[MessageData]:
        """Find messages by group_id and user_id."""
        filter = {}
        if isinstance(group_id, int):
            filter["group_id"] = group_id
        elif group_id:
            filter["group_id"] = {"$in": group_id}
        if isinstance(user_id, int):
            filter["user_id"] = user_id
        elif user_id:
            filter["user_id"] = {"$in": user_id}
        time_filter = {}
        if since:
            time_filter["$gte"] = since
        if until:
            time_filter["$lte"] = until
        if time_filter:
            filter["time"] = time_filter
        if handled is not None:
            filter["handled"] = handled
        return [data async for data in cls.received.find_all(filter=filter)]

    @classmethod
    async def count(
        cls,
        group_id: int | list[int] = [],
        *,
        user_id: int | list[int] = [],
        since: datetime | None = None,
        handled: bool | None = None,
    ) -> int:
        """Count messages by group_id and user_id."""
        filter = {}
        if isinstance(group_id, int):
            filter["group_id"] = group_id
        elif group_id:
            filter["group_id"] = {"$in": group_id}
        if isinstance(user_id, int):
            filter["user_id"] = user_id
        elif user_id:
            filter["user_id"] = {"$in": user_id}
        if since:
            filter["time"] = {"$gte": since}
        if handled is not None:
            filter["handled"] = handled
        return await cls.received.collection.count_documents(filter)

    @classmethod
    async def list_active_users(
        cls,
        group_id: int,
        recent: timedelta,
    ) -> list[int]:
        """List active users in a group."""
        return await cls.received.collection.distinct(
            "user_id",
            filter={
                "group_id": group_id,
                "time": {
                    "$gte": datetime.now() - recent
                },
            },
        )

    @classmethod
    async def list_distinct_groups(cls) -> list[int]:
        """List distinct groups."""
        return await cls.received.collection.distinct("group_id")


@ReceivedMessageTracker.received.serialize()
def serialize(data: MessageData) -> dict:
    segments = ExtMessageSegment.serialize(data.content)
    return {
        "time": data.time,
        "user_id": data.user_id,
        "group_id": data.group_id,
        "message_id": data.message_id,
        "content": segments,
        "handled": data.handled,
    }


@ReceivedMessageTracker.received.deserialize(drop_id=True)
def _(data: dict) -> MessageData:
    message = ExtMessageSegment.deserialize(data["content"])
    return MessageData(
        time=data["time"],
        user_id=data["user_id"],
        group_id=data["group_id"],
        message_id=data["message_id"],
        content=message,
        handled=data["handled"],
    )


@ReceivedMessageTracker.received.filter()
def _(data: MessageData) -> dict:
    """Use group_id and message_id as the unique identifier."""
    return {
        "group_id": data.group_id,
        "message_id": data.message_id,
    }
