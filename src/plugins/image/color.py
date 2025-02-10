from __future__ import annotations

import re
from typing import Iterable

from PIL.Image import Image as PILImage

from src.utils.render import *

color_string_pattern = re.compile(r"#(?:[0-9A-Fa-f]{6}|[0-9A-Fa-f]{3})")


def mix_with_black_white(color: Color, k: int = 3) -> list[Color]:
    linsp = [1.0 / (k + 1) * (i + 1) for i in range(k)]
    whites = [Palette.natural_blend(color, Palette.WHITE, i) for i in linsp]
    blacks = [
        Palette.natural_blend(color, Palette.BLACK, i / 2) for i in linsp
    ]
    whites.reverse()
    return whites + [color] + blacks


def render_single_color(color: Color, size: int = 40) -> RenderObject:
    color_hex = Text.of(
        color.as_hex(),
        font="data/static/fonts/Genshin.ttf",
        size=size // 8,
        background=color,
    )
    return Stack.from_children(
        children=[
            Spacer.of(size, size),
            color_hex,
        ],
        alignment=Alignment.CENTER,
        background=color,
    )


def render_color(*colors: Color) -> PILImage:
    children = []
    size = 80
    for color in colors:
        children.append(
            Container.from_children(
                [
                    render_single_color(c, size)
                    for c in mix_with_black_white(color)
                ],
                direction=Direction.HORIZONTAL,
            ))
        children.append(Spacer.of(height=size // 4))
    if len(children) > 0:
        children.pop()
    return Container.from_children(
        children,
        direction=Direction.VERTICAL,
        background=Color.of(242, 242, 242),
        padding=Space.all(size // 8),
    ).render().to_pil()


def random_color(k: int) -> Iterable[Color]:
    for _ in range(k):
        yield Color.rand()


def parse_color(s: str) -> Iterable[Color]:
    for color_hex in color_string_pattern.findall(s):
        try:
            yield Color.from_hex(color_hex)
        except ValueError:
            pass
