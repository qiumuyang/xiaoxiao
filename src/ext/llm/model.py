# pyright: reportCallIssue=false

import os
from collections.abc import Sequence

from langchain_core.callbacks import BaseCallbackHandler
from langchain_openai import ChatOpenAI

from .callback import PrometheusCallback


def get_chat_model(
    *,
    model: str = "deepseek-chat",
    base_url: str | None = None,
    api_key: str | None = None,
    temperature: float = 0.0,
    max_tokens: int = 4096,
    max_retries: int = 2,
    request_timeout: float = 30.0,
    callbacks: Sequence[BaseCallbackHandler] = (),
    extra_body: dict | None = None,
) -> ChatOpenAI:
    if api_key is None:
        api_key = os.environ.get("XIAO_LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError(
            "LLM API key 未配置：请设置环境变量 XIAO_LLM_API_KEY（或 OPENAI_API_KEY）"
        )

    if base_url is None and not model.startswith(("gpt-", "o1", "o3", "o4")):
        raise ValueError(
            f"模型 {model!r} 非 OpenAI 官方模型，必须显式传入 base_url（如 https://api.deepseek.com）"
        )

    all_callbacks: list[BaseCallbackHandler] = [PrometheusCallback(model=model)]
    all_callbacks.extend(callbacks)

    return ChatOpenAI(
        model_name=model,
        openai_api_base=base_url,
        openai_api_key=api_key,
        temperature=temperature,
        max_tokens=max_tokens,
        max_retries=max_retries,
        request_timeout=request_timeout,
        callbacks=all_callbacks,
        extra_body=extra_body or None,
    )
