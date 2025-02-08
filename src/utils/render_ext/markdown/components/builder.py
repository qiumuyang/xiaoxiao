import random
import re
import string

from typing_extensions import Unpack

from src.utils.render import (Alignment, BaseStyle, Container, Direction,
                              RenderObject, Spacer, StyledText, TextStyle)

from ..style import OverrideStyle


def rand_str(length: int = 4) -> str:

    return "".join(random.choices(string.ascii_lowercase, k=length))


def deduplicate(name: str, existing: set[str]) -> str:
    new_name = name
    while new_name in existing:
        new_name = name + rand_str()
    return new_name


class Builder:

    _styles: dict[str, TextStyle]
    _content: str

    def __init__(self, default: TextStyle, no_override: bool = False) -> None:
        self._styles = {}
        self._content = ""
        self._default = default
        self.no_override = no_override

    def text(self, content: str):
        self._content += StyledText.escape(content)

    def style(self, name: str, style: TextStyle | None, dedup: bool = True):
        style = style or self._default
        if dedup:
            name = deduplicate(name, set(self._styles.keys()))
        self._styles[name] = style
        return self.StyleContext(self, name)

    @property
    def content(self):
        return self._content

    @property
    def raw_content(self):
        return re.sub(r"<[^>]*>", "", self._content)

    @property
    def styles(self):
        if self.no_override:
            return self._styles
        if isinstance(self._default, OverrideStyle):
            if self._default.foreground_color:
                return {
                    k: v.with_color(self._default.foreground_color)
                    for k, v in self._styles.items()
                }
        return self._styles

    def build(self,
              *,
              max_width: int | None = None,
              spacing: int = 0,
              **kwargs: Unpack[BaseStyle]) -> RenderObject:
        return StyledText.of(self.content,
                             styles=self.styles,
                             default=self._default,
                             max_width=max_width,
                             line_spacing=spacing,
                             **kwargs)

    class StyleContext:

        def __init__(self, constructor: "Builder", name: str):
            self.constructor = constructor
            self.name = name

        def __enter__(self):
            self.constructor._content += f"<{self.name}>"

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.constructor._content += f"</{self.name}>"


class Box:
    """
    Creates a box that contains a RenderObject with specified size.
    """

    def __init__(self,
                 obj: RenderObject,
                 width: int | None = None,
                 height: int | None = None,
                 alignment_vertical: Alignment = Alignment.CENTER,
                 alignment_horizontal: Alignment = Alignment.START) -> None:
        self.obj = obj
        self.width = width
        self.height = height
        self.alignment_vertical = alignment_vertical
        self.alignment_horizontal = alignment_horizontal

    def build(self, **kwargs: Unpack[BaseStyle]) -> RenderObject:
        width = self.width or self.obj.width
        height = self.height or self.obj.height
        match self.alignment_vertical:
            case Alignment.START:
                y = 0
            case Alignment.CENTER:
                y = (height - self.obj.height) // 2
            case Alignment.END:
                y = height - self.obj.height
        return Container.from_children(
            [
                Spacer.of(width=width, height=y),
                self.obj,
                Spacer.of(height=height - y - self.obj.height),
            ],
            alignment=self.alignment_horizontal,
            direction=Direction.VERTICAL,
            **kwargs,
        )
