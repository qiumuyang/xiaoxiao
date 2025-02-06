from __future__ import annotations

import math
from enum import Flag, auto

from PIL import Image, ImageDraw, ImageFont
from typing_extensions import Self

from ..utils import PathLike
from .cacheable import Cacheable, cached, volatile
from .color import Color, Palette
from .image import RenderImage
from .textfont import TextFont


class TextDecoration(Flag):
    NONE = 0
    UNDERLINE = auto()
    OVERLINE = auto()
    LINE_THROUGH = auto()


class RenderText(Cacheable):
    """Render text to an image in one single line.

    Attributes:
        text: text to render.
        font: font file path.
        size: font size.
        color: text color.
        stroke_width: width of stroke.
        stroke_color: color of stroke.
        decoration: text decoration. See `TextDecoration`.
        decoration_thickness: thickness of text decoration lines.
        shading: shading color of the text.
            Do not confuse with `RenderObject.background`.
        embedded_color: whether to use embedded color in the font.
        ymin_correction: whether to use yMin in font metrics
            for baseline correction.
        italic: whether to simulate italic by shearing the text.
    """

    SHEAR = 0.2

    def __init__(
        self,
        text: str,
        font: PathLike,
        size: int,
        color: Color = Palette.BLACK,
        stroke_width: int = 0,
        stroke_color: Color | None = None,
        decoration: TextDecoration = TextDecoration.NONE,
        decoration_thickness: int = -1,
        shading: Color = Palette.TRANSPARENT,
        embedded_color: bool = False,
        ymin_correction: bool = False,
        italic: bool = False,
    ) -> None:
        super().__init__()
        with volatile(self):
            self.text = text
            self.font = font
            self.size = size
            self.color = color
            self.stroke_width = stroke_width
            self.stroke_color = stroke_color
            self.decoration = decoration
            self.decoration_thickness = decoration_thickness
            self.shading = shading
            self.embedded_color = embedded_color
            self.ymin_correction = ymin_correction
            self.italic = italic

    @classmethod
    def of(
        cls,
        text: str,
        font: PathLike,
        size: int = 12,
        *,
        color: Color | None = None,
        stroke_width: int = 0,
        stroke_color: Color | None = None,
        decoration: TextDecoration = TextDecoration.NONE,
        decoration_thickness: int = -1,
        shading: Color = Palette.TRANSPARENT,
        background: Color = Palette.TRANSPARENT,
        embedded_color: bool = False,
        ymin_correction: bool = False,
        italic: bool = False,
    ) -> Self:
        """Create a `RenderText` instance with default values.

        If `color` is not specified, it will be automatically chosen
        from BLACK or WHITE based on the background color luminance.
        """
        if color is None:
            im_bg = RenderImage.empty(1, 1, background)
            im_sd = RenderImage.empty(1, 1, shading)
            r, g, b, _ = im_bg.paste(0, 0, im_sd).base_im[0, 0]
            luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
            color = Palette.WHITE if luminance < 128 else Palette.BLACK
        if decoration_thickness < 0:
            decoration_thickness = max(size // 10, 1)
        return cls(text, font, size, color, stroke_width, stroke_color,
                   decoration, decoration_thickness, shading, embedded_color,
                   ymin_correction, italic)

    @cached
    def render(self) -> RenderImage:
        font = ImageFont.truetype(str(self.font), self.size)
        # https://pillow.readthedocs.io/en/stable/handbook/text-anchors.html
        # 1. calculate font metrics and text bounding box
        l, t, r, _ = font.getbbox(self.text,
                                  mode="RGBA",
                                  stroke_width=self.stroke_width,
                                  anchor="ls")
        metrics = TextFont.get_metrics(str(self.font), self.size)
        pad_b = TextFont.get_padding(str(self.font), self.size)
        pad_t = math.ceil(-metrics.y_min) if self.ymin_correction else 0
        # ascent: distance from the top to the baseline
        # descent: distance from the baseline to the bottom
        #          (normally negative, but in Pillow it is positive)
        ascent, descent = font.getmetrics()
        width = math.ceil(r - l)
        height = ascent + descent + self.stroke_width * 2 + pad_t + pad_b
        # add padding to avoid overflow
        pad_l = int(self.SHEAR * height) if self.italic else 0
        # 2. draw text
        im = Image.new("RGBA", (width + pad_l, height), color=self.shading)
        draw = ImageDraw.Draw(im)
        draw.text(
            xy=(self.stroke_width + pad_l, self.stroke_width + pad_t),
            text=self.text,
            fill=self.color,
            font=font,
            stroke_width=self.stroke_width,
            stroke_fill=self.stroke_color,
            embedded_color=self.embedded_color,
        )
        # 3. draw decoration
        y_coords: list[float] = []
        thick = self.decoration_thickness
        half_thick = thick // 2 + 1
        if self.decoration & TextDecoration.UNDERLINE:
            y_coords.append(self.baseline + half_thick)
        if self.decoration & TextDecoration.OVERLINE:
            y_coords.append(ascent + t - half_thick)  # t < 0
        if self.decoration & TextDecoration.LINE_THROUGH:
            # deco_y.append((ascent + t + self.baseline) // 2 + half_thick)
            y_coords.append(height // 2 + half_thick)
        for y in y_coords:
            draw.line(
                xy=[(pad_l, y), (width, y)],
                fill=self.color,
                width=thick,
            )
        # 4. shear the image to simulate italic
        if self.italic:
            im = im.transform(
                (im.width, im.height),
                Image.Transform.AFFINE,
                (1, self.SHEAR, 0, 0, 1, 0),
                resample=Image.Resampling.BILINEAR,
                fillcolor=self.shading,
            )
        return RenderImage.from_pil(im)

    @property
    @cached
    def baseline(self) -> int:
        """Distance from the top to the baseline of the text."""
        font = ImageFont.truetype(str(self.font), self.size)
        ascent, _ = font.getmetrics()
        metrics = TextFont.get_metrics(str(self.font), self.size)
        pad = math.ceil(-metrics.y_min) if self.ymin_correction else 0
        return ascent + self.stroke_width + pad

    @property
    @cached
    def width(self) -> int:
        return self.calculate_size(self.font, self.size, self.text,
                                   self.stroke_width, self.italic,
                                   self.ymin_correction)[0]

    @property
    @cached
    def height(self) -> int:
        return self.calculate_size(self.font, self.size, self.text,
                                   self.stroke_width, self.italic,
                                   self.ymin_correction)[1]

    @classmethod
    def calculate_size(
        cls,
        font: PathLike,
        size: int,
        text: str,
        stroke: int,
        italic: bool,
        ymin_correction: bool = False,
    ) -> tuple[int, int]:
        font_ = ImageFont.truetype(str(font), size)
        # https://pillow.readthedocs.io/en/stable/handbook/text-anchors.html
        l, _, r, _ = font_.getbbox(text,
                                   mode="RGBA",
                                   stroke_width=stroke,
                                   anchor="ls")
        metrics = TextFont.get_metrics(str(font), size)
        pad_b = TextFont.get_padding(str(font), size)
        pad_t = math.ceil(-metrics.y_min) if ymin_correction else 0
        ascent, descent = font_.getmetrics()
        width = math.ceil(r - l)
        height = ascent + descent + stroke * 2 + pad_t + pad_b
        # add padding to avoid overflow
        pad_l = int(cls.SHEAR * height) if italic else 0
        return width + pad_l, height
