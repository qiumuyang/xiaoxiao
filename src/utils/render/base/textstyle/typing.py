from typing import Final, TypedDict, cast

from typing_extensions import Required

from ..color import Color
from .decoration import TextDecoration, TextShading, TextStroke
from .font import AbsoluteSize, FontFamily, RelativeSize
from .wrap import TextWrap


class TextStyle(TypedDict, total=False):
    """
    A dictionary type that defines the style properties for text rendering.

    Attributes:
        font (str | FontFamily): The font family to be used.
        size (AbsoluteSize | RelativeSize):
            The size of the text, absolute or relative.
        color (Color):
            The color of the text (fill), standard or font-embedded color.
        stroke (TextStroke | None):
            The stroke style for the text, if any.
        decoration (TextDecoration | None):
            The decoration style for the text, if any.
        shading (TextShading | None):
            The shading style for the text, if any.
        bold (bool): Whether the text should be bold.
        italic (bool): Whether the text should be italic.
        wrap (TextWrap, reserved for multiline text):
            The wrap style for the text, including hyphenation and overflow,
            if any.
    """
    font: str | FontFamily
    size: int | float | AbsoluteSize | RelativeSize
    color: Color
    stroke: TextStroke | None
    decoration: TextDecoration | None
    shading: Color | TextShading | None
    bold: bool
    italic: bool
    wrap: TextWrap


class MinimalTextStyle(TypedDict, total=False):
    font: Required[str | FontFamily]
    size: Required[int | AbsoluteSize]
    color: Color
    stroke: TextStroke | None
    decoration: TextDecoration | None
    shading: Color | TextShading | None
    bold: bool
    italic: bool
    wrap: TextWrap


class TextStyleDefaults:
    color: Final[Color] = Color.of(0, 0, 0)
    stroke: Final = None
    decoration: Final = None
    shading: Final = None
    bold: Final[bool] = False
    italic: Final[bool] = False
    wrap: Final[TextWrap] = TextWrap.default()


def enforce_minimal(style: TextStyle) -> MinimalTextStyle:
    if "font" not in style:
        raise KeyError("Minimal text style must contain 'font'")
    if "size" not in style:
        raise KeyError("Minimal text style must contain 'size'")
    if not isinstance(style["size"], int):
        raise TypeError("Minimal text style's size must be absolute")
    return cast(MinimalTextStyle, style)
