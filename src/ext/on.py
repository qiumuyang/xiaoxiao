from datetime import datetime, timedelta

from nonebot.dependencies import Dependent
from nonebot.matcher import Matcher
from nonebot.permission import Permission
from nonebot.plugin import on
from nonebot.rule import Rule
from nonebot.typing import (T_Handler, T_PermissionChecker, T_RuleChecker,
                            T_State)

from .rule import reply


def on_reply(
    startswith: str | tuple[str, ...] = tuple(),
    rule: Rule | T_RuleChecker | None = None,
    force_whitespace: bool = True,
    permission: Permission | T_PermissionChecker | None = None,
    *,
    handlers: list[T_Handler | Dependent] | None = None,
    temp: bool = False,
    expire_time: datetime | timedelta | None = None,
    priority: int = 1,
    block: bool = True,
    state: T_State | None = None,
) -> type[Matcher]:
    """注册一个回复消息事件响应器。"""
    if isinstance(startswith, str):
        startswith = (startswith, )
    return on("message",
              reply(*startswith, force_whitespace=force_whitespace) & rule,
              permission,
              handlers=handlers,
              temp=temp,
              expire_time=expire_time,
              priority=priority,
              block=block,
              state=state)
