import io
from typing import cast

import cairosvg
from PIL import Image


def svg_to_png(
    svg: str,
    background: tuple[int, ...] | None = None,
    dpi: int = 800,
) -> Image.Image:
    png_bytes = cairosvg.svg2png(bytestring=svg.encode("utf-8"), dpi=dpi)
    buffer = io.BytesIO(cast(bytes, png_bytes))
    image = Image.open(buffer)
    image.load()
    if background is not None:
        image = image.convert("RGBA")
        bg = Image.new("RGBA", image.size, background)
        bg.alpha_composite(image)
        return bg
    return image
