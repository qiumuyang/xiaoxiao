from ....base import RenderImage
from .element import Element, Split


class ImageElement:

    def __init__(self, image: RenderImage):
        self.image = image

    @property
    def width(self) -> int:
        return self.image.width

    @property
    def height(self) -> int:
        return self.image.height

    @property
    def line_continue(self) -> bool:
        return False

    def split_at(self, width: int, next_width: int) -> Split:
        if self.width <= width:
            return Split(current=self, remaining=None)
        if self.width <= next_width:
            return Split(current=None, remaining=self)
        copy = self.image.copy()
        copy.thumbnail(max_width=next_width)
        return Split(current=None, remaining=ImageElement(copy))

    def render(self) -> RenderImage:
        return self.image

    def merge(self, other: Element) -> Element | None:
        # cannot merge with other elements
        return None
