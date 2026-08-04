"""语言插件共享的 LLM 工具：XML 转义、prompt 加载、结构化模型工厂。

ask_llm / rerank_reply 共用；本模块只依赖 src.ext.llm，不反向依赖任何业务模块。
"""

from collections.abc import Callable, Sequence
from pathlib import Path

from langchain_core.callbacks import BaseCallbackHandler

from src.ext.llm import get_chat_model

# 共享 LLM 配置（两模块一致；注意 TIMEOUT 是 asyncio.wait_for 超时，非 request_timeout）
MODEL = "deepseek-v4-flash"
BASE_URL = "https://api.deepseek.com"
TIMEOUT = 5.0
TEMPERATURE = 0.3
# deepseek-v4-flash 默认思考模式不支持 tool_choice，必须关闭
EXTRA_BODY = {"thinking": {"type": "disabled"}}

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
