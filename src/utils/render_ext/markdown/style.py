from pathlib import Path
from typing import Callable, NamedTuple, cast

import mistletoe.span_token as T
from typing_extensions import Required

from src.utils.render import (Color, FontFamily, Space, TextDecoration,
                              TextShading, TextStyle, TextWrap)

from .token import Emoji

StrOrPath = str | Path


class OverrideStyle(TextStyle):

    foreground_color: Required[Color]

    @staticmethod  # type: ignore
    def to_normal(style: TextStyle) -> TextStyle:
        kv = {k: v for k, v in style.items() if k != "foreground_color"}
        return cast(TextStyle, kv)

    @staticmethod  # type: ignore
    def isinstance(style: TextStyle) -> bool:
        return "foreground_color" in style


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
    caption: str = "#666666"


class Palette(NamedTuple):
    break_line: str = "#D8DEE4"
    quote_bar: str = "#D0D7DE"
    table_border: str = "D0D7DE"


class TextSize(NamedTuple):
    main: int = 24
    heading: list[int] = [48, 42, 36, 30, 24, 20]
    code_inline: int = 22
    unordered_bullet_scale: float = 1.0
    # measure different from pillow pixel size
    caption: int = 14


class TextFont(NamedTuple):
    main: FontFamily = FontFamily.of(regular="data/static/fonts/MSYAHEI.ttc",
                                     bold="data/static/fonts/MSYAHEIbd.ttc")
    code: FontFamily = FontFamily.of(
        regular="data/static/fonts/MapleMonoNormalNL-CN-Regular.ttf",
        bold="data/static/fonts/MapleMonoNormalNL-CN-Bold.ttf",
        italic="data/static/fonts/MapleMonoNormalNL-CN-Italic.ttf",
        bold_italic="data/static/fonts/MapleMonoNormalNL-CN-BoldItalic.ttf")
    emoji: FontFamily = FontFamily.of(regular="data/static/fonts/seguiemj.ttf",
                                      embedded_color=True,
                                      baseline_correction=True)


class Heading(NamedTuple):
    font: FontFamily
    sizes: list[int]
    color: str
    bold: list[bool] = [True, True, True, True, True, True]
    line_below: list[float | None] = [0.33, 0.33, None, None, None, None]
    margin_factor: float = 0.5

    def level(self, level: int) -> TextStyle:
        return TextStyle(font=self.font,
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
    rounded: bool = True
    radius_factor: float = 0.5

    @property
    def style(self) -> TextStyle:
        return TextStyle(font=self.font,
                         size=self.size,
                         color=Color.from_hex(self.color),
                         wrap=TextWrap.of(hyphen="none"))


class CodeInline(NamedTuple):
    font: FontFamily
    size: int
    color: str
    background: str
    force_regular: bool = False
    rounded: bool = True

    @property
    def style(self) -> TextStyle:
        sty = TextStyle(
            font=self.font,
            size=self.size,
            color=Color.from_hex(self.color),
            shading=TextShading(color=Color.from_hex(self.background),
                                rounded=self.rounded,
                                padding=Space.of_side(4, 2)),
        )
        if self.force_regular:
            sty["bold"] = False
            sty["italic"] = False
        return sty


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
        return OverrideStyle(font=self.font,
                             size=self.size,
                             color=Color.from_hex(self.color),
                             italic=self.italic,
                             foreground_color=Color.from_hex(self.color))


class Link(NamedTuple):
    color: str
    underline: bool = True

    @property
    def style(self) -> TextStyle:
        return TextStyle(
            color=Color.from_hex(self.color),
            decoration=TextDecoration.underline() if self.underline else None,
        )


class Table(NamedTuple):
    main: str
    alt: str

    border_color: str
    border_thick: int = 1

    min_column_chars: int = 4

    header_bold: bool = True
    header_main: bool = True
    padding_factor: tuple[float, float] = (0.8, 0.4)

    @property
    def header(self) -> TextStyle:
        return TextStyle(bold=self.header_bold)

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
        return TextStyle(size=self.ordered_bullet_size
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
        return TextStyle(font=self.text_font.main,
                         size=self.text_size.main,
                         color=Color.from_hex(self.text_palette.main))

    @property
    def caption(self) -> TextStyle:
        return TextStyle(font=self.text_font.main,
                         size=self.text_size.caption,
                         color=Color.from_hex(self.text_palette.caption))

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
            T.Emphasis: (TextStyle(italic=True), "em"),
            T.Strong: (TextStyle(bold=True), "strong"),
            T.InlineCode: (self.code_inline.style, "code"),
            T.Link: (self.link.style, "a"),
            T.Strikethrough:
            (TextStyle(decoration=TextDecoration.line_through()), "s"),
            T.EscapeSequence: (TextStyle(), "esc"),
            Emoji: (TextStyle(font=self.text_font.emoji), "emoji"),
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
