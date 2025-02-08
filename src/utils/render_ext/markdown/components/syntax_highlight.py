from typing import Iterable, NamedTuple

from pygments import lex
from pygments.lexers import get_lexer_by_name
from pygments.styles import get_style_by_name
from pygments.util import ClassNotFound

from src.utils.render import Color, TextDecoration, TextShading, TextStyle
from src.utils.render.base.color import Palette


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
            deco = TextDecoration.UNDERLINE
        else:
            deco = TextDecoration.NONE
        if self.bgcolor:
            bg = Color.from_hex(self.bgcolor)
        else:
            bg = Palette.TRANSPARENT
        return TextStyle.of(
            color=Color.from_hex(self.color) if self.color else None,
            bold=self.bold,
            italic=self.italic,
            decoration=deco,
            background=TextShading(color=bg),
        )


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

    for token_type, token_content in lex(code, lexer):
        token_type_str = ".".join(t for t in str(token_type).split(".")[1:])
        token_style = style.style_for_token(token_type)
        style_dict = StyleDict(**token_style)  # type: ignore
        yield (token_content, token_type_str, style_dict)
