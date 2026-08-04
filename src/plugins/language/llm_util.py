"""语言插件共享的 LLM 工具：XML 转义、prompt 加载、结构化模型工厂、每日预算。

ask_llm / rerank_reply 共用；本模块只依赖 src.ext.llm，不反向依赖任何业务模块
（nonebot 仅在 notify_budget_exceeded 内 lazy import）。
"""

import os
from collections.abc import Callable, Sequence
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from langchain_core.callbacks import BaseCallbackHandler

from src.ext.llm import DailyCostBudget, get_chat_model
from src.utils.log import logger_wrapper

logger = logger_wrapper(__name__)
_CST = ZoneInfo("Asia/Shanghai")

# 共享 LLM 配置（两模块一致；注意 TIMEOUT 是 asyncio.wait_for 超时，非 request_timeout）
MODEL = "deepseek-v4-flash"
BASE_URL = "https://api.deepseek.com"
TIMEOUT = 5.0
TEMPERATURE = 0.3
# deepseek-v4-flash 默认思考模式不支持 tool_choice，必须关闭
EXTRA_BODY = {"thinking": {"type": "disabled"}}

# 每日 LLM 预算：rerank 与 ask_llm 必须共用同一实例。若各自 new 一个
# DailyCostBudget，两个实例都向同一 Mongo 文档 {_id: 日期} 做 $set，
# 会互相覆盖 consumed_fen（丢账），且每日额度翻倍。
DAILY_BUDGET_YUAN = 3.0
budget = DailyCostBudget(DAILY_BUDGET_YUAN)
_last_notify_date: date | None = None


async def notify_budget_exceeded() -> None:
    """预算超限向通知群发消息，每天仅一次（两模块共享状态，不会重复通知）。"""
    global _last_notify_date
    today = datetime.now(_CST).date()
    if _last_notify_date == today:
        return
    _last_notify_date = today
    group_id = os.getenv("ALERT_GROUP_ID")
    if not group_id:
        return
    try:
        from nonebot import get_bot

        bot = get_bot()
        await bot.send_group_msg(
            group_id=int(group_id),
            message="[鸮鸮] 今日 LLM 预算已用尽，智能回复与「问」已降级为随机回复",
        )
    except Exception as e:
        logger.warning("Failed to notify budget exceeded", exception=e)


_ESCAPE_TABLE = str.maketrans({"<": "&lt;", ">": "&gt;", "&": "&amp;", '"': "&quot;"})


def xml_escape(s: str) -> str:
    """转义 XML 特殊字符，防嵌套 tag 注入。"""
    return s.translate(_ESCAPE_TABLE)


def wrap_tag(name: str, content: str, *, index: int | None = None) -> str:
    """把 content XML 转义后包进 <name>…</name>（可选 index 属性）。"""
    attrs = f' index="{index}"' if index is not None else ""
    return f"<{name}{attrs}>{xml_escape(content)}</{name}>"


def make_prompt_loader(path: Path) -> Callable[[], str | None]:
    """创建 mtime 缓存的 prompt 文件加载器；文件缺失返回 None。"""

    cache: tuple[float, str] | None = None

    def load() -> str | None:
        nonlocal cache
        try:
            mtime = path.stat().st_mtime
        except FileNotFoundError:
            return None
        if cache is not None and cache[0] == mtime:
            return cache[1]
        text = path.read_text(encoding="utf-8")
        cache = (mtime, text)
        return text

    return load


def make_structured_model(output_cls, *, callbacks: Sequence[BaseCallbackHandler] = ()):
    """get_chat_model + with_structured_output(method=function_calling)。

    callbacks 透传给 get_chat_model（如 rerank 的 BudgetCallback）；其余参数
    用共享常量。超时/异常处理由调用方各自负责（wait_for + 降级逻辑不同）。
    """
    model = get_chat_model(
        model=MODEL,
        base_url=BASE_URL,
        temperature=TEMPERATURE,
        callbacks=callbacks,
        extra_body=EXTRA_BODY,
    )
    return model.with_structured_output(output_cls, method="function_calling")
