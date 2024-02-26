from datetime import datetime, timedelta
from typing import TypedDict


class MessageData(TypedDict):
    message_id: int
    time: datetime


class SentMessageTracker:
    """Tracks bot sent messages for recall and deletion."""

    TTL = timedelta(days=1)

    sent: dict[str, list[MessageData]] = {}

    @classmethod
    def _maintain(cls, key: str) -> None:
        """Maintain the sent message list by removing outdated messages."""
        now = datetime.now()
        if key in cls.sent:
            original = len(cls.sent[key])
            cls.sent[key] = [
                msg for msg in cls.sent[key] if now - msg["time"] < cls.TTL
            ]

    @classmethod
    def add(cls, key: str, message_id: int) -> None:
        """Add a message to the sent message list."""
        cls._maintain(key)
        cls.sent.setdefault(key, []).append({
            "message_id": message_id,
            "time": datetime.now()
        })

    @classmethod
    def remove(cls, key: str, message_id: int | None = None) -> int | None:
        """Remove a message from the sent message list.

        If message_id is None, remove the last message.

        Returns the removed message_id if successful, otherwise None.
        """
        cls._maintain(key)
        if not cls.sent.get(key):
            return
        if message_id is None:
            message_id = cls.sent[key][-1]["message_id"]
        elif message_id not in [msg["message_id"] for msg in cls.sent[key]]:
            return

        cls.sent[key] = [
            msg for msg in cls.sent[key] if msg["message_id"] != message_id
        ]
        return message_id
