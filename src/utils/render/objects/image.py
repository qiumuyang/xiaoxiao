from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from PIL import Image as PILImage
from typing_extensions import Self, Unpack, override

from ..base import (BaseStyle, Color, Interpolation, RenderImage, RenderObject,
                    volatile)
from ..utils import PathLike


class Image(RenderObject):
    """A RenderObject wrapping a RenderImage.

    Attributes:
        im: The wrapped RenderImage.

    Note:
        The wrapped RenderImage is set to be read-only to prevent
        accidental modification.
        If modification is necessary, use the modify context manager
        to ensure the cache is cleared.
    """

    def __init__(self, im: RenderImage, **kwargs: Unpack[BaseStyle]) -> None:
        super().__init__(**kwargs)
        with volatile(self):
            self.im = im
            self.im.base_im.setflags(write=False)

    @contextmanager
    def modify(self) -> Generator[None, None, None]:
        """Context manager that temporarily sets the wrapped RenderImage to be
        writable.
        """
        self.im.base_im.setflags(write=True)
        yield
        self.clear_cache()
        self.im.base_im.setflags(write=False)

    @classmethod
    def empty(cls, width: int, height: int, color: Color,
              **kwargs: Unpack[BaseStyle]) -> Image:
        return cls.from_image(RenderImage.empty(width, height, color),
                              **kwargs)

    @classmethod
    def from_file(
        cls,
        path: PathLike,
        resize: float | tuple[int, int] | None = None,
        **kwargs: Unpack[BaseStyle],
    ) -> Image:
        im = RenderImage.from_file(path)
        if resize is not None:
            if isinstance(resize, tuple):
                im = im.resize(*resize)
            else:
                im = im.resize(int(im.width * resize), int(im.height * resize))
        return Image(im, **kwargs)

    @classmethod
    def from_url(
        cls,
        url: str,
        resize: float | tuple[int, int] | None = None,
        **kwargs: Unpack[BaseStyle],
    ) -> Image:
        im = RenderImage.from_url(url)
        if resize is not None:
            if isinstance(resize, tuple):
                im = im.resize(*resize)
            else:
                im = im.resize(int(im.width * resize), int(im.height * resize))
        return Image(im, **kwargs)

    @classmethod
    def from_image(cls, im: RenderImage | PILImage.Image,
                   **kwargs: Unpack[BaseStyle]) -> Image:
        """Create a new Image from an existing RenderImage.

        Note:
            Copy is used to cut off the reference to the original RenderImage.
        """
        if isinstance(im, PILImage.Image):
            return Image(RenderImage.from_pil(im), **kwargs)
        return Image(im.copy(), **kwargs)

    @classmethod
    def from_color(cls, width: int, height: int, color: Color,
                   **kwargs: Unpack[BaseStyle]) -> Image:
        return Image(RenderImage.empty(width, height, color), **kwargs)

    @classmethod
    def horizontal_line(cls, length: int, width: int, color: Color,
                        **kwargs: Unpack[BaseStyle]) -> Image:
        return cls.from_color(length, width, color, **kwargs)

    @classmethod
    def vertical_line(cls, length: int, width: int, color: Color,
                      **kwargs: Unpack[BaseStyle]) -> Image:
        return cls.from_color(width, length, color, **kwargs)

    @property
    @override
    def content_width(self) -> int:
        return self.im.width

    @property
    @override
    def content_height(self) -> int:
        return self.im.height

    @override
    def render_content(self) -> RenderImage:
        return self.im

    def resize(self, width: int, height: int) -> Self:
        """Resize the wrapped RenderImage."""
        with self.modify():
            self.im.resize(width, height)
        return self

    def rescale(self, scale: float) -> Self:
        """Rescale the wrapped RenderImage."""
        with self.modify():
            self.im.rescale(scale)
        return self

    def thumbnail(
        self,
        width: int,
        height: int,
        interpolation: Interpolation = Interpolation.BILINEAR,
    ) -> Self:
        """Thumbnail the wrapped RenderImage."""
        with self.modify():
            self.im.thumbnail(width, height, interpolation)
        return self

    def cover(
        self,
        width: int,
        height: int,
        interpolation: Interpolation = Interpolation.BILINEAR,
    ) -> Self:
        """Cover the wrapped RenderImage."""
        with self.modify():
            self.im.cover(width, height, interpolation)
        return self
