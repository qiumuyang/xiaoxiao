from __future__ import annotations

from copy import deepcopy
from typing import Any, Generator, Iterable

from PIL import ImageFont
from typing_extensions import Self, Unpack, override

from src.utils.render.base.text import TextShading

from ...base import (Alignment, BaseStyle, Palette, RenderImage, RenderObject,
                     RenderText, TextDecoration, cached, volatile)
from ...utils import Undefined
from .style import FontFamily, TextStyle
from .style_utils import LineBuffer, TagParser
from .text import Text


class StyledText(RenderObject):
    """Render multi-styled text with HTML-like tags.

    Note:
        If the original text contains raw content like <something>,
        it should be escaped using the `escape` method.
    """

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

    @classmethod
    def escape(cls, text: str) -> str:
        return TagParser.escape(text)

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
        if not rendered_lines:
            return RenderImage.empty(0, 0, Palette.TRANSPARENT)
        return RenderImage.concat_vertical(
            rendered_lines,
            alignment=self.alignment,
            spacing=self.line_spacing,
        )

    def _cut_blocks(self) -> Generator[tuple[str, TextStyle], None, None]:
        """Yield successive (text_block, style) tuples from the tag parser."""
        parser = TagParser(self.text, self.styles)
        yield from parser.parse()

    def _load_style_properties(self, style: TextStyle) -> dict[str, Any]:
        """
        Extract font and style properties from a TextStyle.

        Returns a dictionary containing:
            - 'font': An ImageFont instance.
            - 'font_path': The path used to load the font.
            - 'font_size': The size of the font.
            - 'pseudo_italic': Whether to simulate italics.
            - 'color', 'stroke_width', 'stroke_color', 'hyphenation',
              'decoration', 'thickness', 'shading', 'embedded_color',
              'ymin_correction': Various text style settings.
        """
        font_size = round(Undefined.default(style.size, 0))
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
            font = ImageFont.truetype(str(font_path), font_size)
        else:
            font = ImageFont.load_default()

        return {
            "font": font,
            "font_path": font_path,
            "font_size": font_size,
            "pseudo_italic": pseudo_italic,
            "color": Undefined.default(style.color, None),
            "stroke_width": Undefined.default(style.stroke_width, 0),
            "stroke_color": Undefined.default(style.stroke_color, None),
            "hyphenation": Undefined.default(style.hyphenation, True),
            "decoration": Undefined.default(style.decoration,
                                            TextDecoration.NONE),
            "thickness": Undefined.default(style.decoration_thickness, -1),
            "shading": Undefined.default(style.shading, TextShading()),
            "embedded_color": Undefined.default(style.embedded_color, False),
            "ymin_correction": Undefined.default(style.ymin_correction, False),
        }

    def cut(self) -> Iterable[list[RenderText]]:
        """
        Cut the text into lines.

        Each line is represented as a list of RenderText objects.
        """
        buffer = LineBuffer(self.max_width)
        for text_block, style in self._cut_blocks():
            props = self._load_style_properties(style)
            font = props["font"]
            font_path = props["font_path"]
            pseudo_italic = props["pseudo_italic"]
            stroke_width = props["stroke_width"]
            hyphenation = props["hyphenation"]
            color = props["color"]
            stroke_color = props["stroke_color"]
            decoration = props["decoration"]
            thickness = props["thickness"]
            shading = props["shading"]
            embedded_color = props["embedded_color"]
            ymin_correction = props["ymin_correction"]

            # Process the text block split by natural newline characters.
            line_break_at_end = text_block.endswith("\n")
            natural_lines = text_block.split("\n")

            for lineno, natural_line in enumerate(natural_lines):
                current_line = natural_line
                first_segment = True
                while current_line:
                    # Ensure a valid font is set.
                    if not isinstance(font,
                                      ImageFont.FreeTypeFont) or not font_path:
                        raise ValueError("Font required")

                    try:
                        split_text, remaining, bad_split = Text.split_once(
                            font,
                            current_line,
                            stroke_width=stroke_width,
                            max_width=buffer.remaining_width,
                            hyphenation=hyphenation,
                            italic=pseudo_italic,
                            shading=shading,
                        )
                    except ValueError:
                        # If splitting fails due to width, flush the buffer and retry.
                        yield from buffer.flush()
                        split_text, remaining, bad_split = Text.split_once(
                            font,
                            current_line,
                            stroke_width=stroke_width,
                            max_width=buffer.remaining_width,
                            hyphenation=hyphenation,
                            italic=pseudo_italic,
                            shading=shading,
                        )

                    if buffer and bad_split:
                        # Flush buffer if the split part doesn't fit well.
                        yield from buffer.flush()
                        split_text, remaining, _ = Text.split_once(
                            font,
                            current_line,
                            stroke_width=stroke_width,
                            max_width=buffer.remaining_width,
                            hyphenation=hyphenation,
                            italic=pseudo_italic,
                            shading=shading,
                        )

                    if not buffer and not first_segment:
                        # newline, remove leading spaces
                        split_text = split_text.lstrip(" ")

                    first_segment = False
                    buffer.append(
                        RenderText.of(
                            split_text,
                            font_path,
                            props["font_size"],
                            color=color,
                            stroke_width=stroke_width,
                            stroke_color=stroke_color,
                            decoration=decoration,
                            decoration_thickness=thickness,
                            shading=shading or Palette.TRANSPARENT,
                            background=self.background,
                            embedded_color=embedded_color,
                            ymin_correction=ymin_correction,
                            italic=pseudo_italic,
                        ))
                    current_line = remaining

                # Flush the buffer at the end of a natural line.
                if lineno != len(natural_lines) - 1 or line_break_at_end:
                    yield from buffer.flush()
        yield from buffer.flush(non_empty=True)

    @staticmethod
    def text_concat(render_texts: Iterable[RenderText]) -> RenderImage:
        """
        Concatenate rendered texts horizontally into a single RenderImage.
        """
        rendered_images = [rt.render() for rt in render_texts]
        total_width = sum(img.width for img in rendered_images)
        max_height = max(img.height for img in rendered_images)
        baseline = max(rt.baseline for rt in render_texts)

        image = RenderImage.empty(total_width, max_height, Palette.TRANSPARENT)
        x_offset = 0
        for rt, img in zip(render_texts, rendered_images):
            image = image.paste(x_offset, baseline - rt.baseline, img)
            x_offset += img.width
        return image

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
        """
        Create a StyledText object from a string with embedded style tags.

        Args:
            text: Text to render, including tag strings to specify styles.
            default: Default text style
                (i.e., the style for content outside any tag).
            styles: Mapping of tag names to text styles.
            max_width: Maximum width of the text, or None for no limit.
            alignment: Alignment of the rendered text.
            line_spacing: Spacing between lines.

        Raises:
            ValueError:
                If the default style is specified twice or missing.
                If a style is used but not defined.

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
