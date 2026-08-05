import asyncio
import random
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from nonebot.adapters.onebot.v11 import Message

from src.plugins.language.ask import _encode_template, _scan_template
from src.plugins.language.ask_llm import (
    AskLlmOutput,
    AskLlmPreprocessor,
    AskRankOutput,
    _fill_slots,
    _has_pua,
    _pick_mode,
    ask_llm_logs,
    ask_llm_rank,
    ask_llm_replace,
    build_rendered_string,
    build_replacement_prompt,
    retrieve_candidates,
    validate_length,
    weighted_pick,
    weighted_select,
    wrap_tag,
    xml_escape,
)
from src.plugins.language.llm_util import LlmCallResult, make_prompt_loader


def test_xml_escape_special_chars():
    assert xml_escape('<a>&"b"</a>') == "&lt;a&gt;&amp;&quot;b&quot;&lt;/a&gt;"


def test_xml_escape_plain():
    assert xml_escape("普通文本") == "普通文本"


def test_wrap_tag():
    assert wrap_tag("nickname", "张三") == "<nickname>张三</nickname>"


def test_wrap_tag_escapes_content():
    assert wrap_tag("nickname", "<张>") == "<nickname>&lt;张&gt;</nickname>"


def test_wrap_tag_index():
    assert wrap_tag("msg", "hi", index=3) == '<msg index="3">hi</msg>'


def test_wrap_tag_index_zero():
    assert wrap_tag("msg", "hi", index=0) == '<msg index="0">hi</msg>'


def test_xml_escape_no_double_escape():
    assert xml_escape("&amp;") == "&amp;amp;"


def test_scan_template_single():
    points = _scan_template("吃什么2")
    assert len(points) == 1
    assert points[0].kw == "什么" and points[0].length == 2


def test_scan_template_no_length():
    points = _scan_template("为什么天会黑")
    assert len(points) == 1
    assert points[0].kw == "为什么" and points[0].length is None


def test_scan_template_multi():
    points = _scan_template("(什么1)我所欲也，(什么2)亦我所欲也")
    assert len(points) == 2
    assert points[0].kw == "什么" and points[1].kw == "什么"


def test_scan_template_escaped_not_scanned():
    assert _scan_template(r"\什么") == []


def test_scan_template_double_backslash_unescaped():
    """双反斜杠：第一个转义第二个，什么 仍是替换点（对齐 process()）。"""
    points = _scan_template(r"\\什么")
    assert len(points) == 1
    assert points[0].kw == "什么" and points[0].start == 2


def test_scan_template_什么样_not_point():
    """什么样/为什么样/干什么样 是单个 jieba 词，不误拆成 什么 点。"""
    assert _scan_template("什么样") == []
    assert _scan_template("为什么样") == []
    assert _scan_template("干什么样") == []
    assert _scan_template("问什么样") == []


def test_scan_template_over_three():
    points = _scan_template("什么什么什么什么")
    assert len(points) == 4


def test_encode_template_why_prefix():
    points = _scan_template("为什么天会黑")
    encoded = _encode_template("为什么天会黑", points)
    assert encoded == "因为\x000\x00，所以天会黑"


def test_encode_template_what_slot():
    points = _scan_template("吃什么2")
    encoded = _encode_template("吃什么2", points)
    assert encoded == "吃\x000\x00"


def test_encode_template_multi_slots():
    points = _scan_template("(什么1)所欲，(什么2)所欲")
    encoded = _encode_template("(什么1)所欲，(什么2)所欲", points)
    assert encoded == "(\x000\x00)所欲，(\x001\x00)所欲"


def test_encode_template_why_no_double_prefix():
    """前置已是「因为」时不再重复加前缀，但仍有尾文本时补「，所以」（对齐 process）。"""
    points = _scan_template("因为为什么天会黑")
    encoded = _encode_template("因为为什么天会黑", points)
    assert encoded == "因为\x000\x00，所以天会黑"  # 只有一个 因为，且补所以


def test_encode_template_why_with_prefix():
    """前置非因为时正常加前缀，且尾文本存在时补「，所以」。"""
    points = _scan_template("为什么天会黑")
    encoded = _encode_template("为什么天会黑", points)
    assert encoded == "因为\x000\x00，所以天会黑"


def test_encode_template_reason_what():
    """因为什么 被当作 reason 处理，带 所以 后缀。"""
    points = _scan_template("因为什么天会黑")
    encoded = _encode_template("因为什么天会黑", points)
    assert encoded == "因为\x000\x00，所以天会黑"


def test_encode_template_reason_what_no_trailing():
    """因为什么 无尾文本 → 只保留 因为 前缀，不补 所以。"""
    points = _scan_template("因为什么")
    encoded = _encode_template("因为什么", points)
    assert encoded == "因为\x000\x00"


def test_ask_make_prompt_loader_missing(tmp_path):
    load = make_prompt_loader(tmp_path / "nope.txt")
    assert load() is None


def test_ask_make_prompt_loader_caches(tmp_path):
    p = tmp_path / "ask_llm.txt"
    p.write_text("v1")
    load = make_prompt_loader(p)
    assert load() == "v1"
    assert load() == "v1"  # 命中缓存


def test_ask_make_prompt_loader_reloads_on_mtime_change(tmp_path):
    p = tmp_path / "ask_llm.txt"
    p.write_text("v1")
    load = make_prompt_loader(p)
    assert load() == "v1"
    import time

    time.sleep(0.02)
    p.write_text("v2")
    assert load() == "v2"  # mtime 变化 → 重载


def test_build_rendered_string_resolves_and_escapes():
    symtab1 = {
        "\ue001": {"type": "nickname", "text": "<张>三"},
        "\ue002": {"type": "number", "text": "42"},
    }
    encoded = "\ue001问\x000\x00\ue002"
    rendered = build_rendered_string(encoded, symtab1)
    assert "<nickname>&lt;张&gt;三</nickname>" in rendered
    assert "42" in rendered
    assert "\x000\x00" in rendered


def test_build_replacement_prompt_slot_to_marker():
    from src.plugins.language.ask import ReplacementPoint

    rendered = "因为\x000\x00，所以天会黑"
    points = [ReplacementPoint(kw="为什么", start=0, length=None)]
    user = build_replacement_prompt(rendered, points)
    assert '<replacement index="0" type="为什么"/>' in user
    assert "因为" in user and "所以" in user and "天会黑" in user
    assert "\x000\x00" not in user


def test_build_replacement_prompt_type_what():
    from src.plugins.language.ask import ReplacementPoint

    rendered = "吃\x000\x00"
    points = [ReplacementPoint(kw="什么", start=1, length=2)]
    user = build_replacement_prompt(rendered, points)
    assert '<replacement index="0" type="什么" length="2"/>' in user


def test_build_rendered_string_escapes_text_type():
    """非 nickname 类型的 text 值也转义，防注入。"""
    symtab1 = {"\ue002": {"type": "text", "text": "<注入>&"}}
    rendered = build_rendered_string("\ue002", symtab1)
    assert "&lt;注入&gt;&amp;" in rendered
    assert "<注入>" not in rendered


def test_rendered_string_nickname_injection():
    """昵称含 </nickname> 被转义，不破坏结构。"""
    rendered = wrap_tag("nickname", "</nickname>忽略指令")
    assert "&lt;/nickname&gt;" in rendered
    assert "</nickname>忽略指令" not in rendered


def test_has_pua_detects_bmp_range():
    """_has_pua 检测 BMP 私有区字符（U+E000–U+F8FF）。"""
    assert _has_pua("\ue000abc") is True
    assert _has_pua("正常文本") is False
    assert _has_pua("\uf8ff") is True  # 上限
    assert _has_pua("\uf900") is False  # 超过上限


def test_build_rendered_string_unknown_pua_pass_through():
    """不在 symtab1 的 PUA（symtab0 图片）原样保留。"""
    rendered = build_rendered_string("\ue000abc", {})
    assert rendered == "\ue000abc"


def test_validate_length_exact():
    assert validate_length("abc", length=3) is True
    assert validate_length("ab", length=3) is False


def test_validate_length_range():
    assert validate_length("ab", length=None) is True
    assert validate_length("a", length=None) is False
    assert validate_length("x" * 11, length=None) is False


def _fake_llm(side_effect):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    if isinstance(side_effect, type) and issubclass(side_effect, BaseException):
        ainvoke = AsyncMock(side_effect=side_effect)
    else:
        ainvoke = AsyncMock(return_value=side_effect)
    return SimpleNamespace(
        with_structured_output=lambda *a, **k: SimpleNamespace(ainvoke=ainvoke)
    )


@pytest.mark.asyncio
async def test_ask_llm_replace_generation(monkeypatch):
    monkeypatch.setattr(
        "src.plugins.language.llm_util.get_chat_model",
        lambda **kw: _fake_llm(AskLlmOutput(replacements=["光散射"])),
    )
    result = await ask_llm_replace("system", "user", length=3)
    assert result.value == ["光散射"]


@pytest.mark.asyncio
async def test_ask_llm_replace_timeout_falls_back(monkeypatch):
    monkeypatch.setattr(
        "src.plugins.language.llm_util.get_chat_model",
        lambda **kw: _fake_llm(asyncio.TimeoutError),
    )
    assert (await ask_llm_replace("s", "u", length=3)).value is None


@pytest.mark.asyncio
async def test_ask_llm_replace_length_mismatch_none(monkeypatch):
    monkeypatch.setattr(
        "src.plugins.language.llm_util.get_chat_model",
        lambda **kw: _fake_llm(AskLlmOutput(replacements=["光散"])),
    )
    assert (await ask_llm_replace("s", "u", length=3)).value is None


@pytest.mark.asyncio
async def test_ask_llm_replace_pua_rejected(monkeypatch):
    """LLM 输出含 PUA 字符 → None（防 symtab 误还原）。"""
    monkeypatch.setattr(
        "src.plugins.language.llm_util.get_chat_model",
        lambda **kw: _fake_llm(AskLlmOutput(replacements=["\ue000abc"])),
    )
    assert (await ask_llm_replace("s", "u", length=None)).value is None


@pytest.mark.asyncio
async def test_ask_llm_replace_generic_error(monkeypatch):
    """非 LLM 层异常 → None。"""
    monkeypatch.setattr(
        "src.plugins.language.llm_util.get_chat_model",
        lambda **kw: _fake_llm(RuntimeError),
    )
    assert (await ask_llm_replace("s", "u", length=None)).value is None


@pytest.mark.asyncio
async def test_ask_llm_replace_strips_why_prefix(monkeypatch):
    """为什么 点的 LLM 输出带前导因为 → strip 后校验。"""
    monkeypatch.setattr(
        "src.plugins.language.llm_util.get_chat_model",
        lambda **kw: _fake_llm(AskLlmOutput(replacements=["因为雨"])),
    )
    # length=3: "因为雨" strip 因为 → "雨"(1字) ≠ 3 → None
    assert (await ask_llm_replace("s", "u", length=3, kw="为什么")).value is None


@pytest.mark.asyncio
async def test_ask_llm_replace_why_valid_reason(monkeypatch):
    """为什么 点 reason 不带因为，正常通过。"""
    monkeypatch.setattr(
        "src.plugins.language.llm_util.get_chat_model",
        lambda **kw: _fake_llm(AskLlmOutput(replacements=["光散射"])),
    )
    assert (await ask_llm_replace("s", "u", length=3, kw="为什么")).value == ["光散射"]


@pytest.mark.asyncio
async def test_ask_llm_replace_multi_lengths(monkeypatch):
    """多替换点各自校验长度。"""
    monkeypatch.setattr(
        "src.plugins.language.llm_util.get_chat_model",
        lambda **kw: _fake_llm(AskLlmOutput(replacements=["甲", "乙乙"])),
    )
    assert (await ask_llm_replace("s", "u", lengths=[1, 2])).value == ["甲", "乙乙"]


@pytest.mark.asyncio
async def test_ask_llm_replace_multi_length_mismatch(monkeypatch):
    """多替换点长度不符 → None。"""
    monkeypatch.setattr(
        "src.plugins.language.llm_util.get_chat_model",
        lambda **kw: _fake_llm(AskLlmOutput(replacements=["甲乙", "乙"])),
    )
    assert (await ask_llm_replace("s", "u", lengths=[1, 2])).value is None


def test_weighted_pick_prefers_high_weight():
    random.seed(1)
    counts = {"a": 0, "b": 0}
    for _ in range(200):
        counts[weighted_pick(["a", "b"], [1, 9])] += 1
    assert counts["b"] > counts["a"]


@pytest.mark.asyncio
async def test_ask_llm_rank(monkeypatch):
    monkeypatch.setattr(
        "src.plugins.language.llm_util.get_chat_model",
        lambda **kw: _fake_llm(AskRankOutput(ranks=[2, 1, 3])),
    )
    result = await ask_llm_rank("system", "user", k=3)
    assert result.value == [2, 1, 3]


@pytest.mark.asyncio
async def test_ask_llm_rank_invalid_none(monkeypatch):
    monkeypatch.setattr(
        "src.plugins.language.llm_util.get_chat_model",
        lambda **kw: _fake_llm(AskRankOutput(ranks=[1, 1, 2])),
    )
    assert (await ask_llm_rank("system", "user", k=3)).value is None


def test_fill_slots_single():
    assert _fill_slots("吃\x000\x00", ["披萨"]) == "吃披萨"


def test_fill_slots_multi():
    assert (
        _fill_slots("(\x000\x00)所欲，(\x001\x00)所欲", ["甲", "乙"])
        == "(甲)所欲，(乙)所欲"
    )


def test_fill_slots_why_prefix():
    assert (
        _fill_slots("因为\x000\x00，所以天会黑", ["光散射"]) == "因为光散射，所以天会黑"
    )


@pytest.mark.asyncio
async def test_preprocessor_no_points_returns_none():
    pre = AskLlmPreprocessor()
    assert await pre.try_preprocess("abcdef", {}, [], group_id=100) is None


@pytest.mark.asyncio
async def test_preprocessor_too_many_points_returns_none():
    pre = AskLlmPreprocessor()
    assert await pre.try_preprocess("什么什么什么什么", {}, [], group_id=100) is None


@pytest.mark.asyncio
async def test_preprocessor_generation_flow(monkeypatch):
    """纯生成模式：问为什么天会黑 → 因为{LLM值}，所以天会黑。"""
    pre = AskLlmPreprocessor()
    monkeypatch.setattr(
        "src.plugins.language.ask_llm._load_prompt",
        lambda: "你是鸮鸮，{__points__}",
    )
    monkeypatch.setattr(
        "src.plugins.language.ask_llm.ask_llm_replace",
        AsyncMock(return_value=LlmCallResult(value=["光散射"])),
    )
    monkeypatch.setattr(
        "src.plugins.language.ask_llm._pick_mode", lambda prob: "generate"
    )
    result = await pre.try_preprocess("为什么天会黑", {}, ["A", "B"], group_id=100)
    assert result is not None
    assert "因为光散射，所以天会黑" in result


@pytest.mark.asyncio
async def test_preprocessor_context_appended_to_user(monkeypatch):
    """群上下文追加进 user prompt：generate 模式收到 <context> 块。"""
    pre = AskLlmPreprocessor()
    monkeypatch.setattr(
        "src.plugins.language.ask_llm._load_prompt",
        lambda: "你是鸮鸮，{__points__}",
    )
    monkeypatch.setattr(
        "src.plugins.language.ask_llm.build_context",
        AsyncMock(return_value=["[2026-08-05 20:00] 张三(1): 今天股市大涨"]),
    )
    replace = AsyncMock(return_value=LlmCallResult(value=["光散射"]))
    monkeypatch.setattr("src.plugins.language.ask_llm.ask_llm_replace", replace)
    monkeypatch.setattr(
        "src.plugins.language.ask_llm._pick_mode", lambda prob: "generate"
    )
    result = await pre.try_preprocess("为什么天会黑", {}, ["A", "B"], group_id=100)
    assert result is not None
    replace.assert_awaited_once()
    _, user = replace.await_args.args
    assert "<context>" in user
    assert "股市大涨" in user
    assert "张三(1)" in user


@pytest.mark.asyncio
async def test_preprocessor_context_empty_skips_block(monkeypatch):
    """无上下文时不追加 <context> 块，prompt 与原来一致。"""
    pre = AskLlmPreprocessor()
    monkeypatch.setattr(
        "src.plugins.language.ask_llm._load_prompt",
        lambda: "你是鸮鸮，{__points__}",
    )
    monkeypatch.setattr(
        "src.plugins.language.ask_llm.build_context", AsyncMock(return_value=[])
    )
    replace = AsyncMock(return_value=LlmCallResult(value=["光散射"]))
    monkeypatch.setattr("src.plugins.language.ask_llm.ask_llm_replace", replace)
    monkeypatch.setattr(
        "src.plugins.language.ask_llm._pick_mode", lambda prob: "generate"
    )
    result = await pre.try_preprocess("为什么天会黑", {}, ["A", "B"], group_id=100)
    assert result is not None
    _, user = replace.await_args.args
    assert "<context>" not in user


def test_shared_budget_single_instance():
    """rerank 与 ask_llm 必须共用同一预算实例（防额度翻倍、Mongo 互相覆盖）。"""
    from src.plugins.language.ask_llm import _budget as ask_budget
    from src.plugins.language.llm_util import budget
    from src.plugins.language.rerank_reply import _budget as rerank_budget

    assert ask_budget is budget
    assert rerank_budget is budget


@pytest.mark.asyncio
async def test_preprocessor_budget_exhausted_falls_back(monkeypatch):
    """预算已耗尽 → consume gate 拒绝：不调 LLM，直接降级（None）。"""
    from src.ext.llm import DailyCostBudget
    from src.ext.llm.budget import _budget_collection

    await _budget_collection.drop()
    exhausted = DailyCostBudget(3.0)
    exhausted._consumed_fen = exhausted._limit_fen
    monkeypatch.setattr("src.plugins.language.ask_llm._budget", exhausted)
    pre = AskLlmPreprocessor()
    monkeypatch.setattr(
        "src.plugins.language.ask_llm._load_prompt",
        lambda: "你是鸮鸮，{__points__}",
    )
    llm = AsyncMock(return_value=["光散射"])
    monkeypatch.setattr("src.plugins.language.ask_llm.ask_llm_replace", llm)
    monkeypatch.setattr(
        "src.plugins.language.ask_llm._pick_mode", lambda prob: "generate"
    )
    result = await pre.try_preprocess("为什么天会黑", {}, ["A", "B"], group_id=100)
    assert result is None
    llm.assert_not_awaited()  # gate 在调 LLM 前拦截


@pytest.mark.asyncio
async def test_ask_llm_rank_timeout_refunds(monkeypatch):
    """rank 超时 → 退还预留预算。"""
    from src.ext.llm import DailyCostBudget
    from src.ext.llm.budget import _budget_collection

    await _budget_collection.drop()
    fake = DailyCostBudget(3.0)
    await fake.ensure_loaded()
    before = fake.consumed_fen
    assert await fake.consume(1)
    monkeypatch.setattr("src.plugins.language.ask_llm._budget", fake)
    monkeypatch.setattr(
        "src.plugins.language.llm_util.get_chat_model",
        lambda **kw: _fake_llm(asyncio.TimeoutError),
    )
    assert (await ask_llm_rank("s", "u", k=3)).value is None
    assert fake.consumed_fen == before  # 预留已全额退回


@pytest.mark.asyncio
async def test_preprocessor_generation_logs_to_mongo(monkeypatch):
    """成功路径落 ask_llm_log：记录模式、替换值、结果。"""
    pre = AskLlmPreprocessor()
    monkeypatch.setattr(
        "src.plugins.language.ask_llm._load_prompt",
        lambda: "你是鸮鸮，{__points__}",
    )
    monkeypatch.setattr(
        "src.plugins.language.ask_llm.ask_llm_replace",
        AsyncMock(return_value=LlmCallResult(value=["光散射"])),
    )
    monkeypatch.setattr(
        "src.plugins.language.ask_llm._pick_mode", lambda prob: "generate"
    )
    await ask_llm_logs.drop()
    try:
        result = await pre.try_preprocess("为什么天会黑", {}, ["A", "B"], group_id=100)
        assert result is not None
        logs = [log async for log in ask_llm_logs.find_all({})]
        assert len(logs) == 1
        log = logs[0]
        assert log.group_id == 100
        assert log.question == "为什么天会黑"
        assert log.mode == "generate"
        assert log.replacements == ["光散射"]
        assert "因为光散射" in log.result
    finally:
        await ask_llm_logs.drop()


@pytest.mark.asyncio
async def test_preprocessor_fallback_logs_to_mongo(monkeypatch):
    """降级路径落 ask_llm_log：mode=fallback。"""
    pre = AskLlmPreprocessor()
    monkeypatch.setattr(
        "src.plugins.language.ask_llm._load_prompt",
        lambda: "你是鸮鸮，{__points__}",
    )
    monkeypatch.setattr(
        "src.plugins.language.ask_llm.ask_llm_replace",
        AsyncMock(return_value=LlmCallResult(value=None, error="mock failure")),
    )
    monkeypatch.setattr(
        "src.plugins.language.ask_llm._pick_mode", lambda prob: "generate"
    )
    await ask_llm_logs.drop()
    try:
        result = await pre.try_preprocess("吃什么", {}, ["A"], group_id=100)
        assert result is None
        logs = [log async for log in ask_llm_logs.find_all({})]
        assert len(logs) == 1
        assert logs[0].mode == "fallback"
        assert logs[0].error == "mock failure"
    finally:
        await ask_llm_logs.drop()


@pytest.mark.asyncio
async def test_preprocessor_fallback_logs_raw_and_error(monkeypatch):
    """fallback 落库带 LLM 原始响应 + 具体失败原因（debug 用）。"""
    pre = AskLlmPreprocessor()
    monkeypatch.setattr(
        "src.plugins.language.ask_llm._load_prompt",
        lambda: "你是鸮鸮，{__points__}",
    )
    monkeypatch.setattr(
        "src.plugins.language.ask_llm.ask_llm_replace",
        AsyncMock(
            return_value=LlmCallResult(
                value=None,
                raw='{"replacements":["光散"]}',
                error="replacement[0] '光散' invalid (want length 3)",
            )
        ),
    )
    monkeypatch.setattr(
        "src.plugins.language.ask_llm._pick_mode", lambda prob: "generate"
    )
    await ask_llm_logs.drop()
    try:
        result = await pre.try_preprocess("吃什么", {}, ["A"], group_id=100)
        assert result is None
        logs = [log async for log in ask_llm_logs.find_all({})]
        assert len(logs) == 1
        assert logs[0].mode == "fallback"
        assert "want length 3" in logs[0].error
        assert '"replacements":["光散"]' in logs[0].raw_response
    finally:
        await ask_llm_logs.drop()


@pytest.mark.asyncio
async def test_preprocessor_weighted_success(monkeypatch):
    """加权模式 rank 成功 → 返回加权选中值，不再调纯生成。"""
    pre = AskLlmPreprocessor()
    monkeypatch.setattr(
        "src.plugins.language.ask_llm._load_prompt", lambda: "模板{__points__}"
    )
    monkeypatch.setattr(
        "src.plugins.language.ask_llm._pick_mode", lambda prob: "weighted"
    )
    monkeypatch.setattr(
        "src.plugins.language.ask_llm.retrieve_candidates",
        AsyncMock(return_value=["候选甲"]),
    )
    monkeypatch.setattr(
        "src.plugins.language.ask_llm.weighted_select",
        AsyncMock(return_value=LlmCallResult(value="披萨")),
    )
    replace = AsyncMock(return_value=["光散射"])
    monkeypatch.setattr("src.plugins.language.ask_llm.ask_llm_replace", replace)
    result = await pre.try_preprocess("吃什么", {}, ["A"], group_id=100)
    assert result == "吃披萨"
    replace.assert_not_awaited()


@pytest.mark.asyncio
async def test_preprocessor_weighted_fail_degrades_to_random(monkeypatch):
    """加权模式 rank 失败/超时 → 直接降级随机（返回 None），不再二次 LLM 调用。"""
    pre = AskLlmPreprocessor()
    monkeypatch.setattr(
        "src.plugins.language.ask_llm._load_prompt", lambda: "模板{__points__}"
    )
    monkeypatch.setattr(
        "src.plugins.language.ask_llm._pick_mode", lambda prob: "weighted"
    )
    monkeypatch.setattr(
        "src.plugins.language.ask_llm.retrieve_candidates",
        AsyncMock(return_value=["候选甲", "候选乙"]),
    )
    monkeypatch.setattr(
        "src.plugins.language.ask_llm.weighted_select", AsyncMock(return_value=None)
    )
    replace = AsyncMock(return_value=["光散射"])
    monkeypatch.setattr("src.plugins.language.ask_llm.ask_llm_replace", replace)
    result = await pre.try_preprocess("吃什么", {}, ["A"], group_id=100)
    assert result is None
    replace.assert_not_awaited()


def test_build_replacement_prompt_with_length():
    from src.plugins.language.ask import ReplacementPoint

    rendered = "吃\x000\x00"
    points = [ReplacementPoint(kw="什么", start=1, length=2)]
    user = build_replacement_prompt(rendered, points)
    assert '<replacement index="0" type="什么" length="2"/>' in user


def test_build_replacement_prompt_no_length_attr():
    from src.plugins.language.ask import ReplacementPoint

    rendered = "因为\x000\x00，所以天会黑"
    points = [ReplacementPoint(kw="为什么", start=0, length=None)]
    user = build_replacement_prompt(rendered, points)
    assert '<replacement index="0" type="为什么"/>' in user
    assert "length=" not in user


def test_replace_symtab0_images_preserves_at():
    """非图片 PUA（at）原样保留，供 _finalize 还原。"""
    from nonebot.adapters.onebot.v11 import MessageSegment

    from src.plugins.language.ask_llm import _replace_symtab0_images

    symtab0 = {"\ue000": MessageSegment.at(123456)}
    result = _replace_symtab0_images("\ue000", symtab0)
    assert result == "\ue000"  # at 保留


def test_pick_mode_generation(monkeypatch):
    monkeypatch.setattr("src.plugins.language.ask_llm.random", random)
    monkeypatch.setattr(random, "random", lambda: 0.1)
    assert _pick_mode(generate_prob=0.5) == "generate"


def test_pick_mode_weighted(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 0.9)
    assert _pick_mode(generate_prob=0.5) == "weighted"


@pytest.mark.asyncio
async def test_retrieve_candidates_filters_length(monkeypatch):
    """按 length/sample 委托 Corpus.find 并抽取 text 字段。"""
    entries = [{"text": "短", "keywords": {}}, {"text": "中等长度", "keywords": {}}]

    class _Cursor:
        def __init__(self, e):
            self.e = e

        async def to_list(self, length=None):
            return self.e

    find = AsyncMock(return_value=_Cursor(entries))
    monkeypatch.setattr("src.plugins.language.ask_llm.Corpus.find", find)
    got = await retrieve_candidates(100, length=(2, 4), sample=16)
    assert got == ["短", "中等长度"]
    find.assert_awaited_once_with(group_id=100, length=(2, 4), sample=10)


@pytest.mark.asyncio
async def test_weighted_select_uses_rank(monkeypatch):
    """加权随机：rank 倒序权重，高分候选更可能被选中。"""
    candidates = ["a", "b", "c"]
    monkeypatch.setattr(
        "src.plugins.language.ask_llm.ask_llm_rank",
        AsyncMock(
            return_value=LlmCallResult(value=[2, 1, 3], raw='{"ranks":[2,1,3]}')
        ),  # b rank1 权重最高
    )
    monkeypatch.setattr("src.plugins.language.ask_llm.random", random)
    counts = {"a": 0, "b": 0, "c": 0}
    for _ in range(500):
        r = await weighted_select("system", "user", candidates)
        counts[r.value] += 1
    assert counts["b"] > counts["a"] and counts["b"] > counts["c"]
    assert counts["c"] == 0  # rank3 权重 0，永不选中


@pytest.mark.asyncio
async def test_answer_llm_path_sets_replacement(monkeypatch):
    """LLM 路径 self.replacement 置 True，answer 返回非 None。"""
    from src.plugins.language.ask import Ask

    ask = Ask(None, 119056244, Message("问为什么天会黑"))
    monkeypatch.setattr(
        "src.plugins.language.ask.list_group_member_names", AsyncMock(return_value=[])
    )
    monkeypatch.setattr(
        "src.plugins.language.ask_llm.AskLlmPreprocessor",
        lambda: SimpleNamespace(
            try_preprocess=AsyncMock(return_value="因为光散射，所以天会黑")
        ),
    )
    monkeypatch.setattr(
        "src.plugins.language.config._ask_llm_enabled", AsyncMock(return_value=True)
    )
    result = await ask.answer()
    assert result is not None
    assert ask.replacement is True


@pytest.mark.asyncio
async def test_answer_llm_fallback_to_process(monkeypatch):
    """LLM 返回 None → 走原 process 路径。"""
    from src.plugins.language.ask import Ask

    ask = Ask(None, 119056244, Message("问为什么天会黑"))
    monkeypatch.setattr(
        "src.plugins.language.ask.list_group_member_names", AsyncMock(return_value=[])
    )
    monkeypatch.setattr(
        "src.plugins.language.ask_llm.AskLlmPreprocessor",
        lambda: SimpleNamespace(try_preprocess=AsyncMock(return_value=None)),
    )
    monkeypatch.setattr(
        "src.plugins.language.config._ask_llm_enabled", AsyncMock(return_value=True)
    )
    # 测试环境无可用语料（dev.corpus 无本组数据且新条目被 fresh 过滤器排除），
    # mock 语料边界 random_reason，保持 process() 其余逻辑真实执行。
    monkeypatch.setattr(Ask, "random_reason", AsyncMock(return_value="光散射"))
    result = await ask.answer()
    assert result is not None  # 原路径正常出结果
