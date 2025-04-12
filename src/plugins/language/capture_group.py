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
                    if i + 1 < len(s) and s[i + 1].isdecimal():
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
