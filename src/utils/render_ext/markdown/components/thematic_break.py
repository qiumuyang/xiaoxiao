from mistletoe.block_token import ThematicBreak

from src.utils.render import Color, Image, RenderObject

from ..proto import Context
from ..render import MarkdownRenderer


@MarkdownRenderer.register(ThematicBreak)
class ThematicBreakRenderer:

    def __init__(self, master: MarkdownRenderer) -> None:
        self.master = master

    def render(
        self,
        token: ThematicBreak,
        ctx: Context,
    ) -> RenderObject:
        if token.children is not None:
            raise ValueError("Unexpected children in thematic break")
        style = self.master.style.thematic_break
        return Image.horizontal_line(ctx.max_width,
                                     style.thick,
                                     color=Color.from_hex(style.color))
