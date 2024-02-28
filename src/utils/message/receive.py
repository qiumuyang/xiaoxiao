from dataclasses import dataclass
from datetime import datetime
from typing import Any, Awaitable, Callable

from nonebot.adapters.onebot.v11 import Message

from src.ext import logger_wrapper
from src.ext.message import MessageSegment as ExtMessageSegment

from ..persistence import Collection, Mongo

logger = logger_wrapper(__name__)


@dataclass
class MessageData:
    time: datetime
    group_id: int
    message_id: int
    content: Message
    handled: bool


MessageFilter = Callable[[MessageData], bool]
MessageCollection = Collection[dict, MessageData]
ObjectId = str
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
        group_id: int,
        message_id: int,
        content: Message,
        handled: bool,
    ) -> None:
        """Add a message to the received message tracker."""
        data = MessageData(
            time=datetime.now(),
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


@ReceivedMessageTracker.received.serialize()
def serialize(data: MessageData) -> dict:
    segments = ExtMessageSegment.serialize(data.content)
    return {
        "time": data.time,
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
