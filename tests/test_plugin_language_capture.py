import pytest

from src.plugins.language.capture_group import expand_capture_group_references


def run_tests(tests):
    for s, expected in tests:
        if expected is ValueError:
            with pytest.raises(ValueError):
                expand_capture_group_references(s)
        else:
            assert expand_capture_group_references(s) == expected


def test_no_capture_group():
    tests = [
        ("", ""),
        ("a\\(b)c", "a(b)c"),
    ]
    run_tests(tests)


def test_random_no_capture_group():
    import random
    import string
    cand = list(string.printable)
    cand.remove("(")
    cand.remove(")")
    cand.remove("\\")
    for length in range(1, 100):
        for _ in range(5):
            s = "".join(random.choices(cand, k=length))
            assert expand_capture_group_references(s) == s


def test_single_capture_group():
    tests = [
        ("a(b)c", "abc"),
        ("a(b)c\\1", "abcb"),
        ("(a bc) ", "a bc "),
        ("abc() ", "abc "),
        ("()abc \\1", "abc "),
        ("(ab)c \\2", "abc \\2"),
        ("(a\\1)b", ValueError),
        ("(\\1)b", ValueError),
    ]
    run_tests(tests)


def test_multi_capture_group():
    tests = [
        ("a((b)c(d))e(f)g", "abcdefg"),
        ("(Hello (world))\\1\\2 \\2", "Hello worldHello worldworld world"),
        ("(a(b(c(d)))) \\4 \\3 \\2 \\1", "abcd d cd bcd abcd"),
        ("(a)(b)c(d)(e)(f)\\1\\2\\3\\4\\5", "abcdefabdef"),
        ("(ab \\2 de \\3 gh)(cd)(fg)", "ab cd de fg ghcdfg"),
        ("He says: (Bye, \\2). (John) says: he said \\1",
         "He says: Bye, John. John says: he said Bye, John"),
        ("(\\2)(\\3)(\\4)(\\5)(\\6)(\\1)", ValueError),
    ]
    run_tests(tests)
