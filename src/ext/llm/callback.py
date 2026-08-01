import time
import uuid

from langchain_core.callbacks import BaseCallbackHandler

from src.utils.observability.metrics import (
    LLM_CALL_DURATION,
    LLM_CALL_ERRORS,
    LLM_COST_FEN,
    LLM_TOKEN_USAGE,
)

from .budget import DailyCostBudget
from .pricing import PricingRegistry


def _infer_provider(model: str) -> str:
    return model.split("-", 1)[0]


def _extract_usage(response) -> dict | None:
    """从 on_llm_end 的 response 提取 token 用量。

    回调链分发的是 LLMResult：generations 嵌套 list[list[ChatGeneration]]，
    usage_metadata 在 generations[0][0].message 上。部分模型/测试路径直接
    传扁平 ChatResult（list[ChatGeneration]），两者都兼容。
    """
    generations = getattr(response, "generations", None)
    if not generations:
        return None
    first = generations[0]
    if isinstance(first, list):
        if not first:
            return None
        message = first[0].message
    else:
        message = first.message
    return getattr(message, "usage_metadata", None)


class PrometheusCallback(BaseCallbackHandler):
    def __init__(self, model: str, provider: str = "") -> None:
        self._model = model
        self._provider = provider or _infer_provider(model)
        self._starts: dict[uuid.UUID, float] = {}

    def on_llm_start(self, serialized, prompts, *, run_id, **kwargs) -> None:
        self._starts[run_id] = time.perf_counter()

    def on_llm_end(self, response, *, run_id, **kwargs) -> None:
        start = self._starts.pop(run_id, None)
        if start is None:
            return

        duration = time.perf_counter() - start
        labels = {"model": self._model, "provider": self._provider}

        LLM_CALL_DURATION.labels(**labels, status="success").observe(duration)

        usage = _extract_usage(response)
        if usage:
            LLM_TOKEN_USAGE.labels(**labels, type="input").inc(
                usage.get("input_tokens", 0)
            )
            LLM_TOKEN_USAGE.labels(**labels, type="output").inc(
                usage.get("output_tokens", 0)
            )

    def on_llm_error(self, error, *, run_id, **kwargs) -> None:
        start = self._starts.pop(run_id, None)
        if start is None:
            return

        duration = time.perf_counter() - start
        labels = {"model": self._model, "provider": self._provider}
        error_type = type(error).__name__

        LLM_CALL_DURATION.labels(**labels, status="error").observe(duration)
        LLM_CALL_ERRORS.labels(**labels, error_type=error_type).inc()


class BudgetCallback(BaseCallbackHandler):
    """LLM 调用成本结算。插件需显式创建并传入 callbacks。

    on_llm_end/on_llm_error 必须是 async def：LangChain 对 async 回调
    总是在事件循环内 await（sync 回调则可能在 executor 线程执行，
    那里没有 running loop，无法直接操作预算）。
    """

    def __init__(
        self,
        budget: DailyCostBudget,
        model: str,
        estimated_fen: int,
    ) -> None:
        # fail fast：模型必须在定价表里有价格，否则 settle 阶段静默失败会泄漏预留
        PricingRegistry.get(model)
        self._budget = budget
        self._model = model
        self._estimated_fen = estimated_fen
        self._settled = False
        self._provider = _infer_provider(model)

    async def on_llm_end(self, response, *, run_id, **kwargs) -> None:
        if self._settled:
            return
        self._settled = True

        usage = _extract_usage(response)
        if usage is None:
            await self._budget.refund(self._estimated_fen)
            return

        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        pricing = PricingRegistry.get(self._model)
        actual_fen = pricing.cost(input_tokens, output_tokens)
        delta = actual_fen - self._estimated_fen

        await self._budget.settle(delta)
        LLM_COST_FEN.labels(model=self._model, provider=self._provider).inc(actual_fen)

    async def on_llm_error(self, error, *, run_id, **kwargs) -> None:
        if self._settled:
            return
        self._settled = True
        await self._budget.refund(self._estimated_fen)
