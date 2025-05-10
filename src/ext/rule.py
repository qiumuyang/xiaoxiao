from contextlib import AsyncExitStack
from typing import Literal, Union

from nonebot.adapters.onebot.v11 import (GroupMessageEvent, MessageEvent,
                                         NoticeEvent)
from nonebot.dependencies import Dependent
from nonebot.internal.adapter import Bot, Event
from nonebot.internal.params import Depends
from nonebot.rule import Rule
from nonebot.typing import T_DependencyCache, T_RuleChecker, T_State
from typing_extensions import override

from .config import T_Config
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
        """Normal rules are `infected` by post rules.

        Once there exists a post rule, all rules on the chain will be infected.
        """
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
        event: Event,
        type: RateLimitType,
    ) -> str | None:
        if not isinstance(event, (MessageEvent, NoticeEvent)):
            raise NotImplementedError
        match type:
            case RateLimitType.GROUP:
                key = "group_id"
                fmt = "group_{value}"
            case RateLimitType.USER:
                key = "user_id"
                fmt = "user_{value}"
            case RateLimitType.SESSION:
                return event.get_session_id()
            case _:
                raise NotImplementedError
        if not hasattr(event, key):
            return None
        return fmt.format(value=getattr(event, key))

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


class _RateLimit:
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

    async def __call__(self, event: Event) -> RateLimiter | None:
        id = RateLimitRule.get_message_event_id(event, self.type)
        return await RateLimitManager.create_or_get(
            key=self.key + id,
            rate_limit=TokenBucketRateLimiter,
            capacity=self.concurrency,
            refill_rate=self.concurrency / self.seconds) if id else None


def RateLimit(
    key: str,
    type: RateLimitType | Literal["group", "user", "session"],
    seconds: float,
    concurrency: int = 1,
) -> RateLimiter:
    return Depends(_RateLimit(key, type, seconds, concurrency),
                   use_cache=False)


class ReplyRule:
    """检查消息是否为回复消息，并满足指定前缀。

    参数:
        *startswith: 任一前缀
        lstrip: 是否去除空白字符后检查
    """

    __slots__ = ("startswith", "lstrip", "force_whitespace")

    def __init__(self,
                 *startswith: str,
                 lstrip: bool = True,
                 force_whitespace: bool = True):
        self.startswith = startswith
        self.lstrip = lstrip
        self.force_whitespace = force_whitespace

    async def __call__(self, event: MessageEvent, state: T_State) -> bool:
        if not event.reply:
            return False
        if self.startswith:
            text = event.get_plaintext()
            if self.lstrip:
                text = text.lstrip()
            if not text.startswith(self.startswith):
                return False
            # if equals to any startswith, return True
            if text not in self.startswith and self.force_whitespace:
                for s in self.startswith:
                    if text.startswith(s) and not text[len(s)].isspace():
                        return False
        state["reply"] = event.reply.model_copy()
        return True


class NotReplyRule:

    def __call__(self, event: MessageEvent) -> bool:
        return not event.reply


def reply(*startswith: str, force_whitespace: bool = True) -> Rule:
    """匹配包含回复的消息，且文本部分满足指定前缀。"""
    return Rule(ReplyRule(*startswith, force_whitespace=force_whitespace))


def not_reply() -> Rule:
    return Rule(NotReplyRule())


class EnabledRule:

    def __init__(self, config: type[T_Config]):
        self.config = config

    async def __call__(self, event: MessageEvent) -> bool:
        user = await self.config.get(user_id=event.user_id)
        if not user.enabled:
            return False
        if isinstance(event, GroupMessageEvent):
            group = await self.config.get(group_id=event.group_id)
            return group.enabled
        return True


def enabled(config: type[T_Config]) -> Rule:
    return Rule(EnabledRule(config))
