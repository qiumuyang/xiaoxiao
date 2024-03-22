from src.plugins.idiom.data import Diff, Idiom


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
