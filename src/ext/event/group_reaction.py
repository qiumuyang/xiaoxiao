from typing import Literal

from nonebot.adapters.onebot.v11 import NoticeEvent
from nonebot.params import Depends

from .convert import EventConvert


class GroupReactionEvent(NoticeEvent):
    notice_type: Literal["reaction"]  # type: ignore
    operator_id: int
    group_id: int
    message_id: int
    code: str
    count: int
    sub_type: str


class GroupReactionAddEvent(GroupReactionEvent):
    sub_type: Literal["add"]  # type: ignore


class GroupReactionRemoveEvent(GroupReactionEvent):
    sub_type: Literal["remove"]  # type: ignore


def GroupReaction():
    return Depends(EventConvert(GroupReactionEvent))


def GroupReactionAdd():
    return Depends(EventConvert(GroupReactionAddEvent))


def GroupReactionRemove():
    return Depends(EventConvert(GroupReactionRemoveEvent))


# TODO: llonebot compatibility
