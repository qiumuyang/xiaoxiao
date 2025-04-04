from typing import Iterable, NamedTuple

from pygments import lex
from pygments.lexers import get_lexer_by_name
from pygments.styles import get_style_by_name
from pygments.util import ClassNotFound

from src.utils.render import (Color, Palette, TextDecoration, TextShading,
                              TextStyle)


class StyleDict(NamedTuple):
    color: str
    bold: bool
    italic: bool
    underline: bool
    bgcolor: str
    border: str
    roman: bool
    sans: bool
    mono: bool
    ansicolor: str
    bgansicolor: str

    @property
    def style(self) -> TextStyle:
        if self.underline:
            deco = TextDecoration.underline()
        else:
            deco = None
        if self.bgcolor:
            bg = Color.from_hex(self.bgcolor)
        else:
            bg = Palette.TRANSPARENT
        sty = TextStyle(
            bold=self.bold,
            italic=self.italic,
            decoration=deco,
            shading=TextShading(color=bg),
        )
        if self.color:
            sty["color"] = Color.from_hex(self.color)
        return sty


def skip_last(iterable: Iterable) -> Iterable:
    iterator = iter(iterable)
    try:
        current = next(iterator)
    except StopIteration:
        return  # 空迭代对象
    for next_item in iterator:
        yield current  # 返回当前元素（非最后一个）
        current = next_item


def tokenize_code(
    lang: str,
    code: str,
    style_name: str = "default",
) -> Iterable[tuple[str, str, StyleDict]]:
    try:
        lexer = get_lexer_by_name(lang)
    except ClassNotFound:
        # raise ValueError(f"Unsupported language: {lang}")
        lexer = get_lexer_by_name("text")

    try:
        style = get_style_by_name(style_name)
    except ClassNotFound:
        style = get_style_by_name("default")

    # lex unexpectedly yield an extra newline even if it is not present
    # skip the last newline
    for token_type, token_content in skip_last(lex(code, lexer)):
        token_type_str = ".".join(t for t in str(token_type).split(".")[1:])
        token_style = style.style_for_token(token_type)
        style_dict = StyleDict(**token_style)  # type: ignore
        yield (token_content, token_type_str, style_dict)
