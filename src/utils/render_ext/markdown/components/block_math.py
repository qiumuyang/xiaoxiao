from src.utils.render import (Alignment, Color, Image, RenderObject, Space,
                              Stack, Text)
from src.utils.render.utils.squircle import draw_squircle

from ..proto import Context
from ..render import MarkdownRenderer
from ..style import OverrideStyle
from ..token import BlockMath
from .math_utils import render_equation


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

        try:
            image = render_equation(eq, style.size_block, color=color.as_hex())
        except ValueError as e:
            # error to Text
            code_style = self.master.style.code_block.style
            if isinstance(code_style.size, float):
                base_size = code_style.size
            else:
                base_size = self.master.style.text_size.main
            content = Text.from_style(e.args[0],
                                      code_style.with_size(base_size // 2),
                                      max_width=ctx.max_width)
            align_h = Alignment.START
        else:
            content = Image.from_image(image,
                                       padding=Space.of_side(
                                           0, style.size_block // 4))
            align_h = Alignment.CENTER
        squircle = Image.from_image(
            draw_squircle(ctx.max_width,
                          content.height,
                          fill=Color.from_hex(style.background),
                          n=6))
        return Stack.from_children(
            [squircle, content],
            horizontal_alignment=align_h,
            vertical_alignment=Alignment.CENTER,
        )
