from enum import Enum
from typing import NamedTuple

import cv2
from typing_extensions import Self

from .color import Color, Palette


class Alignment(Enum):
    START = 1
    CENTER = 2
    END = 3


class Direction(Enum):
    HORIZONTAL = 1
    VERTICAL = 2


class Interpolation(Enum):
    NEAREST = cv2.INTER_NEAREST_EXACT
    BILINEAR = cv2.INTER_LINEAR_EXACT
    BICUBIC = cv2.INTER_CUBIC
    LANCZOS = cv2.INTER_LANCZOS4
    AREA = cv2.INTER_AREA


class Border:

    def __init__(self, color: Color, width: int) -> None:
        self.color = color
        self.width = width

    @classmethod
    def zero(cls) -> Self:
        return cls.of(0)

    @classmethod
    def of(cls, width: int, color: Color = Palette.BLACK) -> Self:
        return cls(color, width)


class Space:

    def __init__(self, left: int, right: int, top: int, bottom: int) -> None:
        self.left = left
        self.right = right
        self.top = top
        self.bottom = bottom

    @classmethod
    def zero(cls) -> Self:
        return cls(0, 0, 0, 0)

    @classmethod
    def all(cls, width: int) -> Self:
        return cls(width, width, width, width)

    @classmethod
    def of(cls, left: int, right: int, top: int, bottom: int) -> Self:
        return cls(left, right, top, bottom)

    @classmethod
    def of_side(cls, horizontal: int, vertical: int) -> Self:
        return cls(horizontal, horizontal, vertical, vertical)

    @classmethod
    def horizontal(cls, width: int) -> Self:
        return cls(width, width, 0, 0)

    @classmethod
    def vertical(cls, width: int) -> Self:
        return cls(0, 0, width, width)

    @property
    def width(self) -> int:
        return self.left + self.right

    @property
    def height(self) -> int:
        return self.top + self.bottom

    def as_tuple(self) -> tuple[int, int, int, int]:
        return self.left, self.right, self.top, self.bottom


class BoundingBox(NamedTuple):
    x: int
    y: int
    w: int
    h: int

    @classmethod
    def of(cls, x: int, y: int, w: int, h: int) -> Self:
        return cls(x, y, w, h)

    def contains(self, x: int, y: int) -> bool:
        """Check if a point is inside the bounding box."""
        return self.x1 <= x < self.x2 and self.y1 <= y < self.y2

    def intersects(self, other: Self) -> bool:
        """Check if two bounding boxes intersect."""
        return any(
            other.contains(x, y) for x in (self.x1, self.x2)
            for y in (self.y1, self.y2))

    @property
    def x1(self) -> int:
        return self.x

    @property
    def y1(self) -> int:
        return self.y

    @property
    def x2(self) -> int:
        return self.x + self.w

    @property
    def y2(self) -> int:
        return self.y + self.h
