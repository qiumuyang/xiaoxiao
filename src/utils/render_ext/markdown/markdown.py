from typing_extensions import Unpack

from src.utils.render import (BaseStyle, BoxShadow, Color, Container,
                              RenderImage, RenderObject, Space, cached,
                              volatile)

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
            margin=Space.all(self.md_width // 20),
            background=self._background_color,
            decorations=[
                BoxShadow.of(blur_radius=91,
                             spread=4,
                             color=Color.of(0, 0, 0, 0.8))
            ],
        ).render()

    @property
    @cached
    def content_width(self) -> int:
        return self.render_content().width

    @property
    @cached
    def content_height(self) -> int:
        return self.render_content().height
