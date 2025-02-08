from typing_extensions import Unpack

from src.utils.render import (BaseStyle, Border, Color, Container,
                              RenderObject, Space, cached, volatile)
from src.utils.render.base.image import RenderImage

from .render import MarkdownRenderer
from .style import MarkdownStyle


class Markdown(RenderObject):

    PAD_DIV = (20, 15)

    def __init__(self,
                 text: str,
                 style: MarkdownStyle = MarkdownStyle(),
                 content_width: int = 800,
                 **kwargs: Unpack[BaseStyle]) -> None:
        super().__init__(**kwargs)
        with volatile(self):
            self.text = text
            self.style = style
            self.md_width = content_width
        self.background = self._background_color
        self.padding = Space.all(30)

    @property
    def _background_color(self) -> Color:
        return Color.from_hex(self.style.bg_palette.main)

    @property
    def _border_color(self) -> Color:
        return Color.from_hex(self.style.palette.break_line)

    @property
    def _padding(self) -> Space:
        return Space.of_side(*(self.md_width // d for d in self.PAD_DIV))

    @cached
    def render_content(self) -> RenderImage:
        md = MarkdownRenderer(self.text,
                              self.style,
                              content_width=self.md_width)
        main = md.render()
        return Container.from_children(
            [main],
            padding=self._padding,
            border=Border.of(1, color=self._border_color),
            background=self._background_color,
        ).render()

    @property
    @cached
    def content_width(self) -> int:
        return self.render_content().width

    @property
    @cached
    def content_height(self) -> int:
        return self.render_content().height
