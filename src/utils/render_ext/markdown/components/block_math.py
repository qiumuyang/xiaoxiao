from src.utils.render import (Alignment, Color, Image, RenderObject, Space,
                              Stack)
from src.utils.render.utils.squircle import draw_squircle

from ..math import BlockMath, render_equation
from ..proto import Context
from ..render import MarkdownRenderer
from ..style import OverrideStyle


@MarkdownRenderer.register(BlockMath)
class BlockMathRenderer:

    def __init__(self, master: MarkdownRenderer) -> None:
        self.master = master

    def render(self, token: BlockMath, ctx: Context) -> RenderObject:
        style = self.master.style.math
        eq = f"${token.content.strip()}$"
        if (isinstance(ctx.style, OverrideStyle)
                and ctx.style.foreground_color is not None):
            color = ctx.style.foreground_color
        else:
            color = Color.from_hex(style.color)

        image = render_equation(eq, style.size_block, color=color.as_hex())
        content = Image.from_image(image,
                                   padding=Space.of_side(
                                       0, style.size_block // 4))
        squircle = Image.from_image(
            draw_squircle(ctx.max_width,
                          content.height,
                          fill=Color.from_hex(style.background),
                          n=6))
        return Stack.from_children(
            [squircle, content],
            horizontal_alignment=Alignment.CENTER,
            vertical_alignment=Alignment.CENTER,
        )
