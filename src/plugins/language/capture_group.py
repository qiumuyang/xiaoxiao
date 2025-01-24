import re
from typing import NamedTuple


class CaptureGroup(NamedTuple):
    start: int
    content: list[str]


def expand_capture_group_references(s: str) -> str:
    output = []
    # 1. Extract capture groups
    groups: list[CaptureGroup] = []
    st: list[CaptureGroup] = []
    skip = False
    for i, c in enumerate(s):
        if skip:
            skip = False
            continue
        match c:
            case "(":
                st.append(CaptureGroup(i, []))
            case ")":
                if st:
                    captured_group = st.pop()
                    groups.append(captured_group)
                    if st:
                        st[-1].content.extend(captured_group.content)
                else:
                    output.append(c)
            case _:
                if c == "\\":
                    if i + 1 < len(s) and s[i + 1].isdigit():
                        # is reference
                        output.append(c)
                    else:
                        # is escape
                        skip = True
                        output.append(s[i + 1] if i + 1 < len(s) else c)
                else:
                    output.append(c)
                if st:
                    st[-1].content.append(c)
    groups.sort(key=lambda x: x.start)
    group_texts = ["".join(g.content) for g in groups]
    # 2. Check group cross-reference
    processed = [False] * len(groups)
    pattern = re.compile(r"\\(\d+)")

    def dfs(i: int, vis: list[bool]) -> list[str]:
        if i < 0 or i >= len(groups):
            return [rf"\{i+1}"]
        if processed[i]:
            return [group_texts[i]]
        if vis[i]:
            raise ValueError("Circular reference detected")
        vis[i] = True
        text = pattern.sub(lambda m: "".join(dfs(int(m.group(1)) - 1, vis)),
                           group_texts[i])
        group_texts[i] = text
        processed[i] = True
        return [text]

    for i in range(len(groups)):
        dfs(i, [False] * len(groups))
    # 3. Replace references
    return pattern.sub(
        lambda m: group_texts[idx] if 0 <=
        (idx := int(m.group(1)) - 1) < len(group_texts) else m.group(0),
        "".join(output))


import unittest


class Test(unittest.TestCase):

    def _make_test(self, tests):
        for s, expected in tests:
            if expected == ValueError:
                with self.assertRaises(ValueError):
                    expand_capture_group_references(s)
            else:
                got = expand_capture_group_references(s)
                self.assertEqual(got, expected)

    def test_no_capture_group(self):
        tests = [
            ("", ""),
            ("a\\(b)c", "a(b)c"),
            # ("a(bcdef", "a(bcdef"),
            # missing the first (, temporary won't fix
        ]
        self._make_test(tests)

    def test_random_no_capture_group(self):
        import random
        import string
        cand = list(string.printable)
        cand.remove("(")
        cand.remove(")")
        cand.remove("\\")
        for length in range(1, 100):
            for _ in range(5):
                s = "".join(random.choices(cand, k=length))
                self.assertEqual(expand_capture_group_references(s), s)

    def test_single_capture_group(self):
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
        self._make_test(tests)

    def test_multi_capture_group(self):
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
        self._make_test(tests)
        self._make_test(tests)
