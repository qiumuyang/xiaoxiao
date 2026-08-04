"""「问」LLM 介入：三阶段预处理（pass1 预填充 → pass2 LLM → pass3 填回）。

任何 LLM 路径异常一律降级回 ask.py 原纯随机路径，不阻塞用户、不抛到 handler 外。
prompt 模板放本地文件 data/prompts/ask_llm.txt，不进 git。
"""

import asyncio
import random
import re
from pathlib import Path

from pydantic import BaseModel

from src.plugins.language.ask import ReplacementPoint
from src.plugins.language.corpus import Corpus
from src.plugins.language.llm_util import (
    TIMEOUT,
    make_prompt_loader,
    make_structured_model,
    wrap_tag,
    xml_escape,
)
from src.utils.log import logger_wrapper

logger = logger_wrapper(__name__)

PROMPT_PATH = Path("data/prompts/ask_llm.txt")
PROMPT_VERSION = "v1"
K = 10  # 候选数上限（加权采样模式用）

_load_prompt = make_prompt_loader(PROMPT_PATH)

# slot 标记：\x00{index}\x00，_encode_template 生成，_fill_slots/build_replacement_prompt 消费
_SLOT_RE = re.compile(r"\x00(\d+)\x00")

# LLM 输出里的 PUA 字符（昵称/图片符号）不该出现在 replacement 里
_PUA_RE = re.compile(f"[{chr(0xE000)}-{chr(0xF8FF)}]")


def _has_pua(text: str) -> bool:
    return _PUA_RE.search(text) is not None


def build_rendered_string(encoded: str, symtab1: dict[str, dict]) -> str:
    """把 encoded 里的 PUA 字符还原为真实值（昵称包 <nickname> tag）。

    slot 标记 \x00N\x00 保留，交给 build_replacement_prompt 转 <replacement>。
    symtab0 的 PUA（图片）不在 symtab1 里，原样保留，由调用方替换为 [图片]。
    """
    out = []
    for ch in encoded:
        if ch in symtab1:
            entry = symtab1[ch]
            if entry["type"] == "nickname":
                out.append(wrap_tag("nickname", entry["text"]))
            else:
                out.append(xml_escape(entry["text"]))
        else:
            out.append(ch)
    return "".join(out)


def build_replacement_prompt(template: str, points: list[ReplacementPoint]) -> str:
    """把 encoded 里的 slot 标记 \x00N\x00 转自闭合 <replacement index="N" type="T" length="L"/>。

    index 对应结构化输出数组下标；type 取 points 的 kw；length 为该点长度约束（如 什么3 → 3），
    None 时不带 length 属性。
    """

    def _repl(m: re.Match) -> str:
        idx = int(m.group(1))
        if 0 <= idx < len(points):
            p = points[idx]
            attrs = f'index="{idx}" type="{p.kw}"'
            if p.length is not None:
                attrs += f' length="{p.length}"'
            return f"<replacement {attrs}/>"
        return m.group(0)

    return _SLOT_RE.sub(_repl, template)


def _fill_slots(template: str, replacements: list[str]) -> str:
    """按 slot 标记 \x00N\x00 填回 LLM 值。"""

    def _repl(m: re.Match) -> str:
        idx = int(m.group(1))
        return replacements[idx] if 0 <= idx < len(replacements) else m.group(0)

    return _SLOT_RE.sub(_repl, template)


MIN_LEN, MAX_LEN = 2, 10  # 对齐 ask.py MIN_WHAT/MAX_WHAT


class AskLlmOutput(BaseModel):
    replacements: list[str]


def validate_length(text: str, *, length: int | None) -> bool:
    if length is not None:
        return len(text) == length
    return MIN_LEN <= len(text) <= MAX_LEN


async def ask_llm_replace(
    system: str,
    user: str,
    *,
    length: int | None = None,
    kw: str | None = None,
    lengths: list[int | None] | None = None,
) -> list[str] | None:
    """调 LLM 生成 replacement(s)；超时/异常/长度不符 → None（调用方降级）。

    length 与 lengths 二选一：length 对所有 replacement 统一校验；
    lengths 逐点校验（多替换点场景）。kw == "为什么" 时 LLM 可能带前导「因为」，
    但模板已由 _encode_template 提供「因为」前缀，这里先 strip 再校验长度，
    避免 因为因为 重复。
    """
    structured = make_structured_model(AskLlmOutput)
    try:
        result = await asyncio.wait_for(
            structured.ainvoke([("system", system), ("human", user)]),
            timeout=TIMEOUT,
        )
    except asyncio.CancelledError:
        raise  # 不吞取消，保持取消传播
    except TimeoutError:
        logger.warning("Ask llm timed out, fallback")
        return None
    except Exception as e:
        logger.warning("Ask llm error, fallback", exception=e)
        return None
    if not isinstance(result, AskLlmOutput) or not result.replacements:
        return None
    if lengths is not None and len(result.replacements) != len(lengths):
        return None
    results = []
    for i, r in enumerate(result.replacements):
        if kw == "为什么":
            r = r.removeprefix("因为")
        if lengths is not None:
            ok = validate_length(r, length=lengths[i])
        else:
            ok = validate_length(r, length=length)
        if not ok:
            return None
        if _has_pua(r):
            logger.warning("Ask llm output contains PUA chars, fallback")
            return None
        results.append(r)
    return results


class AskRankOutput(BaseModel):
    ranks: list[int]


def weighted_pick(items: list[str], weights: list[float]) -> str:
    """按权重随机选一条；权重全 0 时均匀。"""
    if not items:
        raise ValueError("empty items")
    total = sum(weights)
    if total <= 0:
        return random.choice(items)
    return random.choices(items, weights=weights, k=1)[0]


async def ask_llm_rank(system: str, user: str, *, k: int) -> list[int] | None:
    """LLM 给候选排序；返回 1..k 排列，非法 → None。"""
    structured = make_structured_model(AskRankOutput)
    try:
        result = await asyncio.wait_for(
            structured.ainvoke([("system", system), ("human", user)]),
            timeout=TIMEOUT,
        )
    except asyncio.CancelledError:
        raise  # 不吞取消
    except TimeoutError:
        return None
    except Exception as e:
        logger.warning("Ask rank error, fallback", exception=e)
        return None
    if not isinstance(result, AskRankOutput):
        return None
    ranks = result.ranks
    if len(ranks) != k or sorted(ranks) != list(range(1, k + 1)):
        return None
    return ranks


async def retrieve_candidates(
    group_id: int, *, length: tuple[int, int], sample: int = 16
) -> list[str]:
    """按长度约束拉候选语料（复用 Corpus.find），截断到 K。"""
    sample = min(sample, K)
    cursor = await Corpus.find(group_id=group_id, length=length, sample=sample)
    entries = await cursor.to_list(length=sample)
    return [e["text"] for e in entries]


async def weighted_select(system: str, user: str, candidates: list[str]) -> str | None:
    """LLM 给候选排序，按 rank 生成权重做加权随机选。失败 → None。

    权重 = k - rank（rank1 权重最高 k-1，rank k 权重最低 0），weighted_pick 按权重
    随机选——保留随机性且高分候选更可能被选中。
    """
    k = len(candidates)
    if k == 0:
        return None
    if k == 1:
        return candidates[0]
    ranks = await ask_llm_rank(system, user, k=k)
    if ranks is None:
        return None
    weights = [k - rank for rank in ranks]
    return weighted_pick(candidates, weights)


MAX_LLM_POINTS = 3


def _fill_system(template: str, n_points: int) -> str:
    return template.replace("{__points__}", str(n_points))


class AskLlmPreprocessor:
    """三阶段预处理编排。try_preprocess 返回完整回答或 None（降级走原路径）。"""

    async def try_preprocess(
        self,
        question: str,
        symtab0: dict[str, dict],
        members: list[str],
        *,
        group_id: int,
    ) -> str | None:
        from src.plugins.language.ask import _scan_template

        points = _scan_template(question)
        if not points or len(points) > MAX_LLM_POINTS:
            return None
        system_template = _load_prompt()
        if system_template is None:
            logger.warning("Ask llm prompt 模板缺失")
            return None
        try:
            return await self._run(
                question, symtab0, members, points, system_template, group_id
            )
        except Exception as e:
            logger.warning("Ask llm preprocess failed, fallback", exception=e)
            return None

    async def _run(
        self, question, symtab0, members, points, system_template, group_id
    ) -> str:
        from src.plugins.language.ask import Ask, _encode_template

        encoded = _encode_template(question, points)

        collect: dict[str, tuple[str, str]] = {}
        ask = Ask(None, group_id, None)
        parts = []
        async for token in ask.process(
            encoded,
            members,
            collect_values=collect,
            pua_start=len(symtab0),
        ):
            parts.append(token)
        encoded_filled = "".join(parts)

        rendered = build_rendered_string(encoded_filled, _typed_symtab(collect))
        rendered = _replace_symtab0_images(rendered, symtab0)

        # --- pass2：概率混合 → 纯生成 或 加权采样 ---
        from src.plugins.language.config import RerankReplyConfig

        cfg = await RerankReplyConfig.get(group_id=group_id)
        system = _fill_system(system_template, len(points))
        user = build_replacement_prompt(rendered, points)

        # 加权模式 v1 仅单替换点；多替换点或 generate 模式 → 纯生成。
        # 加权失败直接降级随机（返回 None 触发原随机路径），不再二次 LLM 调用。
        mode = _pick_mode(cfg.ask_llm_generate_prob)
        replacements: list[str] | None = None
        if mode == "weighted" and len(points) == 1:
            p_len = points[0].length
            cand_length = (p_len, p_len) if p_len is not None else (MIN_LEN, MAX_LEN)
            candidates = await retrieve_candidates(
                group_id, length=cand_length, sample=16
            )
            if not candidates:
                return None
            cand_user = (
                user
                + "\n候选语料：\n"
                + "\n".join(
                    wrap_tag("candidate", c, index=i)
                    for i, c in enumerate(candidates, 1)
                )
            )
            selected = await weighted_select(system, cand_user, candidates)
            if selected is not None and points[0].kw == "为什么":
                selected = selected.removeprefix("因为")
            if selected is not None and (p_len is None or len(selected) == p_len):
                replacements = [selected]
            else:
                return None  # 加权失败直接降级随机，不再二次 LLM 调用
        else:
            replacements = await ask_llm_replace(
                system,
                user,
                lengths=[p.length for p in points],
                kw=points[0].kw if len(points) == 1 else None,
            )
        if replacements is None or len(replacements) != len(points):
            return None

        result = _fill_slots(encoded_filled, replacements)
        result = _restore_collected(result, collect)
        result = _replace_symtab0_images(result, symtab0)
        return result


def _typed_symtab(collect: dict[str, tuple[str, str]]) -> dict[str, dict]:
    """collect {PUA: (type, text)} → typed symtab {PUA: {"type", "text"}}。"""
    return {ch: {"type": type_, "text": text} for ch, (type_, text) in collect.items()}


def _replace_symtab0_images(text: str, symtab0: dict[str, dict]) -> str:
    """把 text 里的 symtab0 图片 PUA 字符替换为 [图片] 占位。

    非图片的 symtab0 PUA（at/表情）原样保留，交给 _finalize 的 decode 还原为真实段。
    """
    out = []
    for ch in text:
        if ch in symtab0:
            seg = symtab0[ch]
            if getattr(seg, "type", "") == "image":
                out.append("[图片]")
            else:
                out.append(ch)  # at/表情 保留，_finalize 还原
        else:
            out.append(ch)
    return "".join(out)


def _restore_collected(text: str, collect: dict[str, tuple[str, str]]) -> str:
    """把 text 里的 collect PUA 字符替换为真实值。"""
    out = []
    for ch in text:
        if ch in collect:
            out.append(collect[ch][1])
        else:
            out.append(ch)
    return "".join(out)


def _pick_mode(generate_prob: float) -> str:
    """按生成概率选模式：'generate' 或 'weighted'。"""
    return "generate" if random.random() < generate_prob else "weighted"
