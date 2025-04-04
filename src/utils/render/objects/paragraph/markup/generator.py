from contextlib import contextmanager
from typing import Callable, Iterable

from ....base import (AbsoluteSize, MinimalTextStyle, RelativeSize,
                      RenderImage, RenderObject, TextStyle, enforce_minimal)
from ..layout import Element, ImageElement, TextElement
from .parser import MarkupElement, MarkupNode, MarkupText


class OverridableStyle:

    def __init__(self, style: TextStyle):
        self._style = style.copy()
        self._default_size: AbsoluteSize | None = None
        if (size := style.get("size")) is not None:
            self.default_size = size

    @property
    def default_size(self) -> AbsoluteSize:
        if self._default_size is None:
            raise ValueError("Default size required")
        return self._default_size

    @default_size.setter
    def default_size(self, size: int | float | AbsoluteSize | RelativeSize):
        if self._default_size is not None:
            return
        if isinstance(size, float):
            raise ValueError("Default size must be absolute")
        self._default_size = AbsoluteSize(size)

    @contextmanager
    def override(self, style: TextStyle):
        original = self._style.copy()
        size_new = style.get("size", None)
        if isinstance(size_new, int):
            size = size_new
            self.default_size = size
        elif isinstance(size_new, float):
            size = round(size_new * self.default_size)
        else:
            size = None
        # update
        self._style.update(style)
        if size is not None:
            self._style["size"] = size
        yield
        # restore
        self._style = original

    @property
    def style(self) -> MinimalTextStyle:
        return enforce_minimal(self._style.copy())


class LayoutElementGenerator:

    def __init__(
        self,
        markup: list[MarkupNode],
        *,
        default: TextStyle,
        styles: dict[str, TextStyle],
        images: dict[str, RenderObject | RenderImage],
        unescape: Callable[[str], str] = lambda x: x,
    ) -> None:
        self.markup = markup
        self.default = default
        self.styles = styles
        self.images = images
        self.default = default
        self.unescape = unescape

    def layout(self) -> Iterable[Element]:
        for node in self.markup:
            yield from self._layout(node, OverridableStyle(self.default))

    def _layout(self, node: MarkupNode,
                style_stack: OverridableStyle) -> Iterable[Element]:
        match node:
            case MarkupText(content):
                yield TextElement.of(text=self.unescape(content),
                                     **style_stack.style)
            case MarkupElement(tag, children):
                if children is None:
                    image = self.images.get(tag, None)
                    if image is None:
                        raise ValueError(f"Unknown image name: {tag}")
                    if isinstance(image, RenderObject):
                        image = image.render()
                    yield ImageElement(image)
                else:
                    override_style = self.styles.get(tag, None)
                    if override_style is None:
                        raise ValueError(f"Unknown style name: {tag}")
                    with style_stack.override(override_style):
                        for child in children:
                            yield from self._layout(child, style_stack)
