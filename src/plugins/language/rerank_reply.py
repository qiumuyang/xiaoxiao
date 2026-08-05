"""rerank 智能回复：sample corpus 后 LLM rerank 选一条最贴合上下文的回复。

触发链位置：keyword_respond 检索到候选后，per-group 灰度 + 概率路由进入本模块。
任何 LLM 路径异常一律降级回随机选，不阻塞群聊、不抛到 handler 外。
prompt 模板放本地文件（data/prompts/rerank_reply.txt），不进 git。
"""

from datetime import UTC, datetime
from pathlib import Path

from nonebot import get_bot
from nonebot.adapters.onebot.v11 import Message
from pydantic import BaseModel

from src.ext.llm import PricingRegistry
from src.utils.log import logger_wrapper
from src.utils.persistence.mongo import Collection, Mongo

from .corpus import Corpus
from .keywords import Keyword
from .llm_util import (
    CONTEXT_N,
    DAILY_BUDGET_YUAN,
    MODEL,
    LlmCallResult,
    build_context,
    invoke_structured,
    make_prompt_loader,
    try_consume_budget,
    wrap_context,
    wrap_tag,
    xml_escape,
)
from .llm_util import (
    budget as _budget,
)

logger = logger_wrapper(__name__)

PROMPT_PATH = Path("data/prompts/rerank_reply.txt")
PROMPT_VERSION = "v2"

ESTIMATED_FEN = PricingRegistry.get(MODEL).cost(1500, 100)

K = 10
# rerank 专用宽松召回：低相似度阈值 + 更大样本，由 LLM 精排（随机选仍用 KW_SIM_THRESHOLD）
RERANK_CORPUS_SAMPLES = 256
RERANK_SIM_THRESHOLD = 0.2

_load_prompt = make_prompt_loader(PROMPT_PATH)


class RerankOutput(BaseModel):
    ranks: list[int]


class RerankLog(BaseModel):
    group_id: int
    context: list[str]
    candidates: list[str]
    ranks: list[int]
    selected: str
    raw_response: str | None = None  # LLM 原始结构化输出（JSON），失败时也可能有
    error: str | None = None  # 失败原因/异常细节，成功时为 None
    prompt_version: str
    logged_at: datetime


rerank_logs: Collection[dict, RerankLog] = Mongo.collection(
    "rerank_log"
).auto_serialize(RerankLog)


def _fill_template(template: str, *, self_id: int, context_n: int, k: int) -> str:
    """replace 占位符（不用 str.format，模板含 {ranks:...} 会误解析）。"""
    return (
        template.replace("{self_id}", str(self_id))
        .replace("{CONTEXT_N}", str(context_n))
        .replace("{K}", str(k))
    )


def build_user_prompt(
    context: list[str],
    candidates: list[str],
    *,
    context_n: int,
    k: int,
    group_name: str = "",
) -> str:
    """构造 user 提示：群名（可选）+ 最近群聊（tag 包裹）+ 候选语料（tag 包裹）。"""
    head = f"<group>{xml_escape(group_name)}</group>\n" if group_name else ""
    cand_lines = "\n".join(
        wrap_tag("candidate", c, index=i) for i, c in enumerate(candidates[:k], 1)
    )
    return f"{head}{wrap_context(context, context_n=context_n)}\n<candidates>\n{cand_lines}\n</candidates>"


def build_prompt(
    system_template: str,
    context: list[str],
    candidates: list[str],
    *,
    self_id: int,
    context_n: int,
    k: int,
    group_name: str = "",
) -> tuple[str, str]:
    """构造 system/user 双提示：填充占位符后返回 (system, user)。"""
    system = _fill_template(system_template, self_id=self_id, context_n=context_n, k=k)
    user = build_user_prompt(
        context, candidates, context_n=context_n, k=k, group_name=group_name
    )
    return system, user


def parse_ranks(ranks: list[int], *, k: int) -> int | None:
    """校验 ranks 为 1..k 的排列，返回选中序号（ranks[0]）；非法返回 None。"""
    if len(ranks) != k:
        return None
    if sorted(ranks) != list(range(1, k + 1)):
        return None
    return ranks[0]


async def retrieve_rerank_candidates(
    group_id: int,
    query: str,
    words: list[str],
    *,
    exclude: set[str],
    length: tuple[int, int],
) -> list[str]:
    """宽松召回候选供 LLM 精排：低阈值 + 更大样本，排除近期复读，上限 K。

    随机选路径（keyword_respond）仍用 KW_SIM_THRESHOLD 高阈值检索；本函数是
    rerank 专用，候选更丰富，由 LLM 排序挑选最贴合的一条。
    """
    cursor = await Corpus.find(
        group_id,
        length=length,
        keywords=words,
        sample=RERANK_CORPUS_SAMPLES,
        include_stale=True,
    )
    entries = await cursor.to_list(length=RERANK_CORPUS_SAMPLES)
    corpus = [e["text"] for e in entries]
    corpus_kw = [e["keywords"] for e in entries]
    candidates = Keyword.search(
        [query],
        corpus,
        corpus_kw,
        threshold=RERANK_SIM_THRESHOLD,
        top_k=K,
    )
    return [c for c in candidates if c.strip() not in exclude][:K]


async def _safe_group_name(bot, group_id: int) -> str:
    try:
        info = await bot.get_group_info(group_id=group_id, no_cache=True)
        return info.get("group_name", "")
    except Exception:
        return ""


async def _log_rerank(
    group_id: int,
    context: list[str],
    candidates: list[str],
    *,
    ranks: list[int] | None = None,
    selected: str = "",
    raw: str | None = None,
    error: str | None = None,
) -> None:
    """落 rerank_log；失败路径也落（ranks 空、error 带原因），用于诊断。"""
    try:
        await rerank_logs.insert_one(
            RerankLog(
                group_id=group_id,
                context=context,
                candidates=candidates,
                ranks=ranks or [],
                selected=selected,
                raw_response=raw,
                error=error,
                prompt_version=PROMPT_VERSION,
                logged_at=datetime.now(UTC),
            )
        )
    except Exception as e:
        logger.warning("Failed to write rerank log", exception=e)


class RerankReply:
    @classmethod
    async def rank_and_select(
        cls, group_id: int, candidates: list[str]
    ) -> Message | None:
        """rerank 候选，返回选中 Message；任何异常返回 None（调用方降级随机选）。"""
        if not candidates:
            return None
        system_template = _load_prompt()
        if system_template is None:
            logger.warning(f"Rerank prompt 模板缺失: {PROMPT_PATH}")
            return None
        try:
            context = await build_context(group_id)
        except Exception as e:
            logger.warning("Failed to build rerank context", exception=e)
            await _log_rerank(
                group_id,
                [],
                candidates,
                error=f"build_context: {type(e).__name__}: {e}",
            )
            return None
        if not await try_consume_budget(_budget, ESTIMATED_FEN):
            await _log_rerank(group_id, [], candidates, error="budget exhausted")
            return None
        try:
            k = min(K, len(candidates))
            bot = get_bot()
            group_name = await _safe_group_name(bot, group_id)
            system, user = build_prompt(
                system_template,
                context,
                candidates,
                self_id=int(bot.self_id),
                context_n=CONTEXT_N,
                k=k,
                group_name=group_name,
            )
            result = await cls._invoke_llm(system, user)
        except Exception as e:
            logger.warning("Failed to run rerank", exception=e)
            await _budget.refund(ESTIMATED_FEN)
            await _log_rerank(
                group_id,
                context,
                candidates,
                error=f"run: {type(e).__name__}: {e}",
            )
            return None
        if result.value is None:
            await _log_rerank(
                group_id, context, candidates, raw=result.raw, error=result.error
            )
            return None
        selected_idx = parse_ranks(result.value.ranks, k=k)
        if selected_idx is None:
            await _log_rerank(
                group_id,
                context,
                candidates,
                raw=result.raw,
                error=f"invalid ranks: {result.value.ranks}",
            )
            return None
        selected = candidates[selected_idx - 1]
        await _log_rerank(
            group_id,
            context,
            candidates,
            ranks=result.value.ranks,
            selected=selected,
            raw=result.raw,
        )
        return Message(selected)

    @classmethod
    async def _invoke_llm(cls, system: str, user: str) -> LlmCallResult:
        """统一 LLM 调用骨架；超时/异常/非预期输出 → LlmCallResult(value=None, error=…)。"""
        return await invoke_structured(
            RerankOutput, system, user, budget=_budget, estimated_fen=ESTIMATED_FEN
        )

    @classmethod
    async def budget_status(cls) -> str:
        await _budget.ensure_loaded()
        return f"{_budget.consumed_fen / 100:.2f} 元 / {DAILY_BUDGET_YUAN:.2f} 元"


def parse_log_page(arg: str) -> int:
    """解析日志页码：空/非法/<=0 → 1。"""
    try:
        page = int(arg.strip())
    except ValueError:
        return 1
    return max(page, 1)


async def list_logs(
    group_id: int | None, page: int, page_size: int = 10
) -> list[RerankLog]:
    """按时间倒序分页查 rerank 决策日志。"""
    filter = {"group_id": group_id} if group_id else {}
    return [
        log
        async for log in rerank_logs.find_all(
            filter,
            sort=[("logged_at", -1)],
            skip=(page - 1) * page_size,
            limit=page_size,
        )
    ]
