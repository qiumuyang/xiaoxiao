from dataclasses import dataclass
from enum import Enum, Flag, auto
from typing import ClassVar, Literal, TypedDict

from typing_extensions import Unpack

from ..color import Color
from ..properties import Space


class TextDecorationType(Flag):
    UNDERLINE = auto()
    OVERLINE = auto()
    LINE_THROUGH = auto()


class TextDecorationLayer(Enum):
    OVER = auto()
    UNDER = auto()


class _DecorationAlias(TypedDict, total=False):
    thickness: int
    layer: TextDecorationLayer | Literal["over", "under"]


def _make_text_decoration(
    type: TextDecorationType,
    thickness: int = -1,
    layer: TextDecorationLayer
    | Literal["over", "under"] = TextDecorationLayer.OVER,
) -> "TextDecoration":
    if isinstance(layer, str):
        layer = TextDecorationLayer[layer.upper()]
    return TextDecoration(type, thickness, layer)


@dataclass(frozen=True)
class TextDecoration:
    """Text decoration style.

    Attributes:
        type: decoration type.
        thickness: decoration thickness.
        layer: line over or under the text.
    """

    type: TextDecorationType
    thickness: int
    layer: TextDecorationLayer

    # yapf: disable
    UNDERLINE: ClassVar[TextDecorationType] = TextDecorationType.UNDERLINE
    OVERLINE: ClassVar[TextDecorationType] = TextDecorationType.OVERLINE
    LINE_THROUGH: ClassVar[TextDecorationType] = TextDecorationType.LINE_THROUGH
    OVER: ClassVar[TextDecorationLayer] = TextDecorationLayer.OVER
    UNDER: ClassVar[TextDecorationLayer] = TextDecorationLayer.UNDER
    # yapf: enable

    @staticmethod
    def underline(**kwargs: Unpack[_DecorationAlias]) -> "TextDecoration":
        return _make_text_decoration(TextDecorationType.UNDERLINE, **kwargs)

    @staticmethod
    def overline(**kwargs: Unpack[_DecorationAlias]) -> "TextDecoration":
        return _make_text_decoration(TextDecorationType.OVERLINE, **kwargs)

    @staticmethod
    def line_through(**kwargs: Unpack[_DecorationAlias]) -> "TextDecoration":
        return _make_text_decoration(TextDecorationType.LINE_THROUGH, **kwargs)

    @staticmethod
    def all(**kwargs: Unpack[_DecorationAlias]) -> "TextDecoration":
        return _make_text_decoration(
            TextDecorationType.UNDERLINE | TextDecorationType.OVERLINE
            | TextDecorationType.LINE_THROUGH, **kwargs)


@dataclass(frozen=True)
class TextShading:
    """Distinguish from `RenderObject.background`.

    Attributes:
        color: shading color.
        rounded: whether to use rounded corner rect.
        padding: padding around the text.
    """
    color: Color
    rounded: bool = True
    padding: Space = Space.all(0)


@dataclass(frozen=True)
class TextStroke:
    width: int
    color: Color
