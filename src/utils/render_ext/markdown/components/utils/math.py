from src.utils.render import Alignment, RenderImage

from .katexsvg import KaTeX
from .katexsvg.png import svg_to_png


def render_math(
    equation: str,
    inline: bool = False,
    max_width: int | None = None,
    rescale: float = 0.2,
) -> RenderImage:
    katex = KaTeX()
    svg = katex.render_to_svg(equation, inline=inline)
    im = RenderImage.from_pil(svg_to_png(svg)).rescale(rescale)
    if not inline and max_width:
        im = RenderImage.concat_vertical(
            [im, RenderImage.empty(max_width, 0)], alignment=Alignment.CENTER)
    return im
