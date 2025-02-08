from mistletoe.block_token import BlockToken, Document

from src.utils.render import (Container, Direction, RenderObject,
                              ZeroSpacingSpacer)

from ..proto import Context
from ..render import MarkdownRenderer


@MarkdownRenderer.register(Document)
class DocumentRenderer:

    def __init__(self, master: MarkdownRenderer) -> None:
        self.master = master

    def render(self, token: Document, ctx: Context) -> RenderObject:
        objects: list[RenderObject] = [
            ZeroSpacingSpacer.of(width=ctx.max_width)
        ]
        for child in token.children or []:
            if not isinstance(child, BlockToken):
                raise ValueError(f"Unexpected non-block token: {child}")
            objects.append(self.master._dispatch_render(child, ctx=ctx))
        return Container.from_children(objects,
                                       direction=Direction.VERTICAL,
                                       background=self.master.style.background,
                                       spacing=self.master.style.spacing)
