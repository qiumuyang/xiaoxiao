from dataclasses import dataclass
from enum import Enum, auto
from typing import Literal


class OverflowWrap(Enum):
    """
    Enum class representing the overflow wrap behavior for text.

    Attributes:
        STRICT:
            Overflowing word should start on a new line.
        FLEX:
            Overflowing word should continue on the same line,
            moving to the next line only if necessary.
    """
    STRICT = auto()
    FLEX = auto()


class Hyphen(Enum):
    """
    Enum class representing the hyphenation behavior for text.

    Attributes:
        NONE:
            No hyphenation should be applied.
        ANYWHERE:
            Hyphenation at any point is allowed.
            Same as NONE but with hyphenation.
        RULE:
            Hyphenation is allowed only at specified points (based on pyphen).
    """
    NONE = auto()
    ANYWHERE = auto()
    RULE = auto()


@dataclass(frozen=True)
class TextWrap:

    hyphen: Hyphen
    overflow: OverflowWrap

    @classmethod
    def default(cls) -> "TextWrap":
        return cls(Hyphen.RULE, OverflowWrap.FLEX)

    @classmethod
    def of(
        cls,
        *,
        hyphen: Literal["none", "anywhere", "rule"] = "rule",
        overflow: Literal["strict", "flex"] = "flex",
    ) -> "TextWrap":
        return cls(Hyphen[hyphen.upper()], OverflowWrap[overflow.upper()])
