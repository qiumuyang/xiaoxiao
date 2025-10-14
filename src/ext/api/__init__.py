import sys
from typing import cast

from typing_extensions import Protocol

from .base import ForwardMessage
from .factory import _get_api


class _APIAlias(Protocol):

    async def set_emoji_reaction(self, group_id: int, message_id: int,
                                 emoji: str) -> None:
        ...

    async def unset_emoji_reaction(self, group_id: int, message_id: int,
                                   emoji: str) -> None:
        ...

    async def send_group_forward_msg(self, group_id: int,
                                     messages: list[ForwardMessage]) -> None:
        ...


def __getattr__(name: str):
    instance = _get_api()
    attr = getattr(instance, name, None)
    if attr is None:
        raise AttributeError(
            f"{name} not found in API implementation {type(instance).__name__}"
        )
    return attr


api: _APIAlias = cast(_APIAlias, sys.modules[__name__])

__all__ = ["api"]
