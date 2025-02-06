from __future__ import annotations

import re
from copy import deepcopy
from typing import Generator, Iterable

from PIL import ImageFont
from typing_extensions import Self, Unpack, override

from ...base import (Alignment, BaseStyle, Palette, RenderImage, RenderObject,
                     RenderText, TextDecoration, cached, volatile)
from ...utils import Undefined, undefined
from .style import FontFamily, TextStyle
from .text import Text


class NestedTextStyle:
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
                if getattr(style, k) is undefined:
                    setattr(style, k, v)
        return style


class StyledText(RenderObject):
    """A text object with multiple styles."""

    tag_begin = re.compile(r"<(\w+)>")
    tag_end = re.compile(r"</(\w+)>")
    tag_any = re.compile(r"</?(\w+)>")

    def __init__(
        self,
        text: str,
        styles: dict[str, TextStyle],
        max_width: int | None,
        alignment: Alignment,
        line_spacing: int,
        **kwargs: Unpack[BaseStyle],
    ) -> None:
        super().__init__(**kwargs)

        with volatile(self) as vlt:
            self.text = text
            self.styles = vlt.dict(styles)
            self.alignment = alignment
            self.line_spacing = line_spacing
            self.max_width = max_width

    @property
    @cached
    @override
    def content_width(self) -> int:
        return self.render_content().width

    @property
    @cached
    @override
    def content_height(self) -> int:
        return self.render_content().height

    @override
    def render_content(self) -> RenderImage:
        rendered_lines: list[RenderImage] = []
        for line in self.cut():
            if line:
                rendered_lines.append(self.text_concat(line))
        return RenderImage.concat_vertical(
            rendered_lines,
            alignment=self.alignment,
            spacing=self.line_spacing,
        )

    def _cut_blocks(self) -> Generator[tuple[str, TextStyle], None, None]:
        text = self.text
        styles = self.styles

        style = NestedTextStyle()
        style.push("default", self.styles["default"])

        index = 0
        while index < len(text):
            # search for tag begin,
            # if found, push the style referenced by the tag
            match = self.tag_begin.match(text, index)
            if match:
                name = match.group(1)
                if name not in styles:
                    raise ValueError(f"Style used but not defined: {name}")
                style.push(name, styles[name])
                index = match.end()
                continue
            # search for tag end,
            # if found, pop the style referenced by the tag
            match = self.tag_end.match(text, index)
            if match:
                name = match.group(1)
                try:
                    style.pop(name)
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
                yield plain_text, style.query()
            index = next_tag

        if len(style.stack) > 1:  # check if all tags are closed
            raise ValueError(f"Unclosed tag: {style.stack[-1][0]}")

    def cut(self) -> Generator[list[RenderText], None, None]:
        """Cut the text into lines. Each line is a list of RenderTexts."""

        def current_width() -> int | None:
            """Return the current acceptable width of the line."""
            if max_width is None:
                return None
            return max_width - sum(t.width for t in line_buffer)

        def flush(
            buffer: list[RenderText]
        ) -> Generator[list[RenderText], None, None]:
            """Yield the current line and clear the buffer."""
            if buffer:
                buffer[-1].text = buffer[-1].text.rstrip(" ")
            yield buffer
            buffer.clear()

        max_width = self.max_width
        blocks = self._cut_blocks()
        line_buffer: list[RenderText] = []
        for block, style in blocks:
            # load style properties
            font_size = Undefined.default(style.size, 0)
            font_size = round(font_size)
            italic = Undefined.default(style.italic, False)
            bold = Undefined.default(style.bold, False)
            pseudo_italic = False
            if isinstance(style.font, Undefined):
                font_path = ""
            elif isinstance(style.font, FontFamily):
                font_path, pseudo_italic = style.font.select(bold, italic)
            else:
                font_path = Undefined.default(str(style.font), "")
                pseudo_italic = italic
                if bold:
                    raise ValueError("Font family required for bold")
            if font_path:
                font = ImageFont.truetype(font_path, font_size)
            else:
                font = ImageFont.load_default()
            color = Undefined.default(style.color, None)
            stroke_width = Undefined.default(style.stroke_width, 0)
            stroke_color = Undefined.default(style.stroke_color, None)
            hyphenation = Undefined.default(style.hyphenation, True)
            decoration = Undefined.default(style.decoration,
                                           TextDecoration.NONE)
            thick = Undefined.default(style.decoration_thickness, -1)
            shading = Undefined.default(style.shading, None)
            embedded_color = Undefined.default(style.embedded_color, False)
            ymin_correction = Undefined.default(style.ymin_correction, False)

            line_break_at_end = block.endswith('\n')
            lines = block.split('\n')
            for lineno, line in enumerate(lines):
                while line:
                    # check font here instead of nest-parse stage
                    # so default style can leave font undefined if not used
                    if not isinstance(font, ImageFont.FreeTypeFont):
                        raise ValueError("Font required")
                    if not font_path:
                        raise ValueError("Font required")
                    try:
                        split, remain, bad = Text.split_once(
                            font,
                            line,
                            stroke_width=stroke_width,
                            max_width=current_width(),
                            hyphenation=hyphenation,
                            italic=pseudo_italic)
                    except ValueError:
                        # too long to fit, flush the line and try again
                        yield from flush(line_buffer)
                        split, remain, bad = Text.split_once(
                            font,
                            line,
                            stroke_width=stroke_width,
                            max_width=current_width(),
                            hyphenation=hyphenation,
                            italic=pseudo_italic)
                    if line_buffer and bad:
                        # flush the line and try again
                        yield from flush(line_buffer)
                        split, remain, _ = Text.split_once(
                            font,
                            line,
                            stroke_width=stroke_width,
                            max_width=current_width(),
                            hyphenation=hyphenation,
                            italic=pseudo_italic)
                    line_buffer.append(
                        RenderText.of(
                            split.lstrip(" ") if not line_buffer else split,
                            font_path,
                            font_size,
                            color=color,
                            stroke_width=stroke_width,
                            stroke_color=stroke_color,
                            decoration=decoration,
                            decoration_thickness=thick,
                            shading=shading or Palette.TRANSPARENT,
                            background=self.background,
                            embedded_color=embedded_color,
                            ymin_correction=ymin_correction,
                            italic=pseudo_italic,
                        ))
                    line = remain
                # end of natural line
                if lineno != len(lines) - 1 or line_break_at_end:
                    yield from flush(line_buffer)
        # check buffer not empty
        if line_buffer:
            yield from flush(line_buffer)

    @staticmethod
    def text_concat(text: Iterable[RenderText]) -> RenderImage:
        rendered = [text.render() for text in text]
        width = sum(text.width for text in rendered)
        height = max(text.height for text in rendered)
        baseline = max(text.baseline for text in text)
        im = RenderImage.empty(width, height, Palette.TRANSPARENT)
        x = 0
        for obj, image in zip(text, rendered):
            im = im.paste(x, baseline - obj.baseline, image)
            x += image.width
        return im

    @classmethod
    def of(
        cls,
        text: str,
        *,
        styles: dict[str, TextStyle],
        default: TextStyle | None = None,
        max_width: int | None = None,
        alignment: Alignment = Alignment.START,
        line_spacing: int = 0,
        **kwargs: Unpack[BaseStyle],
    ) -> Self:
        """Create a Text object from a string with tags.

        Args:
            text: Text to render, including tag strings to specify styles.
            default: Default text style, i.e., no-tag style.
            styles: Mapping of tag names to text styles.
            max_width: Maximum width of the text, or None for no limit.
            alignment:
            line_spacing:

        Raises:
            ValueError: If the default style is not correctly specified.

        Example:
            >>> text = StyledText.of(
            ...     "Hello <b>world</b>!",
            ...     default=TextStyle(color=Palette.RED),
            ...     styles={"b": TextStyle(color=Palette.BLUE)},
            ... )
        """

        if default is not None:
            if "default" in styles:
                raise ValueError("Cannot specify default style twice")
            styles = {**styles, "default": default}
        elif "default" not in styles:
            raise ValueError("Missing default style")

        return cls(text, styles, max_width, alignment, line_spacing, **kwargs)

    @staticmethod
    def get_max_fitting_font_size(
        text: str,
        *,
        styles: dict[str, TextStyle],
        font_size_range: tuple[int, int],
        max_size: tuple[int, int],
        default: TextStyle | None = None,
        alignment: Alignment = Alignment.START,
        line_spacing: int = 0,
        **kwargs: Unpack[BaseStyle],
    ) -> int:
        """Find the maximum font size that fits the given size."""
        start, end = font_size_range
        max_width, max_height = max_size
        if start > end:
            start, end = end, start
        for size in range(end, start - 1, -1):
            default_cp = deepcopy(default)
            styles_cp = deepcopy(styles)
            if default_cp is not None:
                default_cp.size = size
            for style in styles_cp.values():
                if type(style.size) is float:
                    style.size = round(style.size * size)
            temp = StyledText.of(text,
                                 styles=styles_cp,
                                 default=default_cp,
                                 max_width=max_width,
                                 alignment=alignment,
                                 line_spacing=line_spacing,
                                 **kwargs)
            if temp.height <= max_height:
                return size
        raise ValueError(
            "Unable to find a font size that fits the given size.")
