from __future__ import annotations

import math
from typing import TypedDict

from PIL import Image, ImageDraw
from typing_extensions import Self, Unpack

from ..utils.squircle import draw_squircle
from .cacheable import Cacheable, cached, volatile
from .color import Color, Palette
from .image import RenderImage
from .properties import Space
from .textfont import TextFont
from .textstyle import *
from .textstyle.decoration import TextDecorationType


class _Metrics(TypedDict):
    """Internal type for storing text metrics."""
    ascent: int
    descent: int
    bbox: tuple[float, float, float, float]
    stroke_width: int
    padding: Space
    size: tuple[int, int]


class _RenderTextBlock(Cacheable):
    """Render text to an image in **one single line**.

    Refer to `TextStyle` for the attributes.
    """

    def __init__(
        self,
        text: str,
        font: FontFamily,
        size: AbsoluteSize,
        color: Color,
        stroke: TextStroke | None,
        decoration: TextDecoration | None,
        shading: TextShading | None,
        bold: bool,
        italic: bool,
        wrap: TextWrap,
    ) -> None:
        super().__init__()
        with volatile(self):
            self.text = text
            self.font = font
            self.size = size
            self.color = color
            self.stroke = stroke
            self.decoration = decoration
            self.shading = shading
            self.bold = bold
            self.italic = italic
            self.wrap = wrap

    @property
    def style(self) -> TextStyle:
        return TextStyle(font=self.font,
                         size=self.size,
                         color=self.color,
                         stroke=self.stroke,
                         decoration=self.decoration,
                         shading=self.shading,
                         bold=self.bold,
                         italic=self.italic,
                         wrap=self.wrap)

    @classmethod
    def of(
        cls,
        text: str,
        font: str | FontFamily,
        size: int | AbsoluteSize,
        *,
        color: Color = TextStyleDefaults.color,
        stroke: TextStroke | None = TextStyleDefaults.stroke,
        decoration: TextDecoration | None = TextStyleDefaults.decoration,
        shading: Color | TextShading | None = TextStyleDefaults.shading,
        bold: bool = TextStyleDefaults.bold,
        italic: bool = TextStyleDefaults.italic,
        wrap: TextWrap = TextStyleDefaults.wrap,
    ) -> Self:
        if isinstance(font, str):
            font = FontFamily.of(regular=font)
        if isinstance(shading, Color):
            shading = TextShading(shading)
        return cls(text, font, AbsoluteSize(size), color, stroke, decoration,
                   shading, bold, italic, wrap)

    def with_text(self, text: str) -> Self:
        return self.__class__.of(text, **enforce_minimal(self.style))

    def __getitem__(self, index_or_slice: int | slice) -> Self:
        return self.with_text(self.text[index_or_slice])

    @cached
    def render(self) -> RenderImage:
        # 1. 计算字体度量
        metrics = self._get_font_metrics()

        # 2. 创建文本画布
        canvas = Image.new("RGBA", metrics["size"], Palette.TRANSPARENT)
        draw = ImageDraw.Draw(canvas)

        # 3 & 4. 绘制文本和描边 / 绘制装饰线
        if self.decoration and self.decoration.layer == "under":
            # line under text
            self._draw_decorations(draw, metrics)

            self._draw_text_and_stroke(draw, metrics)
        else:
            # line over text
            self._draw_text_and_stroke(draw, metrics)

            self._draw_decorations(draw, metrics)

        # 5. 应用斜体变换
        canvas = self._apply_italic_transform(canvas)

        # 6. 应用着色背景
        if self.text and self.shading:
            canvas = self._apply_shading_background(canvas, self.shading)

        return RenderImage.from_pil(canvas)

    @cached
    def _get_font_metrics(self) -> _Metrics:
        """获取字体度量信息"""
        font_path, simulate_italic = self.font.resolve(self.bold, self.italic)
        font = TextFont.load_font(font_path, self.size)

        if self.stroke:
            stroke_width = self.stroke.width
        else:
            stroke_width = 0

        left, top, right, bottom = font.getbbox(self.text,
                                                mode="RGBA",
                                                stroke_width=stroke_width,
                                                anchor="ls")
        ascent, descent = font.getmetrics()

        # 处理基线校正和底边矫正
        match self.font.baseline_correction:
            case False:
                baseline_corr = 0
            case True:
                baseline_corr = math.ceil(
                    -TextFont.get_metrics(font_path, self.size).y_min)
            case int():
                baseline_corr = self.font.baseline_correction
            case _:
                assert False, "should not reach here"
        patch_b = TextFont.get_padding(font_path, self.size)

        # 边距
        if self.shading:
            # note: l, r, t, b
            padding = list(self.shading.padding.as_tuple())
        else:
            padding = [0, 0, 0, 0]
        padding[2] += baseline_corr
        padding[3] += patch_b
        temp_padding = Space.of(*padding)

        # 考虑斜体模拟需要的左边距
        height = ascent + descent + stroke_width * 2 + temp_padding.height
        if simulate_italic:
            pad_shear = int(self.font.shear * height)
        else:
            pad_shear = 0
        padding[0] += pad_shear

        width = math.ceil(right - left) + temp_padding.width + pad_shear
        return {
            "ascent": ascent,
            "descent": descent,
            "bbox": (left, top, right, bottom),
            "stroke_width": stroke_width,
            "padding": Space.of(*padding),
            "size": (width, height),
        }

    def _draw_text_and_stroke(
        self,
        draw: ImageDraw.ImageDraw,
        metrics: _Metrics,
    ) -> None:
        """绘制文本主体和描边"""
        font_path, _ = self.font.resolve(self.bold, self.italic)
        font = TextFont.load_font(font_path, self.size)

        # 计算起始位置
        x = metrics["stroke_width"] + metrics["padding"].left
        y = metrics["stroke_width"] + metrics["padding"].top

        # 设置颜色参数
        fill = self.color if not self.font.embedded_color else None

        stroke_params = {}
        if self.stroke:
            stroke_params = {
                "stroke_width": self.stroke.width,
                "stroke_fill": self.stroke.color
            }

        draw.text(xy=(x, y),
                  text=self.text,
                  fill=fill,
                  font=font,
                  embedded_color=self.font.embedded_color,
                  **stroke_params)

    def _draw_decorations(
        self,
        draw: ImageDraw.ImageDraw,
        metrics: _Metrics,
    ) -> None:
        """绘制文本装饰线"""
        if not self.decoration or not self.text:
            return

        thick = self.decoration.thickness
        if thick < 0:
            # infer thickness from height
            thick = math.ceil(max(self.height * self.font.thickness, 1))
        half_thick = thick / 2 + 1
        y_coords: list[float] = []
        # 计算各装饰线位置
        if TextDecorationType.UNDERLINE in self.decoration.type:
            y_coords.append(self.baseline + half_thick)
        if TextDecorationType.OVERLINE in self.decoration.type:
            # t is negative
            y_coords.append(self.baseline + metrics["bbox"][1])
        if TextDecorationType.LINE_THROUGH in self.decoration.type:
            y_coords.append(metrics["size"][1] / 2 + half_thick)

        # 绘制线条
        x0 = metrics["padding"].left
        x1 = metrics["size"][0] - metrics["padding"].right
        for y in y_coords:
            draw.line([(x0, y), (x1, y)], fill=self.color, width=thick)

    def _apply_italic_transform(self, canvas: Image.Image) -> Image.Image:
        """应用仿制斜体变换"""
        _, simulate_italic = self.font.resolve(self.bold, self.italic)
        if not simulate_italic:
            return canvas
        shear = self.font.shear
        return canvas.transform(canvas.size,
                                Image.Transform.AFFINE, (1, shear, 0, 0, 1, 0),
                                resample=Image.Resampling.BICUBIC)

    @classmethod
    def _apply_shading_background(cls, canvas: Image.Image,
                                  shading: TextShading) -> Image.Image:
        """应用着色背景"""
        if shading.rounded:
            sd = draw_squircle(canvas.width, canvas.height, shading.color)
        else:
            sd = Image.new("RGBA", (canvas.width, canvas.height),
                           shading.color)
        return Image.alpha_composite(sd, canvas)

    @property
    def baseline(self) -> int:
        """Distance from the top to the baseline of the text."""
        metrics = self._get_font_metrics()
        return (metrics["ascent"] + metrics["stroke_width"] +
                metrics["padding"].top)

    @property
    def width(self) -> int:
        return self._get_font_metrics()["size"][0]

    @property
    def height(self) -> int:
        return self._get_font_metrics()["size"][1]

    @staticmethod
    def get_size(text: str,
                 **kwargs: Unpack[MinimalTextStyle]) -> tuple[int, int]:
        obj = _RenderTextBlock.of(text, **kwargs)
        return obj.width, obj.height

    def __repr__(self) -> str:
        return (f"{self.__class__.__name__}({self.text!r}, "
                f"fontsize={self.size!r})")


class RenderText(_RenderTextBlock):

    def as_block(self) -> _RenderTextBlock:
        return _RenderTextBlock.of(self.text, **enforce_minimal(self.style))

    @property
    @cached
    def blocks(self) -> list[_RenderTextBlock]:
        if not self.font.fallbacks:
            return [self.as_block()]
        if not self.text:
            return [self.as_block()]
        dispatch_text_fonts: list[tuple[str, FontFamily]] = [("", self.font)]
        fonts = [self.font] + self.font.fallbacks
        for c in self.text:
            # find the font that supports the character
            for font in fonts:
                font_path, _ = font.resolve(self.bold, self.italic)
                if TextFont.supports_glyph(font_path, c):
                    break
            else:
                font = self.font
            # add the block
            last_text, last_font = dispatch_text_fonts[-1]
            if last_font is not font:
                dispatch_text_fonts.append((c, font))
            else:
                dispatch_text_fonts[-1] = (last_text + c, last_font)
        blocks = []
        for text, font in dispatch_text_fonts:
            if not text:
                continue
            style = enforce_minimal(self.style)
            if font is not self.font:
                style["font"] = font
                style["size"] = round(style["size"] * font.scale)
            style["shading"] = None  # apply shading after concat
            blocks.append(_RenderTextBlock.of(text, **style))
        return blocks

    @cached
    def render(self) -> RenderImage:
        rendered_blocks = [b.render() for b in self.blocks]
        result = RenderImage.concat_horizontal_baseline(
            rendered_blocks, [b.baseline for b in self.blocks])
        if self.text and self.shading:
            im = self._apply_shading_background(result.to_pil(), self.shading)
            return RenderImage.from_pil(im)
        return result

    @property
    def width(self) -> int:
        return sum(b.width for b in self.blocks)

    @property
    def height(self) -> int:
        return max((b.height for b in self.blocks), default=0)
