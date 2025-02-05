from functools import cached_property
from typing import Any, Callable, NamedTuple

from PIL import Image, ImageDraw
from typing_extensions import Unpack

from src.utils.render import BaseStyle, Color, Direction
from src.utils.render import Image as ImageObject
from src.utils.render import (Palette, RelativeContainer, RenderImage,
                              RenderObject, cached)

from .base import ColorPolicy, DataGraph


class Anchor(NamedTuple):
    key_anchors: list[tuple[int, int]]
    value_anchors: list[tuple[int, int]]


class BarChart(DataGraph):

    def __init__(
        self,
        data: list[float] | dict[Any, float] | list[int] | dict[Any, int],
        *,
        bar_width: int,
        bar_spacing: int,
        bar_length: int,
        layout: Direction,
        color: Color | list[Color] | ColorPolicy,
        **kwargs: Unpack[BaseStyle],
    ):
        super().__init__(data, **kwargs)

        self.bar_width = bar_width
        self.bar_spacing = bar_spacing
        self.bar_length = bar_length
        self.layout = layout
        self.color = color
        if isinstance(color, list) and len(color) != len(data):
            raise ValueError("Length of color list must match data length")

    @property
    def horizontal_size(self) -> tuple[int, int]:
        w = (self.bar_width + self.bar_spacing) * len(
            self.data) - self.bar_spacing
        h = self.bar_length
        return w, h

    @property
    def content_width(self) -> int:
        w, h = self.horizontal_size
        return w if self.layout == Direction.HORIZONTAL else h

    @property
    def content_height(self) -> int:
        w, h = self.horizontal_size
        return h if self.layout == Direction.HORIZONTAL else w

    @cached_property
    def anchors(self) -> Anchor:
        """Get the anchor points of the bars (center aligned)."""
        key_anchors = []
        value_anchors = []

        if self.layout == Direction.HORIZONTAL:
            x, y = 0, self.bar_length
        else:
            x, y = 0, 0

        for value in self.data.values():
            if self.max == self.min:
                bar_length = self.bar_length
            else:
                bar_length = self.bar_length * value / self.max
            if self.layout == Direction.HORIZONTAL:
                key_anchors.append((x + self.bar_width // 2, y))
                value_anchors.append((x + self.bar_width // 2, y - bar_length))
                x += self.bar_width + self.bar_spacing
            else:
                key_anchors.append((x, y + self.bar_width // 2))
                value_anchors.append((x + bar_length, y + self.bar_width // 2))
                y += self.bar_width + self.bar_spacing

        return Anchor(key_anchors, value_anchors)

    def render_content(self) -> RenderImage:
        w, h = self.horizontal_size
        if self.layout == Direction.VERTICAL:
            w, h = h, w
        canvas = Image.new("RGBA", (w, h), Palette.TRANSPARENT)
        draw = ImageDraw.Draw(canvas)

        if self.layout == Direction.HORIZONTAL:
            x_offset, y_offset = self.bar_width // 2, 0
        else:
            x_offset, y_offset = 0, self.bar_width // 2

        for i, (key_anchor, value_anchor,
                value) in enumerate(zip(*self.anchors, self.data.values())):
            if isinstance(self.color, list):
                color = self.color[i]
            elif isinstance(self.color, Color):
                color = self.color
            else:
                color = self.color(value, self.min, self.max)

            xk, yk = key_anchor
            xv, yv = value_anchor
            x, y = sorted([xk, xv]), sorted([yk, yv])
            draw.rectangle(
                [
                    x[0] - x_offset,
                    y[0] - y_offset,
                    x[1] + x_offset,
                    y[1] + y_offset,
                ],
                fill=color,
            )

        return RenderImage.from_pil(canvas)


class BarChartWithLabel(BarChart):

    def __init__(
        self,
        data: dict[Any, float],
        *,
        bar_width: int,
        bar_spacing: int,
        bar_length: int,
        layout: Direction,
        color: Color | list[Color] | ColorPolicy,
        key_to_label: Callable[[Any], RenderObject] | None = None,
        value_to_label: Callable[[float], RenderObject] | None = None,
        key_spacing: int = 0,
        value_spacing: int = 0,
        **kwargs: Unpack[BaseStyle],
    ):
        super().__init__(
            data,
            bar_width=bar_width,
            bar_spacing=bar_spacing,
            bar_length=bar_length,
            layout=layout,
            color=color,
            **kwargs,
        )

        self.key_to_label = key_to_label
        self.value_to_label = value_to_label
        self.key_spacing = key_spacing
        self.value_spacing = value_spacing

    @property
    def key_labels(self) -> list[RenderObject]:
        if self.key_to_label is None:
            return []
        return [self.key_to_label(key) for key in self.data.keys()]

    @property
    def value_labels(self) -> list[RenderObject]:
        if self.value_to_label is None:
            return []
        return [self.value_to_label(value) for value in self.data.values()]

    @property
    @cached
    def content_width(self) -> int:
        return self.render_content().width

    @property
    @cached
    def content_height(self) -> int:
        return self.render_content().height

    @cached
    def render_content(self) -> RenderImage:
        chart = ImageObject.from_image(BarChart.render_content(self))
        container = RelativeContainer()
        container.add_child(chart, align_top=container, align_left=container)
        key_anchor, value_anchor = self.anchors

        for key_label, (x, y) in zip(self.key_labels, key_anchor):
            if self.layout == Direction.HORIZONTAL:
                y += self.key_spacing
                x -= key_label.width // 2
            else:
                x -= self.key_spacing + key_label.width
                y -= key_label.height // 2
            container.add_child(
                key_label,
                align_top=chart,
                align_left=chart,
                offset=(x, y),
            )

        for value_label, (x, y) in zip(self.value_labels, value_anchor):
            if self.layout == Direction.HORIZONTAL:
                y -= self.value_spacing + value_label.height
                x -= value_label.width // 2
            else:
                x += self.value_spacing
                y -= value_label.height // 2
            container.add_child(
                value_label,
                align_top=chart,
                align_left=chart,
                offset=(x, y),
            )

        return container.render_content()
