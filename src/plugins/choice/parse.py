import re
import shlex
from enum import Enum
from typing import Literal, NamedTuple

escape = re.compile(r"\\(.)|&")
escape_table = {"&": "&amp;", "[": "&#91;", "]": "&#93;"}


def repl(m: re.Match[str]) -> str:
    if m.group(0) == "&":
        return "&amp;"
    return escape_table.get(m.group(1), m.group(1))


def unescape(s: str) -> str:
    for k, v in escape_table.items():
        s = s.replace(v, k)
    return s


class Op(Enum):
    ADD = "+"
    REMOVE = "-"
    SHOW = "?"
    TOGGLE = "*"
    NONE = ""


class ItemAction(NamedTuple):
    op: Op
    content: str
    type: Literal["message", "reference"]

    def with_content(self, content: str):
        return ItemAction(self.op, content, self.type)


class Action(NamedTuple):
    op: Op
    name: str
    items: list[ItemAction]


def parse_action(text: str) -> Action | None:
    items: list[ItemAction] = []
    lexer = shlex.shlex(text, posix=True)
    lexer.escape = ""
    lexer.whitespace_split = True
    lexer.commenters = ""
    for i, arg in enumerate(lexer):
        for op in Op:
            if arg.startswith(op.value):
                name = arg[len(op.value):]
                break
        else:
            assert False, "should not reach here"
        name = escape.sub(repl, name)
        if i > 0 and name.startswith("[") and name.endswith("]"):
            name = name[1:-1]
            type_ = "reference"
        else:
            type_ = "message"
        name = unescape(name)
        items.append(ItemAction(op, name, type_))
    if not items:
        return None
    return Action(items[0].op, items[0].content, items[1:])


if __name__ == "__main__":
    print(parse_action('\\-b "+a b" -c'))
    print(parse_action("-a+b-c?"))
    print(parse_action("a +b -c?"))
    print(parse_action("a +[b]"))
    print(parse_action("[a] +b&c"))
    print(parse_action("a +\\[b\\] -c"))
