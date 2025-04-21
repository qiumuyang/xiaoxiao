import random
from pathlib import Path

from src.utils.render import (Alignment, Direction, FixedContainer,
                              JustifyContent, Palette, Paragraph, TextStyle,
                              WaterfallContainer)

out = Path("render-test/container")
out.mkdir(parents=True, exist_ok=True)


def make_object(width: int, height: int):
    p = Paragraph.from_template_with_font_range(
        template="{width}x{height}",
        values=dict(width=width, height=height),
        default=TextStyle(font="data/static/fonts/arial.ttf",
                          size=16,
                          shading=Palette.WHITE),
        max_size=(width, height),
        font_size=(8, 16),
    )
    return FixedContainer.from_children(
        width,
        height, [p],
        alignment=Alignment.CENTER,
        direction=Direction.VERTICAL,
        justify_content=JustifyContent.SPACE_AROUND,
        background=random.choice(list(Palette.colors())))


def test_waterfall():
    width = 100
    children = [
        make_object(width=width, height=random.randint(40, 200))
        for _ in range(10)
    ]

    for k in range(2, 5):
        container = WaterfallContainer.from_children(
            children,
            alignment=Alignment.CENTER,
            columns=k,
            spacing=10,
            background=Palette.WHITE,
        )
        container.render().save(out / f"waterfall-{k}.png")

    WaterfallContainer.from_children(
        children[:3],
        alignment=Alignment.CENTER,
        columns=10,
        spacing=10,
        background=Palette.WHITE,
    ).render().save(out / "waterfall-10.png")
