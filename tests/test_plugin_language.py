import asyncio
from datetime import datetime

import pytest
from nonebot.adapters.onebot.v11 import Bot, Message, MessageSegment
from nonebot.exception import MockApiException

from src.plugins.language.ask import Ask, CorpusFilter
from src.utils.message import ReceivedMessageTracker


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
async def test_answer():

    names = ["AAA", "BB", "c"]
    group_member = [{"card": x, "nickname": x} for x in names]
    group_id = 123456

    @Bot.on_calling_api  # type: ignore
    async def mock(bot: Bot, api: str, data: dict):
        assert api == "get_group_member_list"
        assert data["group_id"] == group_id
        raise MockApiException(result=group_member)

    reasons = ["天气很好", "天气很差", "好吃"]
    reason_tails = ["，所以", "。因此"]

    messages = []
    for reason in reasons:
        for reason_tail in reason_tails:
            messages.append(f"因为{reason}{reason_tail}")

    messages.append("Handled")

    normal_time = datetime.now() - CorpusFilter.MIN_INTERVAL
    ReceivedMessageTracker.received = {
        group_id: {
            i: {
                "content": Message(MessageSegment.text(text)),
                "handled": text == "Handled",
                "time": normal_time
            }
            for i, text in enumerate(messages)
        }
    }

    bot = Bot(None, "")  # type: ignore

    async def answer(question: str) -> str | None:
        return await Ask(bot, group_id, question).answer()

    ret = await answer("问你")
    assert ret is None
    results = await asyncio.gather(*[answer("问谁") for _ in range(10)])
    assert all(x in names + ["你", "我"] for x in results)

    for _ in range(10):
        ret = await answer("问什么")
        assert ret
        assert ret in messages
        assert ret != "Handled"

    ret = await answer("问为什么")
    assert ret
    assert ret.startswith("因为") and not ret.endswith("所以")

    ret = await answer("问为什么你")
    assert ret
    because, result = ret.split("，")
    assert because.startswith("因为")
    assert because.removeprefix("因为") in reasons
    assert result == "所以我"

    assert await answer("问有没有") in ["有", "没有"]
    assert await answer("问是不是") in ["是", "不是"]
    assert await answer("问看不看得见") in ["看得见", "看不见"]
