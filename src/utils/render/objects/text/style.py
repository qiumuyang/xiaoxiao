from __future__ import annotations

import copy
from typing import Iterable, NamedTuple

from typing_extensions import Self

from ...base import Cacheable, Color, TextDecoration, TextShading, volatile
from ...utils import PathLike, Undefined, undefined

SIM_ITALIC = bool


class FontFamily(NamedTuple):
    regular: PathLike
    bold: PathLike
    italic: PathLike | None = None
    bold_italic: PathLike | None = None

    def select(self, bold: bool, italic: bool) -> tuple[PathLike, SIM_ITALIC]:
        if bold and italic:
            return self.bold_italic or self.bold, self.bold_italic is None
        if bold:
            return self.bold, False
        if italic:
            return self.italic or self.regular, self.italic is None
        return self.regular, False


class TextStyle(Cacheable):
    """Defines the style of a text object.

    If not specified, the outer-level style will be used.

    Attributes:
        size: font size if integer, or relative size to default if float.
    """

    def __init__(
        self,
        font: PathLike | FontFamily | Undefined,
        size: float | Undefined,
        color: Color | None | Undefined,
        stroke_width: int | Undefined,
        stroke_color: Color | None | Undefined,
        shading: TextShading | Undefined,
        hyphenation: bool | Undefined,
        decoration: TextDecoration | Undefined,
        decoration_thickness: int | Undefined,
        embedded_color: bool | Undefined,
        ymin_correction: bool | Undefined,
        italic: bool | Undefined,
        bold: bool | Undefined,
    ) -> None:
        super().__init__()
        with volatile(self):
            self.font = font
            self.size = size
            self.color = color
            self.stroke_width = stroke_width
            self.stroke_color = stroke_color
            self.shading = shading
            self.hyphenation = hyphenation
            self.decoration = decoration
            self.decoration_thickness = decoration_thickness
            self.embedded_color = embedded_color
            self.ymin_correction = ymin_correction
            self.italic = italic
            self.bold = bold

    @classmethod
    def of(
        cls,
        font: PathLike | FontFamily | Undefined = undefined,
        size: float | Undefined = undefined,
        *,
        bold: bool | Undefined = undefined,
        italic: bool | Undefined = undefined,
        color: Color | None | Undefined = undefined,
        stroke_width: int | Undefined = undefined,
        stroke_color: Color | None | Undefined = undefined,
        background: Color | TextShading | Undefined = undefined,
        hyphenation: bool | Undefined = undefined,
        decoration: TextDecoration | Undefined = undefined,
        decoration_thickness: int | Undefined = undefined,
        embedded_color: bool | Undefined = undefined,
        ymin_correction: bool | Undefined = undefined,
    ) -> Self:
        if isinstance(background, Color):
            background = TextShading(background)
        return cls(
            font,
            size,
            color,
            stroke_width,
            stroke_color,
            background,
            hyphenation,
            decoration,
            decoration_thickness,
            embedded_color,
            ymin_correction,
            italic,
            bold,
        )

    def with_color(self, color: Color) -> TextStyle:
        obj = copy.copy(self)
        obj.color = color
        return obj

    def with_size(self, size: float) -> TextStyle:
        obj = copy.copy(self)
        obj.size = size
        return obj

    def items(self, strip: bool = False) -> Iterable[tuple[str, object]]:
        for key, value in self.__dict__.items():
            if value is not undefined and key not in self.SKIP_ATTRS:
                if strip:
                    key = key.strip("_")
                yield key, value

    def __str__(self) -> str:
        var_str = ", ".join(f"{k}={v}" for k, v in self.items())
        return f"TextStyle({var_str})"
