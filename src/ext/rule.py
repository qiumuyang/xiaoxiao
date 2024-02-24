from contextlib import AsyncExitStack
from enum import Enum
from typing import Literal, Union

from nonebot.adapters.onebot.v11 import GroupMessageEvent, MessageEvent
from nonebot.dependencies import Dependent
from nonebot.internal.adapter import Bot, Event
from nonebot.rule import Rule
from nonebot.typing import T_DependencyCache, T_RuleChecker, T_State

from .ratelimit import RateLimit, TokenBucketRateLimit


class RateLimitManager:

    rate_limiters: dict[str, RateLimit] = {}

    @classmethod
    def create_or_get(cls, key: str, rate_limit: type[RateLimit], *args,
                      **kwargs) -> RateLimit:
        if key not in cls.rate_limiters:
            cls.rate_limiters[key] = rate_limit(*args, **kwargs)
        return cls.rate_limiters[key]


class RateLimitType(Enum):
    """Rate limit type.

    GROUP: 每个群内的所有用户使用同一个速率限制。
    USER: 每个用户（无论在何处）使用同一个速率限制。
    SESSION: 每个用户在不同群内使用独立的速率限制。
    """
    GROUP = "group"
    USER = "user"
    SESSION = "session"


class RateLimitRule:

    __slots__ = ("key", "type", "seconds", "concurrency", "block")

    def __init__(
        self,
        key: str,
        type: RateLimitType,
        seconds: float,
        concurrency: int = 1,
        block: bool = False,
    ):
        self.key = key
        self.type = type
        self.seconds = seconds
        self.concurrency = concurrency
        self.block = block

    def __repr__(self) -> str:
        return (f"RateLimit(key={self.key}, type={self.type.value}, "
                f"seconds={self.seconds}, concurrency={self.concurrency}, "
                f"block={self.block})")

    def __eq__(self, other: object) -> bool:
        return (isinstance(other, RateLimitRule) and self.key == other.key
                and self.type == other.type and self.block == other.block)

    def __hash__(self) -> int:
        return hash((self.key, self.type, self.block))

    async def __call__(self, event: MessageEvent) -> bool:
        if self.type == RateLimitType.GROUP:
            if not isinstance(event, GroupMessageEvent):
                return False
            id = str(event.group_id)
        elif self.type == RateLimitType.USER:
            id = str(event.user_id)
        else:
            id = event.get_session_id()
        rate_limiter = RateLimitManager.create_or_get(
            key=self.key + id,
            rate_limit=TokenBucketRateLimit,
            capacity=self.concurrency,
            refill_rate=self.concurrency / self.seconds)
        if self.block:
            await rate_limiter.acquire()
            return True
        ret = rate_limiter.try_acquire()
        return ret


class PostRule(Rule):
    """适用于 `nonebot.matcher.Matcher` 的后置规则类。

    当事件传递时，在 `nonebot.matcher.Matcher` 运行前，其余 `nonebot.rule.Rule` 通过后进行检查。

    参数:
        final_checker: 最终RuleChecker
        checkers: 常规RuleChecker

    HACK: FIXME: 由于 `Rule` 的 `__call__` 方法利用 `asyncio.gather` 同时验证所有规则，
    `on_command` 等辅助函数通过构造规则判断是否为对应指令。流量控制规则对于每个事件响应器是独立的，
    需要在常规规则验证完毕当前事件响应器属于对应流量控制规则后，进行流量检测 `try_acquire` 或 `acquire`；
    否则，任意事件都会提前触发流量检测，导致流量控制异常。
    """

    __slots__ = ("checkers", "post_checker")

    def __init__(
        self,
        post_checker: T_RuleChecker | Dependent[bool],
        *checkers: T_RuleChecker | Dependent[bool],
    ):
        Rule.__init__(self, *checkers)
        self.post_checker: Dependent[bool] = (post_checker if isinstance(
            post_checker, Dependent) else Dependent[bool].parse(
                call=post_checker, allow_types=self.HANDLER_PARAM_TYPES))

    def __and__(self, other: Union[Rule, "PostRule", None]) -> "PostRule":
        if other is None:
            return self
        return PostRule(self.post_checker, *self.checkers, *other.checkers)

    def __rand__(self, other: Union[Rule, "PostRule", None]) -> "PostRule":
        if other is None:
            return self
        return PostRule(self.post_checker, *other.checkers, *self.checkers)

    async def __call__(
            self,
            bot: Bot,
            event: Event,
            state: T_State,
            stack: AsyncExitStack | None = None,
            dependency_cache: T_DependencyCache | None = None) -> bool:
        """先检查常规规则，再短路检查后置规则。"""
        precondition = await Rule.__call__(self, bot, event, state, stack,
                                           dependency_cache)
        return precondition and await self.post_checker(
            bot=bot,
            event=event,
            state=state,
            stack=stack,
            dependency_cache=dependency_cache,
        )


def ratelimit(
    key: str,
    type: RateLimitType | Literal["group", "user", "session"],
    seconds: float,
    concurrency: int = 1,
    block: bool = False,
) -> PostRule:
    return PostRule(
        RateLimitRule(key, RateLimitType(type), seconds, concurrency, block))
