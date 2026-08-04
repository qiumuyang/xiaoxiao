import functools
import operator
import random
import string
from collections.abc import Callable
from datetime import datetime
from unittest.mock import AsyncMock

import pytest
from nonebot.adapters.onebot.v11 import Message, MessageSegment

from src.ext import MessageExtension
from src.plugins.language.ask import Ask, Entry


def test_is_question():
    positive = [
        "问今天的天气怎么样？",
        "问什么是人工智能？",
        "问你昨天去了哪里？",
        "问为什么天会黑？",
        "问明天有什么计划",
        "问候车室里有多少人",
        "问路途还要多久",
        "问世界上有多少国家",
        "问下面有什么好吃的",
        "问一下雨就会发生什么",
        # "问起不起床",  # failed
    ]
    negative = [
        "问题的答案是什么",
        "问候语应该怎么写？",
        "问询处在什么地方",
        "问及问题的关键",
        "问问他什么时候回家",
        "问下他有没有空",
        "问一下就知道了",
    ]
    for s in positive:
        assert Ask.is_question(s)
    for s in negative:
        assert not Ask.is_question(s)


@pytest.mark.asyncio
async def test_ask_process():
    members = ["A", "B", "C", "DD"]

    def make_entries(*entries: str):
        return [
            Entry(
                group_id=0,
                created=datetime(2000, 1, 1),
                used=datetime(2000, 1, 1),
                text=e,
                length=len(e),
                keywords=set(),
            )
            for e in entries
        ]

    text = {
        length: [
            "".join(random.choices(string.ascii_lowercase, k=length)) for _ in range(10)
        ]
        for length in range(1, 11)
    }

    def mock_random_corpus_entry(length=None, *args, **kwargs):
        if length is not None:
            return make_entries(*text[length])
        return make_entries(*functools.reduce(operator.iadd, text.values(), []))

    async def test_once(
        question: str, replacement: bool, expected: Callable[[str], bool]
    ):
        ask = Ask(None, 119056244, None)  # type: ignore

        ask.random_corpus_entry = AsyncMock(side_effect=mock_random_corpus_entry)

        ask.replacement = False
        parts = []
        async for result in ask.process(question, members):
            parts.append(result)
        assert expected("".join(parts))
        assert replacement == ask.replacement

    await test_once(
        "你们吃什么2",
        True,
        lambda s: s.startswith("我们吃") and len(s) == 5 and s[-2:] in text[2],
    )
    await test_once(
        "今天星期几",
        True,
        lambda s: s.startswith("今天星期") and s[-1] in "一二三四五六天",
    )
    await test_once("谁", True, lambda s: s in [*members, "我", "你"])
    await test_once("为什么", True, lambda s: s.startswith("因为") and "所以" not in s)
    await test_once("为什么什么", True, lambda s: s.startswith("因为") and "所以" in s)
    await test_once("abcdef", False, lambda s: s == "abcdef")
    await test_once("\\什么什么3", True, lambda s: s[:2] == "什么" and s[2:] in text[3])
    await test_once("\\什么\\什么", False, lambda s: s == "什么什么")


def test_ask_preprocess():
    ask = Ask(None, 119056244, None)  # type: ignore

    def test_once(
        question: str,
        replacement: bool,
        expected: Callable[[str], bool],
    ):
        ask.replacement = False
        result = ask.preprocess_choice(question)
        assert expected(result), f"{question=}, {result=}"
        assert replacement == ask.replacement, (
            f"{question=}, {result=}, {ask.replacement=}"
        )

    test_once("XXYYZZ", False, lambda s: s == "XXYYZZ")
    test_once("问", False, lambda s: s == "问")
    test_once("还是还是还是", False, lambda s: s == "还是还是还是")
    for _ in range(10):
        test_once("A还是B", True, lambda s: s in ["A", "B"])
        test_once(
            "a还是b,\nc还是d", True, lambda s: s in ["a,\nc", "a,\nd", "b,\nc", "b,\nd"]
        )
        test_once(
            "XZC是/火还是水还是风还是雷还是水还是冰还是岩/属性角色",
            True,
            lambda s: (
                s
                in [
                    "XZC是/火/属性角色",
                    "XZC是/水/属性角色",
                    "XZC是/风/属性角色",
                    "XZC是/雷/属性角色",
                    "XZC是/冰/属性角色",
                    "XZC是/岩/属性角色",
                ]
            ),
        )
        test_once(
            r"问11:59之后是/12\:00还是00\:00",
            True,
            lambda s: s in [r"问11:59之后是/12\:00", r"问11:59之后是/00\:00"],
        )

    def preprocess(message: Message) -> Message:
        s, sym = MessageExtension.encode(message)
        s = ask.preprocess_choice(s)
        return MessageExtension.decode(s, sym)

    # more complex cases
    some_text = MessageSegment.text("一些文本")
    or_ = MessageSegment.text("还是")
    at = MessageSegment.at(123456)
    image = MessageSegment.image(file="file:///path/to/image.jpg")
    face = MessageSegment.face(11)
    complex1 = Message([at, or_, image, or_, face])
    complex2 = Message([some_text, image, some_text, or_, at, some_text])
    result1 = preprocess(complex1)
    assert ask.replacement
    assert result1 in [Message([at]), Message([image]), Message([face])]
    result2 = preprocess(complex2)
    assert ask.replacement
    assert result2 in [Message([some_text, image, some_text]), Message([at, some_text])]


@pytest.mark.asyncio
async def test_process_collect_who_as_pua():
    members = ["A", "B", "C"]
    ask = Ask(None, 119056244, None)  # type: ignore
    collect = {}
    ask.replacement = False
    parts = []
    async for result in ask.process("谁", members, collect_values=collect, pua_start=0):
        parts.append(result)
    encoded = "".join(parts)
    assert len(encoded) == 1
    assert encoded in collect
    assert collect[encoded][0] == "nickname"
    assert collect[encoded][1] in ["A", "B", "C"]


@pytest.mark.asyncio
async def test_process_collect_pua_offset():
    members = ["A", "B", "C"]
    ask = Ask(None, 119056244, None)  # type: ignore
    collect = {}
    ask.replacement = False
    parts = []
    async for result in ask.process("谁", members, collect_values=collect, pua_start=1):
        parts.append(result)
    encoded = "".join(parts)
    assert encoded == "\ue001"


@pytest.mark.asyncio
async def test_process_collect_slot_survives():
    members = ["A", "B", "C"]
    ask = Ask(None, 119056244, None)  # type: ignore
    collect = {}
    ask.replacement = False
    parts = []
    async for result in ask.process(
        "谁吃\x000\x00", members, collect_values=collect, pua_start=0
    ):
        parts.append(result)
    encoded = "".join(parts)
    assert encoded.startswith("\ue000")
    assert "\x000\x00" in encoded
    assert "\ue000" in collect


@pytest.mark.asyncio
async def test_process_collect_no_escape_regression():
    """collect 模式下 谁 的值不经过 output()，含数字的昵称不被 escape。"""
    members = ["小明2"]
    ask = Ask(None, 119056244, None)  # type: ignore
    collect = {}
    ask.replacement = False
    parts = []
    async for result in ask.process("谁", members, collect_values=collect, pua_start=0):
        parts.append(result)
    encoded = "".join(parts)
    assert encoded == "\ue000"  # PUA 定长
    assert collect[encoded][1] == "小明2"  # 真实值未被 escape


@pytest.mark.asyncio
async def test_process_collect_how_much_as_pua():
    """collect 模式下 多少 → PUA（number 类型）。"""
    members = ["A", "B", "C"]
    ask = Ask(None, 119056244, None)  # type: ignore
    collect = {}
    ask.replacement = False
    parts = []
    async for result in ask.process(
        "多少", members, collect_values=collect, pua_start=0
    ):
        parts.append(result)
    encoded = "".join(parts)
    assert encoded in collect
    assert collect[encoded][0] == "number"


@pytest.mark.asyncio
async def test_process_collect_multi_values():
    """collect 模式多个非 LLM 点：PUA 序号连续。"""
    members = ["A", "B", "C"]
    ask = Ask(None, 119056244, None)  # type: ignore
    collect = {}
    ask.replacement = False
    parts = []
    async for result in ask.process(
        "谁和谁", members, collect_values=collect, pua_start=0
    ):
        parts.append(result)
    encoded = "".join(parts)
    assert len(collect) == 2
    assert "\ue000" in encoded and "\ue001" in encoded
    assert collect["\ue000"][0] == "nickname"
    assert collect["\ue001"][0] == "nickname"


@pytest.mark.asyncio
async def test_process_no_collect_still_plain():
    """无 collect_values 时 谁 保持裸输出（不 escape）。"""
    members = ["小明2"]
    ask = Ask(None, 119056244, None)  # type: ignore
    ask.replacement = False
    parts = []
    async for result in ask.process("谁", members):
        parts.append(result)
    assert "".join(parts) == "小明2"  # 不经 escape


@pytest.mark.asyncio
async def test_answer_finalize_at_segment(monkeypatch):
    """_finalize 还原 at 段（现有 decode 逻辑复用）。"""
    from unittest.mock import AsyncMock

    from src.plugins.language import ask as ask_mod

    monkeypatch.setattr(
        ask_mod, "get_group_member_name", AsyncMock(return_value="张三")
    )
    ask = Ask(None, 119056244, None)  # type: ignore
    symtab = {"\ue000": MessageSegment.at(123456)}
    msg = await ask._finalize("hi\ue000", symtab, 119056244)
    assert msg is not None
    assert msg[1].type == "at"


@pytest.mark.asyncio
async def test_answer_finalize_awaited(monkeypatch):
    """answer() 返回 Message 而非未 await 的协程。"""
    from src.plugins.language import ask as ask_mod

    ask = Ask(None, 119056244, None)  # type: ignore
    ask.question = Message("问谁")
    monkeypatch.setattr(ask_mod, "list_group_member_names", AsyncMock(return_value=[]))
    result = await ask.answer()
    assert isinstance(result, Message)
    assert result in [Message("你"), Message("我")]
