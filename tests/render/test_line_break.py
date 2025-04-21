import pytest

from src.utils.render import RenderImage
from src.utils.render.objects.paragraph.layout import (Element, LineBreaker,
                                                       Split)


class MockElement:

    def __init__(self, width, height, splitable=True):
        self._width = width
        self._height = height
        self._splitable = splitable

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    @property
    def inline(self) -> bool:
        return True

    def render(self) -> RenderImage:
        return RenderImage.empty(1, 1)

    def split_at(self, width: int, next_width: int) -> Split:
        if self._width <= width:
            return Split(current=self, remaining=None)
        if not self._splitable:
            return Split(current=None, remaining=self)
        return Split(current=MockElement(width, self._height),
                     remaining=MockElement(self._width - width, self._height))

    @property
    def line_continue(self) -> bool:
        return False

    def merge(self, other: Element) -> Element | None:
        return None


def test_line_breaker_single_element():
    elements = [MockElement(5, 10)]
    line_breaker = LineBreaker(elements)
    lines = list(line_breaker.break_lines(10))
    assert len(lines) == 1
    assert len(lines[0]) == 1
    assert lines[0][0].width == 5


def test_line_breaker_multiple_elements():
    elements = [MockElement(5, 10), MockElement(3, 10), MockElement(2, 10)]
    line_breaker = LineBreaker(elements)
    lines = list(line_breaker.break_lines(10))
    assert len(lines) == 1
    assert len(lines[0]) == 3
    assert sum(e.width for e in lines[0]) == 10


def test_line_breaker_split_element():
    elements = [MockElement(15, 10)]
    line_breaker = LineBreaker(elements)
    lines = list(line_breaker.break_lines(10))
    assert len(lines) == 2
    assert len(lines[0]) == 1
    assert lines[0][0].width == 10
    assert len(lines[1]) == 1
    assert lines[1][0].width == 5


def test_line_breaker_no_max_width():
    elements = [MockElement(5, 10), MockElement(3, 10), MockElement(2, 10)]
    line_breaker = LineBreaker(elements)
    lines = list(line_breaker.break_lines(None))
    assert len(lines) == 1
    assert len(lines[0]) == 3
    assert sum(e.width for e in lines[0]) == 10


def test_line_breaker_element_too_wide():
    elements = [MockElement(15, 10, splitable=False)]
    line_breaker = LineBreaker(elements)
    with pytest.raises(ValueError):
        list(line_breaker.break_lines(5))
    lines = list(line_breaker.break_lines(15))
    assert len(lines) == 1
    elements[0]._splitable = True
    lines = list(line_breaker.break_lines(5))
    assert len(lines) == 3
