import random
import re
import string
from typing import cast

from typing_extensions import Unpack

from src.utils.render import (Alignment, BaseStyle, Container, Direction,
                              Paragraph, RenderImage, RenderObject, Spacer,
                              TextStyle)

from ...style import OverrideStyle


def rand_str(length: int = 4) -> str:
    return "".join(random.choices(string.ascii_lowercase, k=length))


def deduplicate(name: str, existing: set[str]) -> str:
    new_name = name
    while new_name in existing:
        new_name = name + rand_str()
    return new_name


class Multiline:

    def __init__(self):
        self.text = ""
        self.newline = False

    def append(self, text: str, inline: bool):
        if self.newline or not inline:
            if self.text:
                self.text += "\n"
            self.newline = False
        self.text += text
        if not inline:
            self.newline = True

    def append_tag_begin(self, tag: str, inline: bool):
        self.append(f"<{tag}>", inline)

    def append_tag_end(self, tag: str, inline: bool):
        self.append(f"</{tag}>", inline)

    def append_self_closing_tag(self, tag: str, inline: bool):
        mod = ":inline" if inline else ""
        self.append(f"<{tag}{mod}/>", True)


class Builder:

    _styles: dict[str, TextStyle]
    _images: dict[str, RenderObject | RenderImage]
    _content: Multiline

    def __init__(self,
                 default: TextStyle,
                 max_width: int | None = None,
                 allow_override: bool = True) -> None:
        self._styles = {}
        self._images = {}
        self._content = Multiline()
        self._default = default
        self.max_width = max_width
        self.allow_override = allow_override

    def text(self, content: str, inline: bool = True):
        self._content.append(Paragraph.formatter.escape(content), inline)

    def image(self,
              image: RenderObject | RenderImage,
              tag: str = "img_",
              inline: bool = False):
        tag = deduplicate(tag, set(self._images.keys()))
        self._images[tag] = image
        self._content.append_self_closing_tag(tag, inline)

    def style(self, tag: str, style: TextStyle | None, dedup: bool = True):
        style = style or self._default
        if dedup:
            tag = deduplicate(tag, set(self._styles.keys()))
        self._styles[tag] = style
        return self.StyleContext(self, tag)

    @property
    def content(self) -> str:
        return self._content.text

    @property
    def raw_content(self) -> str:
        return re.sub(r"<[^>]*>", "", self._content.text)

    @property
    def styles(self):
        if not self.allow_override:
            return {
                k:
                v if not OverrideStyle.isinstance(v) else
                OverrideStyle.to_normal(v)
                for k, v in self._styles.items()
            }
        if OverrideStyle.isinstance(self._default):
            fg = cast(OverrideStyle, self._default)["foreground_color"]
            return {
                k: OverrideStyle.to_normal(v) | TextStyle(color=fg)
                for k, v in self._styles.items()
            }
        return self._styles

    @property
    def default(self):
        return OverrideStyle.to_normal(self._default)

    def build(self,
              *,
              max_width: int | None = None,
              spacing: int = 0,
              **kwargs: Unpack[BaseStyle]) -> RenderObject:
        return Paragraph.from_markup(self.content,
                                     default=self.default,
                                     styles=self.styles,
                                     images=self._images,
                                     max_width=max_width or self.max_width,
                                     line_spacing=spacing,
                                     **kwargs)

    class StyleContext:

        def __init__(self, constructor: "Builder", tag: str):
            self.constructor = constructor
            self.name = tag

        def __enter__(self):
            self.constructor._content.append_tag_begin(self.name, inline=True)

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.constructor._content.append_tag_end(self.name, inline=True)


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
