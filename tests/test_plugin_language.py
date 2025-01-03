import random
import string
from datetime import datetime
from typing import Callable
from unittest.mock import AsyncMock

import pytest
from nonebot.adapters.onebot.v11 import Message

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
            Entry(group_id=0,
                  created=datetime(2000, 1, 1),
                  used=datetime(2000, 1, 1),
                  text=e,
                  length=len(e),
                  keywords=set()) for e in entries
        ]

    text = {
        length: [
            "".join(random.choices(string.ascii_lowercase, k=length))
            for _ in range(10)
        ]
        for length in range(1, 11)
    }

    def mock_random_corpus_entry(length=None, *args, **kwargs):
        if length is not None:
            return make_entries(*text[length])
        return make_entries(*sum(text.values(), []))

    async def test_once(question: str, replacement: bool,
                        expected: Callable[[str], bool]):
        ask = Ask(None, 119056244, None)  # type: ignore

        ask.random_corpus_entry = AsyncMock(
            side_effect=mock_random_corpus_entry)

        ask.replacement = False
        parts = []
        async for result in ask.process(question, members):
            parts.append(result)
        assert expected("".join(parts))
        assert replacement == ask.replacement

    await test_once(
        "你们吃什么2", True,
        lambda s: s.startswith("我们吃") and len(s) == 5 and s[-2:] in text[2])
    await test_once("今天星期几", True,
                    lambda s: s.startswith("今天星期") and s[-1] in "一二三四五六天")
    await test_once("谁", True, lambda s: s in members + ["我", "你"])
    await test_once("为什么", True,
                    lambda s: s.startswith("因为") and "所以" not in s)
    await test_once("为什么什么", True, lambda s: s.startswith("因为") and "所以" in s)
    await test_once("abcdef", False, lambda s: s == "abcdef")


def test_ask_preprocess():
    ask = Ask(None, 119056244, None)  # type: ignore

    def test_once(
        question: str,
        replacement: bool,
        expected: Callable[[str], bool],
    ):
        result = ask.preprocess_choice(Message(question)).extract_plain_text()
        assert expected(result)
        assert replacement == ask.replacement, \
                f"{question=}, {result=}, {ask.replacement=}"

    test_once("问A还是B", True, lambda s: s in ["问A", "问B"])
    test_once("问XXYYZZ", False, lambda s: s == "问XXYYZZ")
    test_once("问", False, lambda s: s == "问")
    test_once("问还是还是还是", False, lambda s: s == "问")
