from typing import NamedTuple, Protocol

from ....base import RenderImage


class Element(Protocol):

    @property
    def width(self) -> int:
        ...

    @property
    def height(self) -> int:
        ...

    @property
    def line_continue(self) -> bool:
        ...

    @property
    def inline(self) -> bool:
        ...

    def split_at(self, width: int, next_width: int) -> "Split":
        """Split the element at the specified width.

        Args:
            width (int): The width to split the element at.
            next_width (int): The usable width for Split.remaining.

        Note:
            Split.remaining should be
            - None if the element fits within the width
            - self if the element does not fit within the width
        """
        ...

    def render(self) -> "RenderImage":
        ...

    def merge(self, other: "Element") -> "Element | None":
        """Used to merge elements on the same line."""
        ...


class Split(NamedTuple):

    current: Element | None
    remaining: Element | None
