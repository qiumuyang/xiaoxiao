from typing import Any

from nonebot.matcher import Matcher
from nonebot.plugin.on import (
    on_command as _on_command,
)
from nonebot.plugin.on import (
    on_message as _on_message,
)
from nonebot.plugin.on import (
    on_notice as _on_notice,
)
from nonebot.plugin.on import (
    on_regex as _on_regex,
)


def _auto_label(arg: str | tuple[str, ...]) -> str | None:
    if isinstance(arg, str):
        return arg
    if isinstance(arg, tuple) and arg:
        return arg[0]
    return None


def with_metric(
    matcher: type[Matcher],
    *,
    label: str | None = None,
    type_: str | None = None,
    sub: str = "",
) -> type[Matcher]:
    if label is not None:
        setattr(matcher, "__metric_matcher_label__", label)  # noqa: B010
    if type_ is not None:
        setattr(matcher, "__metric_matcher_type__", type_)  # noqa: B010
    if sub:
        setattr(matcher, "__metric_matcher_sub__", sub)  # noqa: B010
    return matcher


def on_command(
    cmd: str | tuple[str, ...],
    *,
    metric_label: str | None = None,
    metric_type: str | None = None,
    metric_sub: str = "",
    **kwargs: Any,
) -> type[Matcher]:
    return with_metric(
        _on_command(cmd, **kwargs),
        label=metric_label if metric_label is not None else _auto_label(cmd),
        type_=metric_type,
        sub=metric_sub,
    )


def on_reply(
    startswith: str | tuple[str, ...] = tuple(),
    *,
    metric_label: str | None = None,
    metric_type: str | None = None,
    metric_sub: str = "",
    **kwargs: Any,
) -> type[Matcher]:
    from src.ext.on import on_reply as _on_reply

    return with_metric(
        _on_reply(startswith, **kwargs),
        label=metric_label if metric_label is not None else _auto_label(startswith),
        type_=metric_type if metric_type is not None else "reply",
        sub=metric_sub,
    )


def on_message(
    *,
    metric_label: str | None = None,
    metric_type: str | None = None,
    metric_sub: str = "",
    **kwargs: Any,
) -> type[Matcher]:
    return with_metric(
        _on_message(**kwargs),
        label=metric_label,
        type_=metric_type,
        sub=metric_sub,
    )


def on_notice(
    *,
    metric_label: str | None = None,
    metric_type: str | None = None,
    metric_sub: str = "",
    **kwargs: Any,
) -> type[Matcher]:
    return with_metric(
        _on_notice(**kwargs),
        label=metric_label,
        type_=metric_type,
        sub=metric_sub,
    )


def on_regex(
    pattern: str,
    *,
    metric_label: str | None = None,
    metric_type: str | None = None,
    metric_sub: str = "",
    **kwargs: Any,
) -> type[Matcher]:
    return with_metric(
        _on_regex(pattern, **kwargs),
        label=metric_label,
        type_=metric_type,
        sub=metric_sub,
    )
