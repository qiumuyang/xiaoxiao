from mistletoe.block_token import BlockToken, Quote

from src.utils.render import (Color, Container, Direction, Image, RenderObject,
                              Spacer, ZeroSpacingSpacer)

from ..proto import Context
from ..render import MarkdownRenderer


@MarkdownRenderer.register(Quote)
class QuoteRenderer:

    def __init__(self, master: MarkdownRenderer) -> None:
        self.master = master

    def render(self, token: Quote, ctx: Context) -> RenderObject:
        quote_style = self.master.style.quote
        bar_width = quote_style.bar_thick
        indent = round(quote_style.indent_factor * self.master.style.unit)
        # 1. render quoted content
        with ctx.temp(style=quote_style.style,
                      max_width=ctx.max_width - bar_width - indent):
            objects: list[RenderObject] = [
                ZeroSpacingSpacer.of(width=ctx.max_width)
            ]
            for child in token.children or []:
                if not isinstance(child, BlockToken):
                    raise ValueError(f"Unexpected non-block token: {child}")
                objects.append(self.master._dispatch_render(child, ctx=ctx))
            quoted_content = Container.from_children(
                objects,
                direction=Direction.VERTICAL,
                background=Color.from_hex(quote_style.background),
                spacing=self.master.style.spacing)
        # 2. render quote bar
        quote_bar = Image.vertical_line(quoted_content.height,
                                        bar_width,
                                        color=Color.from_hex(
                                            quote_style.bar_color))
        # 3. assemble
        return Container.from_children(
            [quote_bar, Spacer.of(width=indent), quoted_content],
            direction=Direction.HORIZONTAL)
