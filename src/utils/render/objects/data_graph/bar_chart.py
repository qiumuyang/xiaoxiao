from typing import Any

from PIL import Image, ImageDraw
from typing_extensions import Unpack

from ...base import BaseStyle, Color, Direction, Palette, RenderImage
from .base import ColorPolicy, DataGraph


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

    def render_content(self) -> RenderImage:
        canvas = Image.new("RGBA", (self.content_width, self.content_height),
                           Palette.TRANSPARENT)
        draw = ImageDraw.Draw(canvas)

        if self.layout == Direction.HORIZONTAL:
            x, y = 0, self.bar_length
        else:
            x, y = 0, self.content_height

        for i, (_, value) in enumerate(self.data.items()):
            if isinstance(self.color, list):
                color = self.color[i]
            elif isinstance(self.color, Color):
                color = self.color
            else:
                color = self.color(value, self.min, self.max)
            if self.max == self.min:
                bar_length = self.bar_length
            else:
                bar_length = self.bar_length * value / self.max
            if self.layout == Direction.HORIZONTAL:
                draw.rectangle([x, y - bar_length, x + self.bar_width, y],
                               fill=color)
                x += self.bar_width + self.bar_spacing
            else:
                draw.rectangle([x, y - self.bar_width, x + bar_length, y],
                               fill=color)
                y -= self.bar_width + self.bar_spacing

        return RenderImage.from_pil(canvas)
