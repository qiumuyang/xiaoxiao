import copy
from pathlib import Path
from typing import Callable, NamedTuple

import mistletoe.span_token as T

from src.utils.render import (Color, FontFamily, TextDecoration, TextShading,
                              TextStyle)

StrOrPath = str | Path


class OverrideStyle(TextStyle):
    """

    This is an ugly hack to allow overriding the foreground color for quote.
    """

    foreground_color: Color | None = None

    @classmethod
    def from_style(cls,
                   style: TextStyle,
                   foreground_color: Color | None = None) -> "OverrideStyle":
        obj = cls.__new__(cls)
        obj.__dict__.update(copy.deepcopy(style.__dict__))
        obj.foreground_color = foreground_color
        return obj


class BackgroundPalette(NamedTuple):
    main: str = "#FFFFFF"
    code_block: str = "#F6F8FA"
    code_inline: str = "#EFF1F3"
    quote: str = main
    table_main: str = main
    table_alt: str = "#F6F8FA"


class TextPalette(NamedTuple):
    main: str = "#1F2328"
    heading: str = main
    link: str = "#0969DA"
    quote: str = "#656D76"
    code_block: str = main


class Palette(NamedTuple):
    break_line: str = "#D8DEE4"
    quote_bar: str = "#D0D7DE"
    table_border: str = "D0D7DE"


class TextSize(NamedTuple):
    main: int = 24
    heading: list[int] = [48, 42, 36, 30, 24, 20]
    code_inline: int = 22
    unordered_bullet_scale: float = 1.0


class TextFont(NamedTuple):
    main: FontFamily = FontFamily(regular="data/static/fonts/MSYAHEI.ttc",
                                  bold="data/static/fonts/MSYAHEIbd.ttc")
    code: FontFamily = FontFamily(
        regular="data/static/fonts/MapleMonoNormalNL-CN-Regular.ttf",
        bold="data/static/fonts/MapleMonoNormalNL-CN-Bold.ttf",
        italic="data/static/fonts/MapleMonoNormalNL-CN-Italic.ttf",
        bold_italic="data/static/fonts/MapleMonoNormalNL-CN-BoldItalic.ttf")


class Heading(NamedTuple):
    font: FontFamily
    sizes: list[int]
    color: str
    bold: list[bool] = [True, True, True, True, True, True]
    line_below: list[float | None] = [0.33, 0.33, None, None, None, None]
    margin_factor: float = 0.5

    def level(self, level: int) -> TextStyle:
        return TextStyle.of(font=self.font,
                            size=self.sizes[level - 1],
                            color=Color.from_hex(self.color),
                            bold=self.bold[level - 1])

    def line_offset(self, level: int) -> int | None:
        rel = self.line_below[level - 1]
        return round(rel * self.sizes[level - 1]) if rel is not None else None

    def margin_below(self, level: int) -> int:
        line_below = self.line_below[level - 1]
        size = self.sizes[level - 1]
        return round(self.margin_factor *
                     size) if line_below is not None else 0


class CodeBlock(NamedTuple):
    font: FontFamily
    size: int
    color: str
    background: str
    padding_factor: tuple[float, float] = (1.0, 0.4)
    highlight_style: str = "default"

    @property
    def style(self) -> TextStyle:
        return TextStyle.of(font=self.font,
                            size=self.size,
                            color=Color.from_hex(self.color))


class CodeInline(NamedTuple):
    font: FontFamily
    size: int
    color: str
    background: str
    force_regular: bool = False
    rounded: bool = True

    @property
    def style(self) -> TextStyle:
        style_ = TextStyle.of(
            font=self.font,
            size=self.size,
            color=Color.from_hex(self.color),
            background=TextShading(color=Color.from_hex(self.background),
                                   rounded=self.rounded,
                                   padding=(4, 2)),
        )
        if self.force_regular:
            style_.bold = False
            style_.italic = False
        return style_


class Quote(NamedTuple):
    font: FontFamily
    size: int
    color: str
    bar_color: str
    background: str
    italic: bool = False
    bar_thick: int = 6
    indent_factor: float = 1.3

    @property
    def style(self) -> OverrideStyle:
        normal = TextStyle.of(font=self.font,
                              size=self.size,
                              color=Color.from_hex(self.color),
                              italic=self.italic)
        return OverrideStyle.from_style(normal, Color.from_hex(self.color))


class Link(NamedTuple):
    color: str
    underline: bool = True

    @property
    def style(self) -> TextStyle:
        return TextStyle.of(color=Color.from_hex(self.color),
                            decoration=TextDecoration.UNDERLINE
                            if self.underline else TextDecoration.NONE)


class Table(NamedTuple):
    main: str
    alt: str

    border_color: str
    border_thick: int = 1

    header_bold: bool = True
    header_main: bool = True
    padding_factor: tuple[float, float] = (0.8, 0.4)

    @property
    def header(self) -> TextStyle:
        return TextStyle.of(bold=self.header_bold)

    def background(self, index: int) -> Color:
        if index == 0:
            return Color.from_hex(self.main if self.header_main else self.alt)
        return Color.from_hex(self.alt if index % 2 == 0 else self.main)


class ThematicBreak(NamedTuple):
    color: str
    thick: int = 4


def num(n: int) -> str:
    return str(n)


def roman(n: int) -> str:
    m = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"),
         (90, "XC"), (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"),
         (4, "IV"), (1, "I")]
    result = ""
    for value, letter in m:
        while n >= value:
            result += letter
            n -= value
    return result.lower()


def alpha(n: int) -> str:
    result = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        result = chr(r + ord("a")) + result
    return result


class List(NamedTuple):
    unordered_bullet_size: int
    ordered_bullet_size: int
    bullet_color: str
    unordered_bullets: list[str] = ["•", "◦", "▪", "▫"]
    ordered_bullets: list[Callable[[int], str]] = [num, roman, alpha]
    indent_factor: float = 2.0
    bullet_margin_factor: float = 0.5

    def unordered_bullet(self, indent: int) -> str:
        return self.unordered_bullets[indent % len(self.unordered_bullets)]

    def ordered_bullet(self, indent: int, index: int) -> str:
        if indent >= len(self.ordered_bullets):
            fn = self.ordered_bullets[-1]
        else:
            fn = self.ordered_bullets[indent]
        return fn(index) + "."

    def bullet(self, is_ordered: bool) -> TextStyle:
        return TextStyle.of(size=self.ordered_bullet_size
                            if is_ordered else self.unordered_bullet_size,
                            color=Color.from_hex(self.bullet_color))


class Spacing(int):

    parent: "MarkdownStyle"
    divisor: int

    def __new__(cls,
                default: int,
                parent: "MarkdownStyle",
                divisor: int = 4) -> "Spacing":
        o = super().__new__(cls, default)
        o.divisor = divisor
        o.parent = parent
        return o

    def get(self, relative: int) -> int:
        return relative // self.divisor

    @property
    def max(self) -> int:
        return self.get(self.parent.heading.sizes[0])

    @property
    def min(self) -> int:
        return self.get(self.parent.heading.sizes[-1])

    @property
    def medium(self) -> int:
        return self.get(self.parent.heading.sizes[2])


class MarkdownStyle(NamedTuple):

    bg_palette: BackgroundPalette = BackgroundPalette()
    text_palette: TextPalette = TextPalette()
    palette: Palette = Palette()
    text_size: TextSize = TextSize()
    text_font: TextFont = TextFont()
    line_space_divisor: int = 4
    space_divisor: int = 1

    @property
    def unit(self) -> int:
        return self.text_size.main

    @property
    def line_spacing(self) -> Spacing:
        return Spacing(self.unit // self.line_space_divisor, self,
                       self.line_space_divisor)

    @property
    def spacing(self) -> Spacing:
        return Spacing(self.unit // self.space_divisor, self,
                       self.space_divisor)

    @property
    def background(self) -> Color:
        return Color.from_hex(self.bg_palette.main)

    @property
    def main(self) -> TextStyle:
        return TextStyle.of(font=self.text_font.main,
                            size=self.text_size.main,
                            color=Color.from_hex(self.text_palette.main))

    @property
    def heading(self) -> Heading:
        return Heading(font=self.text_font.main,
                       sizes=self.text_size.heading,
                       color=self.text_palette.heading)

    @property
    def code_block(self) -> CodeBlock:
        return CodeBlock(font=self.text_font.code,
                         size=self.text_size.main,
                         color=self.text_palette.code_block,
                         background=self.bg_palette.code_block)

    @property
    def code_inline(self) -> CodeInline:
        return CodeInline(font=self.text_font.code,
                          size=self.text_size.code_inline,
                          color=self.text_palette.code_block,
                          background=self.bg_palette.code_inline)

    @property
    def link(self) -> Link:
        return Link(color=self.text_palette.link)

    @property
    def quote(self) -> Quote:
        return Quote(font=self.text_font.main,
                     size=self.text_size.main,
                     color=self.text_palette.quote,
                     bar_color=self.palette.quote_bar,
                     background=self.bg_palette.quote)

    @property
    def table(self) -> Table:
        return Table(main=self.bg_palette.table_main,
                     alt=self.bg_palette.table_alt,
                     border_color=self.palette.table_border)

    @property
    def span(self) -> dict[type[T.SpanToken], tuple[TextStyle, str]]:
        return {
            T.Emphasis: (TextStyle.of(italic=True), "em"),
            T.Strong: (TextStyle.of(bold=True), "strong"),
            T.InlineCode: (self.code_inline.style, "code"),
            T.Link: (self.link.style, "a"),
            T.Strikethrough:
            (TextStyle.of(decoration=TextDecoration.LINE_THROUGH), "s"),
        }

    @property
    def thematic_break(self) -> ThematicBreak:
        return ThematicBreak(color=self.palette.break_line)

    @property
    def list(self) -> List:
        return List(
            unordered_bullet_size=round(self.text_size.main *
                                        self.text_size.unordered_bullet_scale),
            ordered_bullet_size=self.text_size.main,
            bullet_color=self.text_palette.main,
        )
