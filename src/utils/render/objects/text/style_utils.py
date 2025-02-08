import re
from copy import deepcopy
from typing import Iterable, Mapping

from ...base.text import RenderText
from ...utils import Undefined, undefined
from .style import TextStyle


class TextStyleStack:
    """A stack of text styles for nested style scopes."""

    def __init__(self) -> None:
        self.stack: list[tuple[str, TextStyle]] = []

    def push(self, name: str, style: TextStyle) -> None:
        if type(style.size) is float:
            style = deepcopy(style)
            out = self.query()
            assert not isinstance(out.size, Undefined)
            assert not isinstance(style.size, Undefined)
            style.size = style.size * out.size
        self.stack.append((name, style))

    def pop(self, name: str) -> TextStyle:
        if not self.stack:
            raise ValueError(f"Expected tag: {name}")
        pop, style = self.stack.pop()
        if pop != name:
            raise ValueError(f"Unmatched tag: expected {pop}, got {name}")
        return style

    def query(self) -> TextStyle:
        """Get the style of the current scope.

        If a style is not defined in the current scope, it will be inherited
        from the outer scope.
        """
        style = TextStyle.of()
        for _, outer_style in reversed(self.stack):
            for k, v in outer_style.items():
                if not hasattr(style, k):
                    continue
                if getattr(style, k) is undefined:
                    setattr(style, k, v)
        return style


def _sub(text: str, repl: dict[str, str], reverse: bool = False) -> str:
    for k, v in repl.items():
        if reverse:
            k, v = v, k
        text = text.replace(k, v)
    return text


class TagParser:

    tag_begin = re.compile(r"<([a-zA-Z][\w\-\._]*)>")
    tag_end = re.compile(r"</([a-zA-Z][\w\-\._]*)>")
    tag_any = re.compile(r"</?([a-zA-Z][\w\-\._]*)>")

    escapes = {"&": "&amp;", "<": "&lt;", ">": "&gt;"}

    def __init__(self, text: str, styles: Mapping[str, TextStyle]) -> None:
        self.text = text
        self.styles = styles

    @classmethod
    def escape(cls, text):
        return "".join(cls.escapes.get(c, c) for c in text)

    @classmethod
    def unescape(cls, text):
        for k, v in cls.escapes.items():
            text = text.replace(v, k)
        return text

    def parse(self) -> Iterable[tuple[str, TextStyle]]:
        text = self.text
        styles = self.styles

        stack = TextStyleStack()
        stack.push("default", self.styles["default"])

        index = 0
        while index < len(text):
            # search for tag begin,
            # if found, push the style referenced by the tag
            match = self.tag_begin.match(text, index)
            if match:
                name = match.group(1)
                if name not in styles:
                    raise ValueError(f"Style used but not defined: {name}")
                stack.push(name, styles[name])
                index = match.end()
                continue
            # search for tag end,
            # if found, pop the style referenced by the tag
            match = self.tag_end.match(text, index)
            if match:
                name = match.group(1)
                try:
                    stack.pop(name)
                except ValueError as e:
                    raise ValueError(str(e) + " in " + repr(text)) from e
                index = match.end()
                continue
            # search for text from current index to next tag
            # next_tag = text.find("<", index)
            match = self.tag_any.search(text, index)
            next_tag = match.start() if match else -1
            if next_tag == -1:
                next_tag = len(text)
            plain_text = text[index:next_tag]
            if plain_text:
                before = plain_text
                plain_text = self.unescape(plain_text)
                yield plain_text, stack.query()
            index = next_tag

        if len(stack.stack) > 1:  # check if all tags are closed
            raise ValueError(f"Unclosed tag: {stack.stack[-1][0]}")


class LineBuffer:

    def __init__(self, max_width: int | None) -> None:
        self.max_width = max_width
        self.buffer: list[RenderText] = []

    def __bool__(self) -> bool:
        return bool(self.buffer)

    @property
    def remaining_width(self) -> int | None:
        if self.max_width is None:
            return None
        return self.max_width - sum(x.width for x in self.buffer)

    def append(self, text: RenderText) -> None:
        self.buffer.append(text)

    def flush(
        self,
        strip_trailing: bool = True,
        non_empty: bool = False,
    ) -> Iterable[list[RenderText]]:
        if strip_trailing and self.buffer:
            self.buffer[-1].text = self.buffer[-1].text.rstrip()
        if non_empty and not self.buffer:
            return
        yield self.buffer
        self.buffer.clear()
