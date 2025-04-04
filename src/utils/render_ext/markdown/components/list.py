from typing import NamedTuple, cast

from mistletoe.block_token import BlockToken, List, ListItem

from src.utils.render import (Alignment, Container, Direction, RenderObject,
                              Space)

from ..proto import Context
from ..render import MarkdownRenderer
from .utils.builder import Box, Builder


@MarkdownRenderer.register(List)
class ListRenderer:

    def __init__(self, master: MarkdownRenderer) -> None:
        self.master = master

    def render(self, token: List, ctx: Context) -> RenderObject:
        style = self.master.style.list
        children = token.children or []
        assert all(isinstance(item, ListItem) for item in children)
        items = [
            ListItemBuilder(self.master, item) for item in children
            if isinstance(item, ListItem)
        ]
        indent = round(style.indent_factor * self.master.style.unit)
        with ctx.temp(indent=ctx.indent + 1, max_width=ctx.max_width - indent):
            bullets = [
                Box(item.bullet(ctx, i, cast(int | None, token.start)),
                    width=indent,
                    alignment_horizontal=Alignment.END).build()
                for i, item in enumerate(items)
            ]
            contents = [item.content(ctx) for item in items]
        return Container.from_children(
            [
                Container.from_children(
                    [bullet, content],
                    direction=Direction.HORIZONTAL,
                    margin=Space.of(
                        0, 0, 0, 0 if i == len(bullets) -
                        1 else self.master.style.line_spacing))
                for i, (bullet, content) in enumerate(zip(bullets, contents))
            ],
            direction=Direction.VERTICAL,
        )


class ListItemResult(NamedTuple):
    bullet: RenderObject
    content: RenderObject


class ListItemBuilder:

    def __init__(
        self,
        master: MarkdownRenderer,
        item: ListItem,
    ) -> None:
        self.master = master
        self.item = item

    def bullet(self,
               ctx: Context,
               index: int,
               start: int | None = None) -> RenderObject:
        style = self.master.style.list
        is_ordered = start is not None
        if is_ordered:
            number = start + index if start is not None else index + 1
            bullet_text = style.ordered_bullet(ctx.indent - 1, number)
        else:
            bullet_text = style.unordered_bullet(ctx.indent - 1)
        builder = Builder(default=ctx.style, max_width=ctx.max_width)
        with builder.style("marker", style=style.bullet(is_ordered)):
            builder.text(bullet_text)
        space_between = round(style.bullet_margin_factor *
                              self.master.style.unit)
        return builder.build(margin=Space.of(0, space_between, 0, 0))

    def content(self, ctx: Context) -> RenderObject:
        objects: list[RenderObject] = []
        for child in self.item.children or []:
            if not isinstance(child, BlockToken):
                raise ValueError(f"Unexpected non-block token: {child}")
            objects.append(self.master._dispatch_render(child, ctx=ctx))
        return Container.from_children(objects, direction=Direction.VERTICAL)
