from mistletoe.block_token import Paragraph

from src.utils.render import RenderObject, Space

from ..proto import Context
from ..render import MarkdownRenderer
from .span import SpanRenderer
from .utils.builder import Builder


@MarkdownRenderer.register(Paragraph)
class ParagraphRenderer:

    def __init__(self, master: MarkdownRenderer) -> None:
        self.master = master

    def render(self, token: Paragraph, ctx: Context) -> RenderObject:
        builder = Builder(default=ctx.style, max_width=ctx.max_width)
        builder = SpanRenderer.render(self.master, token, builder)
        return builder.build(max_width=ctx.max_width,
                             margin=Space.of(0, 0, 0,
                                             self.master.style.line_spacing))
