from abc import ABC, abstractmethod
from typing import TypedDict

from nonebot.adapters.onebot.v11 import Bot, Message


class ForwardMessage(TypedDict):
    user_id: int
    nickname: str
    content: Message


class API(ABC):

    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    @abstractmethod
    async def set_emoji_reaction(self, group_id: int, message_id: int,
                                 emoji: str) -> None:
        ...

    @abstractmethod
    async def unset_emoji_reaction(self, group_id: int, message_id: int,
                                   emoji: str) -> None:
        ...

    @abstractmethod
    async def send_group_forward_msg(self, group_id: int,
                                     messages: list[ForwardMessage]) -> None:
        ...
