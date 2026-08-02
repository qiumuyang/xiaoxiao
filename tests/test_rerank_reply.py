import asyncio
import random
import time
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from nonebot.adapters.onebot.v11 import Message

from src.ext.config import ConfigManager
from src.ext.llm import DailyCostBudget
from src.plugins.language import rerank_reply as rr
from src.plugins.language.config import RerankReplyConfig, get_route_prob
from src.plugins.language.interact import RandomResponse, _InteractMessage
from src.plugins.language.rerank_reply import (
    CONTEXT_N,
    RERANK_CORPUS_SAMPLES,
    RERANK_SIM_THRESHOLD,
    RerankLog,
    RerankOutput,
    RerankReply,
    _load_prompt,
    build_context,
    build_prompt,
    build_user_prompt,
    list_logs,
    parse_log_page,
    parse_ranks,
    rerank_logs,
    retrieve_rerank_candidates,
)
from src.utils.message.receive import MessageData as RMD
from src.utils.message.receive import ReceivedMessageTracker as RMT
from src.utils.message.send import MessageData as SMD
from src.utils.message.send import SentMessageTracker as SMT


def _group_filter(group_id: int) -> dict:
    return {
        "name": ConfigManager.config_name(RerankReplyConfig),
        "user_id": None,
        "group_id": group_id,
    }


@pytest.mark.asyncio
async def test_rerank_config_defaults():
    await ConfigManager.config.delete_one(_group_filter(100))
    cfg = await RerankReplyConfig.get(group_id=100)
    assert cfg.enabled is False
    assert cfg.route_prob == 0.3
    assert get_route_prob() == 0.3


@pytest.mark.asyncio
async def test_rerank_config_per_group_set():
    filter = _group_filter(100)
    await ConfigManager.config.delete_one(filter)  # clean start
    try:
        await RerankReplyConfig.set(RerankReplyConfig(enabled=False), group_id=100)
        cfg = await RerankReplyConfig.get(group_id=100)
        assert cfg.enabled is False
        # 不污染其他群
        other = await RerankReplyConfig.get(group_id=200)
        assert other.enabled is False
        # route_prob 为普通字段，随配置持久化
        assert "route_prob" in RerankReplyConfig(enabled=False).model_dump()
    finally:
        await ConfigManager.config.delete_one(filter)


TEMPLATE = """你是鸮鸮（self_id={self_id}）。
- 输出 {ranks: [K个序号]}，包含 1..K 各一次，按贴合度高→低
- 上下文里你自己的发言可能是复读/随机语料，别当真
"""


def test_load_prompt_missing_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr("src.plugins.language.rerank_reply._prompt_cache", None)
    monkeypatch.setattr(
        "src.plugins.language.rerank_reply.PROMPT_PATH", tmp_path / "nope.txt"
    )
    assert _load_prompt() is None


def test_load_prompt_reads_and_caches(tmp_path, monkeypatch):
    monkeypatch.setattr("src.plugins.language.rerank_reply._prompt_cache", None)
    p = tmp_path / "prompt.txt"
    p.write_text(TEMPLATE)
    monkeypatch.setattr("src.plugins.language.rerank_reply.PROMPT_PATH", p)
    assert _load_prompt() == TEMPLATE
    assert _load_prompt() == TEMPLATE  # 命中缓存


def test_load_prompt_reloads_on_mtime_change(tmp_path, monkeypatch):
    monkeypatch.setattr("src.plugins.language.rerank_reply._prompt_cache", None)
    p = tmp_path / "prompt.txt"
    p.write_text("v1")
    monkeypatch.setattr("src.plugins.language.rerank_reply.PROMPT_PATH", p)
    assert _load_prompt() == "v1"
    time.sleep(0.02)
    p.write_text("v2")
    assert _load_prompt() == "v2"


def test_build_user_prompt():
    context = [
        "[2026-08-02 12:01] 张三(1): 今天要下雨",
        "[2026-08-02 12:02] 李四(2): 别出门",
    ]
    candidates = ["下雨天窝着打游戏", "出门带伞"]
    user = build_user_prompt(context, candidates, context_n=20, k=5)
    assert "今天要下雨" in user and "下雨天窝着打游戏" in user
    assert user.startswith("# 最近群聊")
    assert "1. 下雨天窝着打游戏" in user and "2. 出门带伞" in user


def test_build_user_prompt_with_group_name():
    context = ["[2026-08-02 12:01] 张三(1): hi"]
    candidates = ["a"]
    user = build_user_prompt(
        context, candidates, context_n=20, k=5, group_name="上班摸鱼群"
    )
    assert user.startswith("# 群聊：上班摸鱼群")
    assert "最近群聊" in user
    # 无群名时保持原样
    no_name = build_user_prompt(context, candidates, context_n=20, k=5)
    assert no_name.startswith("# 最近群聊")


def test_build_prompt_fills_placeholders():
    context = ["[2026-08-02 12:01] 张三(1): hi"]
    candidates = ["a", "b", "c"]
    tpl = "你是鸮鸮（self_id={self_id}），最多 {CONTEXT_N} 条，输出 1..{K}"
    system, user = build_prompt(
        tpl, context, candidates, self_id=999, context_n=20, k=3
    )
    assert "self_id=999" in system
    assert "最多 20 条" in system and "输出 1..3" in system
    assert (
        "{self_id}" not in system
        and "{CONTEXT_N}" not in system
        and "{K}" not in system
    )
    assert "1. a" in user


def test_parse_ranks_valid():
    assert parse_ranks([3, 1, 2], k=3) == 3
    assert parse_ranks([1], k=1) == 1


def test_parse_ranks_invalid():
    assert parse_ranks([1, 2], k=3) is None  # 长度不符
    assert parse_ranks([1, 1, 2], k=3) is None  # 重复
    assert parse_ranks([1, 2, 4], k=3) is None  # 越界
    assert parse_ranks([], k=3) is None


def _recv_msg(text: str, *, user_id: int = 1) -> RMD:
    return RMD(
        time=datetime.now(),
        user_id=user_id,
        group_id=100,
        message_id=1,
        content=Message(text),
        handled=True,
    )


def _sent_msg(text: str) -> SMD:
    return SMD(
        session_id="group_100_999",
        message_id=1,
        time=datetime.now(),
        recalled=False,
        content=Message(text),
    )


def _fake_bot():
    return SimpleNamespace(
        self_id="999",
        send_group_msg=AsyncMock(),
        get_group_member_info=AsyncMock(
            return_value={"card": "张三", "nickname": "张三"}
        ),
    )


def _fake_find_all(items, calls=None):
    """Return an async-generator stand-in for Collection.find_all(filter, **kwargs)."""

    async def _find_all(filter, *args, **kwargs):
        if calls is not None:
            calls.append((filter, kwargs))
        for item in items:
            yield item

    return _find_all


@pytest.mark.asyncio
async def test_build_context_format(monkeypatch):
    bot = _fake_bot()
    monkeypatch.setattr("src.plugins.language.rerank_reply.get_bot", lambda: bot)
    monkeypatch.setattr(
        RMT.received,
        "find_all",
        _fake_find_all([_recv_msg("今天要下雨", user_id=1)]),
    )
    monkeypatch.setattr(
        SMT.sent, "find_all", _fake_find_all([_sent_msg("[复读] 别出门")])
    )
    lines = await build_context(100)
    assert len(lines) == 2
    assert "张三(1): 今天要下雨" in lines[0]
    assert "999) [self]: [复读] 别出门" in lines[1]
    assert lines[0].startswith("[20")  # [YYYY-MM-DD HH:MM]


@pytest.mark.asyncio
async def test_build_context_skips_empty_text(monkeypatch):
    bot = _fake_bot()
    monkeypatch.setattr("src.plugins.language.rerank_reply.get_bot", lambda: bot)
    empty = RMD(
        time=datetime.now(),
        user_id=1,
        group_id=100,
        message_id=1,
        content=Message(),
        handled=True,
    )
    monkeypatch.setattr(RMT.received, "find_all", _fake_find_all([empty]))
    monkeypatch.setattr(SMT.sent, "find_all", _fake_find_all([]))
    assert await build_context(100) == []


@pytest.mark.asyncio
async def test_build_context_member_name_fallback(monkeypatch):
    bot = _fake_bot()

    async def _fail_info(*args, **kwargs):
        raise RuntimeError("member not found")

    bot.get_group_member_info = _fail_info
    monkeypatch.setattr("src.plugins.language.rerank_reply.get_bot", lambda: bot)
    monkeypatch.setattr(
        RMT.received, "find_all", _fake_find_all([_recv_msg("hi", user_id=42)])
    )
    monkeypatch.setattr(SMT.sent, "find_all", _fake_find_all([]))
    lines = await build_context(100)
    assert len(lines) == 1 and "42): hi" in lines[0]


@pytest.mark.asyncio
async def test_build_context_truncates_to_context_n(monkeypatch):
    bot = _fake_bot()
    monkeypatch.setattr("src.plugins.language.rerank_reply.get_bot", lambda: bot)
    recv_msgs = [_recv_msg(f"msg-{i}", user_id=i) for i in range(CONTEXT_N + 5)]
    recv_calls = []
    monkeypatch.setattr(RMT.received, "find_all", _fake_find_all(recv_msgs, recv_calls))
    monkeypatch.setattr(SMT.sent, "find_all", _fake_find_all([]))
    lines = await build_context(100)
    assert len(lines) == CONTEXT_N
    assert "msg-24" in lines[-1]
    # 数据库层即已带上限，避免活跃群全量拉取
    assert recv_calls[0][1]["limit"] == CONTEXT_N * 2


@pytest.mark.asyncio
async def test_build_context_interleaves_recv_sent_by_time(monkeypatch):
    bot = _fake_bot()
    monkeypatch.setattr("src.plugins.language.rerank_reply.get_bot", lambda: bot)
    base = datetime(2026, 8, 2, 10, 0, 0)
    recv1 = RMD(
        time=base,
        user_id=1,
        group_id=100,
        message_id=1,
        content=Message("first"),
        handled=True,
    )
    sent = SMD(
        session_id="group_100_999",
        message_id=2,
        time=base + timedelta(minutes=1),
        recalled=False,
        content=Message("second"),
    )
    recv2 = RMD(
        time=base + timedelta(minutes=2),
        user_id=2,
        group_id=100,
        message_id=3,
        content=Message("third"),
        handled=True,
    )
    monkeypatch.setattr(RMT.received, "find_all", _fake_find_all([recv1, recv2]))
    monkeypatch.setattr(SMT.sent, "find_all", _fake_find_all([sent]))
    lines = await build_context(100)
    assert len(lines) == 3
    assert "first" in lines[0] and "second" in lines[1] and "third" in lines[2]


async def _set_budget(monkeypatch, yuan: float):
    from src.ext.llm.budget import _budget_collection

    await _budget_collection.drop()
    monkeypatch.setattr(
        "src.plugins.language.rerank_reply._budget", DailyCostBudget(yuan)
    )


@pytest.mark.asyncio
async def test_rank_and_select_returns_top(monkeypatch):
    await _set_budget(monkeypatch, 3.0)
    bot = SimpleNamespace(self_id="999", send_group_msg=AsyncMock())
    monkeypatch.setattr("src.plugins.language.rerank_reply.get_bot", lambda: bot)
    monkeypatch.setattr(
        "src.plugins.language.rerank_reply.build_context",
        AsyncMock(return_value=["[2026-08-02 12:01] 张三(1): hi"]),
    )
    monkeypatch.setattr(
        "src.plugins.language.rerank_reply._load_prompt",
        lambda: "你是鸮鸮（self_id={self_id}）",
    )
    monkeypatch.setattr(
        "src.plugins.language.rerank_reply.RerankReply._invoke_llm",
        AsyncMock(return_value=RerankOutput(ranks=[2, 1, 3])),
    )
    await rerank_logs.drop()
    result = await RerankReply.rank_and_select(100, ["a", "b", "c"])
    assert result is not None
    assert result.extract_plain_text() == "b"
    logs = [log async for log in rerank_logs.find_all({})]
    assert len(logs) == 1
    assert logs[0].selected == "b" and logs[0].candidates == ["a", "b", "c"]
    await rerank_logs.drop()


@pytest.mark.asyncio
async def test_rank_and_select_bad_ranks_falls_back(monkeypatch):
    await _set_budget(monkeypatch, 3.0)
    bot = SimpleNamespace(self_id="999", send_group_msg=AsyncMock())
    monkeypatch.setattr("src.plugins.language.rerank_reply.get_bot", lambda: bot)
    monkeypatch.setattr(
        "src.plugins.language.rerank_reply.build_context",
        AsyncMock(return_value=["ctx"]),
    )
    monkeypatch.setattr(
        "src.plugins.language.rerank_reply._load_prompt",
        lambda: "你是鸮鸮（self_id={self_id}）",
    )
    monkeypatch.setattr(
        "src.plugins.language.rerank_reply.RerankReply._invoke_llm",
        AsyncMock(return_value=RerankOutput(ranks=[1, 1, 2])),
    )
    assert await RerankReply.rank_and_select(100, ["a", "b", "c"]) is None


@pytest.mark.asyncio
async def test_rank_and_select_llm_error_falls_back(monkeypatch):
    await _set_budget(monkeypatch, 3.0)
    bot = SimpleNamespace(self_id="999", send_group_msg=AsyncMock())
    monkeypatch.setattr("src.plugins.language.rerank_reply.get_bot", lambda: bot)
    monkeypatch.setattr(
        "src.plugins.language.rerank_reply.build_context",
        AsyncMock(return_value=["ctx"]),
    )
    monkeypatch.setattr(
        "src.plugins.language.rerank_reply._load_prompt",
        lambda: "你是鸮鸮（self_id={self_id}）",
    )
    monkeypatch.setattr(
        "src.plugins.language.rerank_reply.RerankReply._invoke_llm",
        AsyncMock(return_value=None),
    )
    assert await RerankReply.rank_and_select(100, ["a", "b", "c"]) is None


@pytest.mark.asyncio
async def test_rank_and_select_timeout_falls_back(monkeypatch):
    await _set_budget(monkeypatch, 3.0)
    bot = SimpleNamespace(self_id="999", send_group_msg=AsyncMock())
    monkeypatch.setattr("src.plugins.language.rerank_reply.get_bot", lambda: bot)
    monkeypatch.setattr(
        "src.plugins.language.rerank_reply.build_context",
        AsyncMock(return_value=["ctx"]),
    )
    monkeypatch.setattr(
        "src.plugins.language.rerank_reply._load_prompt",
        lambda: "你是鸮鸮（self_id={self_id}）",
    )
    monkeypatch.setattr(
        "src.plugins.language.rerank_reply.RerankReply._invoke_llm",
        AsyncMock(side_effect=asyncio.TimeoutError),
    )
    assert await RerankReply.rank_and_select(100, ["a", "b", "c"]) is None


@pytest.mark.asyncio
async def test_rank_and_select_budget_reject_notifies(monkeypatch):
    await _set_budget(monkeypatch, 0.0)  # 0 元 → 必然拒绝
    bot = SimpleNamespace(self_id="999", send_group_msg=AsyncMock())
    monkeypatch.setattr("src.plugins.language.rerank_reply.get_bot", lambda: bot)
    monkeypatch.setattr(
        "src.plugins.language.rerank_reply.build_context",
        AsyncMock(return_value=["ctx"]),
    )
    monkeypatch.setattr(
        "src.plugins.language.rerank_reply._load_prompt",
        lambda: "你是鸮鸮（self_id={self_id}）",
    )
    monkeypatch.setattr("src.plugins.language.rerank_reply._last_notify_date", None)
    monkeypatch.setenv("ALERT_GROUP_ID", "777")
    assert await RerankReply.rank_and_select(100, ["a"]) is None
    bot.send_group_msg.assert_awaited_once()
    # 当天第二次不再通知
    bot.send_group_msg.reset_mock()
    assert await RerankReply.rank_and_select(100, ["a"]) is None
    bot.send_group_msg.assert_not_awaited()


@pytest.mark.asyncio
async def test_rank_and_select_missing_prompt_falls_back(monkeypatch):
    await _set_budget(monkeypatch, 3.0)
    monkeypatch.setattr("src.plugins.language.rerank_reply._load_prompt", lambda: None)
    assert await RerankReply.rank_and_select(100, ["a"]) is None


def _fake_llm_ainvoke(side_effect):
    return SimpleNamespace(
        with_structured_output=lambda *a, **k: SimpleNamespace(
            ainvoke=AsyncMock(side_effect=side_effect)
        )
    )


@pytest.mark.asyncio
async def test_budget_persists_across_instances(monkeypatch):
    """当日已消费量持久化：新实例能从 Mongo 读回，重启不归零。"""
    from src.ext.llm.budget import _budget_collection

    await _budget_collection.drop()
    first = DailyCostBudget(3.0)
    assert await first.consume(100)
    second = DailyCostBudget(3.0)
    assert second.consumed_fen == 0  # 未加载
    await second.ensure_loaded()
    assert second.consumed_fen == 100
    await _budget_collection.drop()


@pytest.mark.asyncio
async def test_budget_resets_on_new_day(monkeypatch):
    """跨天归零：新的一天从 0 开始，且不读前一天残留，Mongo 各自成档。"""
    import src.ext.llm.budget as budget_mod

    await budget_mod._budget_collection.drop()

    class FakeDateTime(datetime):
        _now = datetime(2026, 8, 2, 23, 59, tzinfo=budget_mod._CST)

        @classmethod
        def now(cls, tz=None):
            return cls._now

    monkeypatch.setattr(budget_mod, "datetime", FakeDateTime)
    b = DailyCostBudget(3.0)
    assert await b.consume(100)
    FakeDateTime._now = datetime(2026, 8, 3, 0, 1, tzinfo=budget_mod._CST)
    assert await b.consume(50)
    assert b.consumed_fen == 50  # 归零后只计今天
    docs = [d async for d in budget_mod._budget_collection.find_all({})]
    assert sorted(d["_id"] for d in docs) == ["2026-08-02", "2026-08-03"]
    await budget_mod._budget_collection.drop()


@pytest.mark.asyncio
async def test_budget_status_loads_persisted(monkeypatch):
    """状态命令从 Mongo 读当日已消费量：新实例未预加载也能读到。"""
    from src.ext.llm.budget import _budget_collection

    await _budget_collection.drop()
    seed = DailyCostBudget(3.0)
    assert await seed.consume(rr.ESTIMATED_FEN)
    monkeypatch.setattr(
        "src.plugins.language.rerank_reply._budget", DailyCostBudget(3.0)
    )
    text = await RerankReply.budget_status()
    assert text.startswith("0.01 元")
    await _budget_collection.drop()


@pytest.mark.asyncio
async def test_invoke_llm_error_refunds(monkeypatch):
    await _set_budget(monkeypatch, 3.0)
    monkeypatch.setattr(
        "src.plugins.language.rerank_reply.get_chat_model",
        lambda **kw: _fake_llm_ainvoke(RuntimeError("api down")),
    )
    await rr._budget.consume(rr.ESTIMATED_FEN)
    assert await RerankReply._invoke_llm("s", "u") is None
    assert rr._budget.consumed_fen == 0


@pytest.mark.asyncio
async def test_invoke_llm_timeout_refunds(monkeypatch):
    await _set_budget(monkeypatch, 3.0)
    monkeypatch.setattr(
        "src.plugins.language.rerank_reply.get_chat_model",
        lambda **kw: _fake_llm_ainvoke(asyncio.TimeoutError),
    )
    await rr._budget.consume(rr.ESTIMATED_FEN)
    assert await RerankReply._invoke_llm("s", "u") is None
    assert rr._budget.consumed_fen == 0


class _FakeCursor:
    def __init__(self, entries):
        self._entries = entries

    async def to_list(self, length=None):
        return self._entries


def _patch_keyword_pipeline(monkeypatch, candidates):
    """让 keyword_respond 直达 `if results:` 分支（跳过 Mongo/分词）。"""
    monkeypatch.setattr(RandomResponse, "KW_PROB", 1.0)
    monkeypatch.setattr(RandomResponse, "KW_MIN_QUERY_LEN", 1)
    monkeypatch.setattr(RandomResponse, "KW_AFTER_PROB", 0.0)
    monkeypatch.setattr(RandomResponse, "KW_BY_RECENT_K_MESSAGES", 3)
    entries = [{"text": t, "keywords": []} for t in candidates]
    monkeypatch.setattr(
        "src.plugins.language.interact.Corpus.find",
        AsyncMock(return_value=_FakeCursor(entries)),
    )
    monkeypatch.setattr(
        "src.plugins.language.interact.Keyword.search",
        lambda *a, **kw: candidates,
    )


@pytest.mark.asyncio
async def test_keyword_respond_routes_to_rerank(monkeypatch):
    """启用 + 概率命中 → 走 rerank，返回 rerank 选中的候选。"""
    monkeypatch.setattr(random, "random", lambda: 0.1)
    monkeypatch.setattr(
        "src.plugins.language.interact.RerankReplyConfig.get",
        AsyncMock(return_value=RerankReplyConfig(enabled=True)),
    )
    _patch_keyword_pipeline(monkeypatch, ["a", "b", "c"])
    rank = AsyncMock(return_value=Message("选中的话"))
    monkeypatch.setattr(
        "src.plugins.language.interact.RerankReply.rank_and_select", rank
    )
    messages = [_InteractMessage(True, Message("今天要下雨"))]
    result = await RandomResponse.keyword_respond(100, messages)
    assert result is not None
    assert result.extract_plain_text() == "选中的话"
    rank.assert_awaited_once_with(100, ["a", "b", "c"])


@pytest.mark.asyncio
async def test_keyword_respond_not_enabled_skips_rerank(monkeypatch):
    """未启用 → 不调 rerank，随机选候选。"""
    monkeypatch.setattr(
        "src.plugins.language.interact.RerankReplyConfig.get",
        AsyncMock(return_value=RerankReplyConfig(enabled=False)),
    )
    _patch_keyword_pipeline(monkeypatch, ["a", "b"])
    rank = AsyncMock()
    monkeypatch.setattr(
        "src.plugins.language.interact.RerankReply.rank_and_select", rank
    )
    messages = [_InteractMessage(True, Message("今天要下雨"))]
    result = await RandomResponse.keyword_respond(100, messages)
    assert result is not None and result.extract_plain_text() in {"a", "b"}
    rank.assert_not_awaited()


@pytest.mark.asyncio
async def test_keyword_respond_prob_miss_skips_rerank(monkeypatch):
    """启用但概率未命中 → 不调 rerank，随机选候选。"""
    monkeypatch.setattr(random, "random", lambda: 0.9)  # >= route_prob 0.3
    monkeypatch.setattr(
        "src.plugins.language.interact.RerankReplyConfig.get",
        AsyncMock(return_value=RerankReplyConfig(enabled=True)),
    )
    _patch_keyword_pipeline(monkeypatch, ["a", "b"])
    rank = AsyncMock()
    monkeypatch.setattr(
        "src.plugins.language.interact.RerankReply.rank_and_select", rank
    )
    messages = [_InteractMessage(True, Message("今天要下雨"))]
    result = await RandomResponse.keyword_respond(100, messages)
    assert result is not None and result.extract_plain_text() in {"a", "b"}
    rank.assert_not_awaited()


@pytest.mark.asyncio
async def test_keyword_respond_rerank_returns_none_falls_back(monkeypatch):
    """rerank 返回 None（降级）→ 随机选候选。"""
    monkeypatch.setattr(random, "random", lambda: 0.1)
    monkeypatch.setattr(
        "src.plugins.language.interact.RerankReplyConfig.get",
        AsyncMock(return_value=RerankReplyConfig(enabled=True)),
    )
    _patch_keyword_pipeline(monkeypatch, ["a", "b"])
    rank = AsyncMock(return_value=None)
    monkeypatch.setattr(
        "src.plugins.language.interact.RerankReply.rank_and_select", rank
    )
    messages = [_InteractMessage(True, Message("今天要下雨"))]
    result = await RandomResponse.keyword_respond(100, messages)
    assert result is not None and result.extract_plain_text() in {"a", "b"}
    rank.assert_awaited_once()


def test_parse_log_page():
    assert parse_log_page("") == 1
    assert parse_log_page("2") == 2
    assert parse_log_page("abc") == 1
    assert parse_log_page("0") == 1
    assert parse_log_page("-1") == 1


@pytest.mark.asyncio
async def test_list_logs_paginates_desc():
    await rerank_logs.drop()
    base = datetime.now(UTC)
    for i in range(5):
        await rerank_logs.insert_one(
            RerankLog(
                group_id=100,
                context=[],
                candidates=["c"],
                ranks=[1],
                selected="c",
                prompt_version="v1",
                logged_at=base + timedelta(minutes=i),
            )
        )
    try:
        p1 = await list_logs(group_id=None, page=1, page_size=2)
        p2 = await list_logs(group_id=None, page=2, page_size=2)
        p3 = await list_logs(group_id=None, page=3, page_size=2)
        assert [log.logged_at for log in p1] == [
            base + timedelta(minutes=4),
            base + timedelta(minutes=3),
        ]
        assert [log.logged_at for log in p2] == [
            base + timedelta(minutes=2),
            base + timedelta(minutes=1),
        ]
        assert [log.logged_at for log in p3] == [base + timedelta(minutes=0)]
        # group filter
        gf = await list_logs(group_id=100, page=1, page_size=10)
        assert len(gf) == 5
        gf2 = await list_logs(group_id=999, page=1, page_size=10)
        assert gf2 == []
    finally:
        await rerank_logs.drop()


@pytest.mark.asyncio
async def test_list_enabled_only_group_docs():
    name = ConfigManager.config_name(RerankReplyConfig)
    await RerankReplyConfig.set(RerankReplyConfig(enabled=True), group_id=100)
    await RerankReplyConfig.set(RerankReplyConfig(enabled=False), group_id=200)
    try:
        enabled = await RerankReplyConfig.list_enabled()
        assert (100, True) in enabled and (200, False) in enabled
    finally:
        for gid in (100, 200):
            await ConfigManager.config.delete_one(
                {"name": name, "user_id": None, "group_id": gid}
            )


@pytest.mark.asyncio
async def test_rank_and_select_passes_group_name(monkeypatch):
    """rank_and_select 把群名传入 build_prompt。"""
    await _set_budget(monkeypatch, 3.0)
    bot = SimpleNamespace(
        self_id="999",
        send_group_msg=AsyncMock(),
        get_group_info=AsyncMock(return_value={"group_name": "上班摸鱼群"}),
    )
    monkeypatch.setattr("src.plugins.language.rerank_reply.get_bot", lambda: bot)
    monkeypatch.setattr(
        "src.plugins.language.rerank_reply.build_context",
        AsyncMock(return_value=["ctx"]),
    )
    monkeypatch.setattr(
        "src.plugins.language.rerank_reply._load_prompt",
        lambda: "你是鸮鸮（self_id={self_id}）",
    )
    captured = {}

    def fake_build_prompt(system_template, context, candidates, **kw):
        captured.update(kw)
        return "sys", "user"

    monkeypatch.setattr(
        "src.plugins.language.rerank_reply.build_prompt", fake_build_prompt
    )
    monkeypatch.setattr(
        "src.plugins.language.rerank_reply.RerankReply._invoke_llm",
        AsyncMock(return_value=RerankOutput(ranks=[1])),
    )
    await RerankReply.rank_and_select(100, ["a"])
    assert captured.get("group_name") == "上班摸鱼群"


@pytest.mark.asyncio
async def test_keyword_respond_filters_recent_duplicates(monkeypatch):
    """候选里与最近消息重复的文本被过滤，不喂给 rerank。"""
    monkeypatch.setattr(random, "random", lambda: 0.1)
    monkeypatch.setattr(
        "src.plugins.language.interact.RerankReplyConfig.get",
        AsyncMock(return_value=RerankReplyConfig(enabled=True)),
    )
    _patch_keyword_pipeline(monkeypatch, ["老毕进修去了", "别的话", "老毕消失好久了"])
    rank = AsyncMock(return_value=Message("别的话"))
    monkeypatch.setattr(
        "src.plugins.language.interact.RerankReply.rank_and_select", rank
    )
    messages = [
        _InteractMessage(True, Message("老毕进修去了")),
        _InteractMessage(True, Message("老毕消失好久了")),
    ]
    result = await RandomResponse.keyword_respond(100, messages)
    assert result is not None
    rank.assert_awaited_once_with(100, ["别的话"])


@pytest.mark.asyncio
async def test_keyword_respond_all_duplicates_returns_none(monkeypatch):
    """候选全部与最近消息重复 → 过滤后为空 → 不回复。"""
    monkeypatch.setattr(random, "random", lambda: 0.1)
    monkeypatch.setattr(
        "src.plugins.language.interact.RerankReplyConfig.get",
        AsyncMock(return_value=RerankReplyConfig(enabled=True)),
    )
    _patch_keyword_pipeline(monkeypatch, ["老毕进修去了"])
    rank = AsyncMock()
    monkeypatch.setattr(
        "src.plugins.language.interact.RerankReply.rank_and_select", rank
    )
    messages = [_InteractMessage(True, Message("老毕进修去了"))]
    result = await RandomResponse.keyword_respond(100, messages)
    assert result is None
    rank.assert_not_awaited()


class _FakeCursor:
    def __init__(self, entries):
        self._entries = entries

    async def to_list(self, length=None):
        return self._entries


@pytest.mark.asyncio
async def test_retrieve_rerank_candidates_excludes_and_caps(monkeypatch):
    """retrieve_rerank_candidates：宽松召回，排除近期复读，截断到 K。"""
    entries = [{"text": f"候选{i}", "keywords": {"k"}} for i in range(20)]
    fake_find = AsyncMock(return_value=_FakeCursor(entries))
    monkeypatch.setattr("src.plugins.language.rerank_reply.Corpus.find", fake_find)
    captured = {}

    def fake_search(query, corpus, corpus_kw, **kw):
        captured["threshold"] = kw.get("threshold")
        return [f"候选{i}" for i in range(20)]

    monkeypatch.setattr("src.plugins.language.rerank_reply.Keyword.search", fake_search)
    got = await retrieve_rerank_candidates(
        100, "query", ["老毕"], exclude={"候选1", "候选2"}, length=(6, 40)
    )
    assert "候选1" not in got and "候选2" not in got
    assert len(got) == 10  # 截断到 K=10
    assert captured["threshold"] == RERANK_SIM_THRESHOLD  # 宽松阈值
    # 检索用了更大样本
    assert fake_find.await_count == 1
    assert fake_find.await_args.kwargs["sample"] == RERANK_CORPUS_SAMPLES
    assert fake_find.await_args.kwargs["keywords"] == ["老毕"]
