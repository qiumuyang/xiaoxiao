import time

from nonebot.adapters.onebot.v11 import Event
from nonebot.internal.matcher import Matcher
from nonebot.message import run_postprocessor, run_preprocessor
from nonebot.rule import CommandRule, RegexRule
from nonebot.typing import T_State

from .metrics import MATCHER_DURATION, MatcherOutcome


class MatcherIdentifier:

    @classmethod
    def get_label(cls, inst: Matcher) -> str:
        matcher = type(inst)
        if hasattr(matcher, "__metric_matcher_label__"):
            return getattr(matcher, "__metric_matcher_label__")  # noqa: B009
        if matcher.plugin_name:
            return matcher.plugin_name
        src = matcher._source
        assert src is not None
        return f"raw:{src.module_name}:{src.lineno}"

    @classmethod
    def get_type(cls, inst: Matcher) -> str:
        matcher = type(inst)
        if hasattr(matcher, "__metric_matcher_type__"):
            return getattr(matcher, "__metric_matcher_type__")  # noqa: B009
        return cls._infer_type(matcher)

    @classmethod
    def get_sub_command(cls, inst: Matcher) -> str:
        matcher = type(inst)
        if hasattr(matcher, "__metric_matcher_sub__"):
            return getattr(matcher, "__metric_matcher_sub__")  # noqa: B009
        return cls._extract_sub_command(matcher)

    @classmethod
    def _infer_type(cls, matcher: type[Matcher]) -> str:
        t = matcher.type
        if t == "notice":
            return "notice"
        for checker in matcher.rule.checkers:
            obj = getattr(checker, "call", None)
            if obj is None:
                continue
            if isinstance(obj, CommandRule):
                return "command"
            if isinstance(obj, RegexRule):
                return "regex"
            if hasattr(obj, "startswith") and not isinstance(obj, RegexRule):
                return "reply"
        return "message"

    @classmethod
    def _extract_sub_command(cls, matcher: type[Matcher]) -> str:
        for checker in matcher.rule.checkers:
            obj = getattr(checker, "call", None)
            if isinstance(obj, CommandRule) and obj.cmds:
                cmd = obj.cmds[0]
                if len(cmd) > 1:
                    return "/".join(cmd[1:])
                return ""
        return ""


@run_preprocessor
async def _(matcher: Matcher, event: Event, state: T_State):
    state["_mt_start"] = time.perf_counter()


@run_postprocessor
async def _(
    matcher: Matcher,
    exception: Exception | None,
    event: Event,
    state: T_State,
):
    start = state.get("_mt_start")
    if start is None:
        return

    duration = time.perf_counter() - start
    status = MatcherOutcome.ERROR if exception else MatcherOutcome.SUCCESS

    MATCHER_DURATION.labels(
        matcher=MatcherIdentifier.get_label(matcher),
        matcher_type=MatcherIdentifier.get_type(matcher),
        sub_command=MatcherIdentifier.get_sub_command(matcher),
        status=status.value,
    ).observe(duration)
