import random
import string
import time

import pytest

from src.plugins.idiom.data import Diff, Idiom
from src.plugins.idiom.guess.game import RenderAttemptData, Status
from src.plugins.idiom.guess.render import GuessRender


def test_idiom_syllable():
    assert not Idiom.is_syllable("pia")
    assert not Idiom.is_syllable("kei")

    syllables = [
        ["xian", "lai", "hou", "dao"],
        ["xi'", "an", "rou", "jia", "mo"],
        ["guang", "er", "gao", "zhi"],
        ["zhu", "ni", "sheng", "ri", "kuai", "le"],
    ]
    for case in syllables:
        input0 = "".join(case)
        input1 = " ".join(case)
        expect = tuple(s.replace("'", "") for s in case)
        output0 = Idiom.parse_syllables(input0)
        output1 = Idiom.parse_syllables(input1)
        assert expect in (output0 or [])
        assert expect in (output1 or [])
    assert Idiom.parse_syllables("xiao") == [("xiao", ), ("xi", "ao"),
                                             ("xia", "o"), ("xi", "a", "o")]


def test_idiom_diff():
    N, Y, E = Diff.MISS, Diff.EXACT, Diff.EXIST
    t = "abcbc"
    p = "bbbcx"
    assert Idiom.diff(t, p) == [E, Y, N, E, N]
    t = [1, 2, 3, 4, 5]
    p = [5, 4, 3, 3, 5]
    assert Idiom.diff(t, p) == [N, E, Y, N, Y]
    assert Idiom.diff("", "") == []
    t = [0, 0, 0, 0, 0]
    p = [1, 1, 1, 1, 1]
    assert Idiom.diff(t, p) == [N, N, N, N, N]
    t = [1, 1, 1, 1, 1]
    p = [1, 1, 1, 1, 1]
    assert Idiom.diff(t, p) == [Y, Y, Y, Y, Y]
    t = [1, 2, 3, 4, 5]
    p = [5, 1, 2, 3, 4]
    assert Idiom.diff(t, p) == [E, E, E, E, E]


@pytest.mark.asyncio
async def test_idiom_render():
    target = "xianlaihoudao"
    attempts = []
    for _ in range(4):
        provided = "".join(
            random.choices(string.ascii_lowercase, k=len(target)))
        diff = Idiom.diff(target, provided)
        attempts.append(
            RenderAttemptData(
                user_id=0,
                syllables=[
                    provided[0:4], provided[4:7], provided[7:10], provided[10:]
                ],
                diffs=diff,
            ))
    start = time.time()
    obj = await GuessRender.render(attempts, [4, 3, 3, 3],
                                   key_state={"a": Status.EXACT},
                                   answer=None)
    im = obj.render()
    end = time.time()
    assert end - start < 0.2
    im.save("idiom_render.png")
