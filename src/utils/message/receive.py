import random
from datetime import datetime
from typing import Callable, Iterable, TypedDict

from nonebot.adapters.onebot.v11 import Message


class MessageData(TypedDict):
    time: datetime
    content: Message
    handled: bool


MessageFilter = Callable[[MessageData], bool]


class ReceivedMessageTracker:
    """Tracks bot GROUP received messages."""

    received: dict[int, dict[int, MessageData]] = {}

    @classmethod
    def add(
        cls,
        group_id: int,
        message_id: int,
        content: Message,
        handled: bool,
    ) -> None:
        """Add a message to the received message tracker."""
        cls.received.setdefault(group_id, {})[message_id] = {
            "time": datetime.now(),
            "content": content.copy(),
            "handled": handled,
        }

    @classmethod
    def filter(
        cls,
        group_id: int,
        filter: MessageFilter = lambda x: True,
        shuffle: bool = True,
    ) -> Iterable[MessageData]:
        """Filter the messages in the group."""
        keys = list(cls.received.get(group_id, {}).keys())
        if shuffle:
            random.shuffle(keys)
        for message_id in keys:
            message = cls.received[group_id][message_id]
            try:
                if filter(message):
                    yield message
            except StopIteration:
                return
