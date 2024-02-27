from datetime import datetime, timedelta
from typing import TypedDict

from nonebot.adapters.onebot.v11 import Message


class MessageData(TypedDict):
    time: datetime
    recalled: bool
    content: Message


class SentMessageTracker:
    """Tracks bot sent messages for recall and deletion."""

    TTL = timedelta(days=1)

    sent: dict[str, dict[int, MessageData]] = {}

    @classmethod
    def _maintain(cls, key: str) -> None:
        """Maintain the sent message list by removing outdated messages."""
        now = datetime.now()
        if key in cls.sent:
            cls.sent[key] = {
                id: message
                for id, message in cls.sent[key].items()
                if now - message["time"] < cls.TTL
            }

    @classmethod
    def add(cls, key: str, message_id: int, content: Message) -> None:
        """Add a message to the sent message list."""
        cls._maintain(key)
        cls.sent.setdefault(key, {})[message_id] = {
            "time": datetime.now(),
            "recalled": False,
            "content": content.copy(),
        }

    @classmethod
    def remove(cls, key: str, message_id: int | None = None) -> int | None:
        """Remove a message from the sent message list.

        If message_id is None, remove the last message.

        Returns the removed message_id if successful, otherwise None.
        """
        cls._maintain(key)
        recallable = {
            message_id: data
            for message_id, data in cls.sent[key].items()
            if not data["recalled"]
        }
        if not recallable:
            return
        if message_id is None:
            message_id, data = max(recallable.items(),
                                   key=lambda x: x[1]["time"])
        elif message_id not in cls.sent[key]:
            return
        else:
            data = cls.sent[key][message_id]
        if not data["recalled"]:
            data["recalled"] = True
            return message_id

    @classmethod
    def remove_prefix(cls, prefix: str, message_id: int) -> int | None:
        """Remove a message from the sent message list by prefix.

        Returns the removed message_id if successful, otherwise None.
        """
        for key in cls.sent:
            if key.startswith(prefix):
                removed_id = cls.remove(key, message_id)
                if removed_id:
                    return removed_id

    @classmethod
    def contains(
        cls,
        message: str,
        prefix: str = "",
        exact: bool = True,
        recent: timedelta | None = None,
    ) -> bool:
        """Check if the message is in the sent message list.

        If prefix is specified, only check the messages with the prefix.
        """
        fn = lambda x, y: x == y if exact else x in y
        now = datetime.now()
        for key in cls.sent:
            if key.startswith(prefix):
                if any(
                        fn(message, data["content"].extract_plain_text())
                        for data in cls.sent[key].values()
                        if recent is None or now - data["time"] < recent):
                    return True
        return False
