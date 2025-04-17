import re
from dataclasses import dataclass


@dataclass(slots=True)
class MarkupNode:
    pass


@dataclass(slots=True)
class MarkupText(MarkupNode):
    content: str


@dataclass(slots=True)
class MarkupImage(MarkupNode):
    name: str
    inline: bool = False


@dataclass(slots=True)
class MarkupElement(MarkupNode):
    # Note: be careful with children [] vs None
    # the semantics are different: None for self-closing tag
    tag: str
    children: list[MarkupNode]


class MarkupSyntaxError(ValueError):

    def __init__(self, message: str, markup: str, pos: int) -> None:
        self.markup = markup
        self.pos = pos
        self.message = message

    def __str__(self) -> str:
        info = f"{self.__class__.__name__}: {self.message}"
        detail = f"{self.markup}\n{' ' * self.pos}^"
        return f"{info}\n{detail}"


class MarkupParser:

    # group 1: optional closing tag
    # group 2: tag name (alphanumeric) with optional :modifier
    # group 3: optional self-closing tag
    TAG_PATTERN = re.compile(r"<(/)?([a-zA-Z][\w\-\._]*(?::[\w\-]+)?)(/?)>")

    ESCAPE_TABLE = {"&": "&amp;", "<": "&lt;", ">": "&gt;"}

    @classmethod
    def escape(cls, text: str) -> str:
        return "".join(cls.ESCAPE_TABLE.get(c, c) for c in text)

    @classmethod
    def unescape(cls, text: str) -> str:
        for k, v in cls.ESCAPE_TABLE.items():
            text = text.replace(v, k)
        return text

    def __init__(self, markup: str) -> None:
        self.markup = markup
        self.index = 0

    def parse(self) -> list[MarkupNode]:
        self.index = 0
        return self._parse_nodes()

    def _parse_nodes(self, stop_tag: str = "") -> list[MarkupNode]:
        nodes = []
        while self.index < len(self.markup):
            if self.markup[self.index] == "<":
                match = self.TAG_PATTERN.match(self.markup, self.index)
                if match:
                    is_closing = bool(match.group(1))
                    tag_name = match.group(2)
                    is_self_closing = bool(match.group(3))
                    # Check invalid tags
                    if is_closing and is_self_closing:
                        raise MarkupSyntaxError(
                            "Tag cannot be both closing and self-closing",
                            match.group(0), 1)
                    if is_closing and tag_name != stop_tag:
                        raise MarkupSyntaxError(
                            f"Unexpected closing tag: {tag_name} != {stop_tag}",
                            match.group(0), 1)
                    self.index = match.end()
                    if is_closing:
                        return nodes
                    if is_self_closing:
                        if ":" in tag_name:
                            tag_name, modifier = tag_name.split(":", 1)
                        else:
                            tag_name, modifier = tag_name, ""
                        nodes.append(
                            MarkupImage(tag_name, inline=modifier == "inline"))
                    else:
                        children = self._parse_nodes(tag_name)
                        nodes.append(MarkupElement(tag_name, children))
                    continue
            first = self.markup[self.index]
            text = self._consume_until("<", skip=1)
            nodes.append(MarkupText(first + text))

        if stop_tag:
            _truncate = 20
            text = self.markup[self.index - _truncate:self.index + _truncate]
            raise MarkupSyntaxError(f"Unclosed tag: {stop_tag}", text,
                                    _truncate)
        return nodes

    def _consume_until(self, char: str, skip: int = 0) -> str:
        start = self.index + skip
        pos = self.markup.find(char, start)
        if pos == -1:
            self.index = len(self.markup)
            return self.markup[start:]
        self.index = pos
        return self.markup[start:pos]
