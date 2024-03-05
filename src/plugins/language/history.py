from dataclasses import dataclass
from datetime import datetime, timedelta

from nonebot.adapters.onebot.v11 import Message

from src.utils.message.receive import MessageData as ReceiveMessageData
from src.utils.message.receive import ReceivedMessageTracker as RMT
from src.utils.message.send import MessageData as SentMessageData
from src.utils.message.send import SentMessageTracker as SMT


@dataclass
class HistoryMessageData:
    user_id: int
    content: Message


class History:

    MAX_HISTORY_COUNT = 200
    MAX_HISTORY_INTERVAL = timedelta(hours=1)

    @classmethod
    async def find(
        cls,
        *,
        group_id: int,
        self_id: int,
        index: int = 1,
    ) -> HistoryMessageData | None:
        since = datetime.now() - cls.MAX_HISTORY_INTERVAL
        recv = await RMT.find(group_id=group_id, since=since)
        sent = await SMT.find(group_id=group_id, since=since)
        messages = sorted(recv + sent, key=lambda x: x.time)
        # -1 for the current message
        messages = messages[-cls.MAX_HISTORY_COUNT - 1:]
        try:
            selected = messages[-index - 1]
        except IndexError:
            return

        if isinstance(selected, ReceiveMessageData):
            return HistoryMessageData(
                user_id=selected.user_id,
                content=selected.content,
            )
        if isinstance(selected, SentMessageData):
            return HistoryMessageData(
                user_id=self_id,
                content=selected.content,
            )
        assert False, "should not reach here"
