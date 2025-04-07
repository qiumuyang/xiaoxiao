from typing import cast

from mistletoe.block_token import Heading, SetextHeading

from src.utils.render import (Alignment, Color, Container, Direction, Image,
                              RenderObject, Space, Spacer)

from ..proto import Context
from ..render import MarkdownRenderer
from .span import SpanRenderer
from .utils.builder import Builder


@MarkdownRenderer.register(Heading)
@MarkdownRenderer.register(SetextHeading)
class HeadingRenderer:

    def __init__(self, master: MarkdownRenderer) -> None:
        self.master = master

    def render(
        self,
        token: Heading | SetextHeading,
        ctx: Context,
    ) -> RenderObject:
        level = token.level
        # 1. render content
        builder = Builder(ctx.style, max_width=ctx.max_width)
        heading_style = self.master.style.heading.level(level)
        with builder.style(f"h{level}", heading_style):
            builder = SpanRenderer.render(self.master, token, builder)
        font_size = cast(int, heading_style.get("size"))
        content = builder.build(
            max_width=ctx.max_width,
            spacing=self.master.style.line_spacing.get(font_size))
        # 2. render split line
        components = [content]
        margin_bottom = self.master.style.heading.margin_below(level)
        if line_offset := self.master.style.heading.line_offset(level):
            components.extend([
                Spacer.of(height=line_offset),
                Image.horizontal_line(
                    ctx.max_width,
                    width=1,
                    color=Color.from_hex(self.master.style.palette.break_line))
            ])
            margin_bottom -= line_offset
        # 3. assemble with margin
        return Container.from_children(components,
                                       alignment=Alignment.START,
                                       direction=Direction.VERTICAL,
                                       margin=Space.of(0, 0, 0, margin_bottom))
