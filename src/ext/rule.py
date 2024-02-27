from contextlib import AsyncExitStack
from typing import Literal, Union

from nonebot.adapters.onebot.v11 import GroupMessageEvent, MessageEvent
from nonebot.dependencies import Dependent
from nonebot.internal.adapter import Bot, Event
from nonebot.rule import Rule, StartswithRule
from nonebot.typing import T_DependencyCache, T_RuleChecker, T_State
from typing_extensions import override

from .ratelimit import (RateLimiter, RateLimitManager, RateLimitType,
                        TokenBucketRateLimiter)


class PostRule(Rule):
    """适用于 `nonebot.matcher.Matcher` 的后置规则类。

    当事件传递时，在 `nonebot.matcher.Matcher` 运行前，其余 `nonebot.rule.Rule` 通过后进行检查。

    参数:
        final_checker: 最终RuleChecker
        checkers: 常规RuleChecker

    HACK: FIXME:
    由于 `Rule` 的 `__call__` 方法利用 `asyncio.gather` 同时验证所有规则，`on_command` 等辅助函数通过
    构造规则判断是否为对应事件处理器，如果要实现与具体事件处理器相关联的规则类，且包含对特定事件处理器产
    生副作用的内容，则该规则必须在判断关联之后进行验证，因此需要在 `Rule` 的基础上实现后置规则。
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

    @override
    def __and__(  # type: ignore
        self,
        other: Union[Rule, "PostRule", None],
    ) -> "PostRule":
        if other is None:
            return self
        return PostRule(self.post_checker, *self.checkers, *other.checkers)

    @override
    def __rand__(  # type: ignore
        self,
        other: Union[Rule, "PostRule", None],
    ) -> "PostRule":
        if other is None:
            return self
        return PostRule(self.post_checker, *other.checkers, *self.checkers)

    @override
    async def __call__(
        self,
        bot: Bot,
        event: Event,
        state: T_State,
        stack: AsyncExitStack | None = None,
        dependency_cache: T_DependencyCache | None = None,
    ) -> bool:
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

    @classmethod
    def get_message_event_id(
        cls,
        event: MessageEvent,
        type: RateLimitType,
    ) -> str | None:
        match type:
            case RateLimitType.GROUP:
                return f"group_{event.group_id}" if isinstance(
                    event, GroupMessageEvent) else None
            case RateLimitType.USER:
                return f"user_{event.user_id}"
            case RateLimitType.SESSION:
                return event.get_session_id()
            case _:
                raise NotImplementedError

    async def __call__(self, event: MessageEvent) -> bool:
        """此处调用流量控制器，返回是否通过流量控制。

        若不使用后置规则，则任意消息事件都会尝试 `acquire`，
        成为对于全局消息的流量控制。
        """
        id = self.get_message_event_id(event, self.type)
        if id is None:
            return False
        rate_limiter = await RateLimitManager.create_or_get(
            key=self.key + id,
            rate_limit=TokenBucketRateLimiter,
            capacity=self.concurrency,
            refill_rate=self.concurrency / self.seconds)
        if self.block:
            await rate_limiter.acquire()
            return True
        return rate_limiter.try_acquire()


def ratelimit(
    key: str,
    type: RateLimitType | Literal["group", "user", "session"],
    seconds: float,
    concurrency: int = 1,
    block: bool = False,
) -> PostRule:
    return PostRule(
        RateLimitRule(key, RateLimitType(type), seconds, concurrency, block))


class RateLimit:
    """适用于 `nonebot.params.Depends` 的流量控制子依赖。

    `ratelimit` 规则用于事件响应器前的流量控制，将流量检测行为封装在规则内部。
    然而，有时我们需要显式在事件响应器内部进行流量控制，此时可以使用`RateLimit`子依赖，
    通过 `typing.Annotated[RateLimiter, Depends(RateLimit(...))]` 完成依赖注入获取流量控制器。
    """

    def __init__(
        self,
        key: str,
        type: RateLimitType | Literal["group", "user", "session"],
        seconds: float,
        concurrency: int = 1,
    ):
        self.key = key
        self.type = RateLimitType(type)
        self.seconds = seconds
        self.concurrency = concurrency

    async def __call__(self, event: MessageEvent) -> RateLimiter | None:
        id = RateLimitRule.get_message_event_id(event, self.type)
        return await RateLimitManager.create_or_get(
            key=self.key + id,
            rate_limit=TokenBucketRateLimiter,
            capacity=self.concurrency,
            refill_rate=self.concurrency / self.seconds) if id else None


class ReplyRule:

    __slots__ = ("startswith")

    def __init__(self, *startswith: str):
        self.startswith = startswith

    async def __call__(self, event: MessageEvent, state: T_State) -> bool:
        if not event.reply:
            return False
        if self.startswith:
            rule = StartswithRule(self.startswith)
            if not await rule(event, state):
                return False
        state["reply"] = event.reply.model_copy()
        return True


def reply(*startswith: str) -> Rule:
    return Rule(ReplyRule(*startswith))
