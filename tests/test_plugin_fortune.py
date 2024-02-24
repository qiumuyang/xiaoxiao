import asyncio
import random
import string
from datetime import datetime

import pytest

from src.plugins.fortune.fortune import EVENT, get_fortune, get_seed
from src.plugins.fortune.render import FortuneRender


def test_seed():
    s1 = get_seed(12345, "2021-01-01")
    s2 = get_seed(12345, "2021-01-01")
    s3 = get_seed(12345, "2021-01-02")
    assert s1 == s2
    assert s1 != s3


def test_fortune():
    uid = 12345
    name = "test"
    for _ in range(100):
        year1 = random.randint(2000, 2020)
        year2 = random.randint(2000, 2020)
        f1 = get_fortune(uid, name, datetime(year1, 1, 1))
        f2 = get_fortune(uid, name, datetime(year2, 1, 1))
        if year1 == year2:
            assert f1 == f2
        else:
            assert f1 != f2
        assert len(set(f1["event_good"] + f1["event_bad"])) == 6
        assert len(set(f2["event_good"] + f2["event_bad"])) == 6


@pytest.mark.asyncio
async def test_fortune_render_fuzzy():
    max_len = 50
    coros = []
    for l in range(1, min(max_len, len(string.printable)), 2):
        name = string.printable[:l]
        uid = random.randint(1000000000, 10000000000)
        date = datetime(year=random.randint(2000, 2020),
                        month=random.randint(1, 12),
                        day=random.randint(1, 28)).strftime("%Y-%m-%d")
        good: list[str] = random.sample(EVENT, 3)
        bad: list[str] = random.sample(EVENT, 3)
        coro = FortuneRender.render({
            "user_id": uid,
            "user_name": name,
            "date": date,
            "event_good": good,
            "event_bad": bad,
            "fortune": "大吉",
            "lucky_color": (255, 255, 255),
        })
        coros.append(coro)

    await asyncio.gather(*coros)
