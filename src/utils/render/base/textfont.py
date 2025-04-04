"""
Fix fonts overshooting ascender.
"""

import string
from copy import deepcopy
from dataclasses import dataclass
from functools import lru_cache, wraps
from typing import Any

from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._h_e_a_d import table__h_e_a_d
from fontTools.ttLib.tables._h_h_e_a import table__h_h_e_a
from PIL import Image, ImageDraw, ImageFont


@dataclass
class FontMetrics:
    ascent: float
    descent: float
    y_min: float  # distance from ascender to top of the glyph (negative)
    units_per_em: int


class TextFont:

    metrics: dict[str, FontMetrics] = {}
    cmaps: dict[str, Any] = {}

    @classmethod
    def init_font(cls, font_path: str):
        if font_path not in cls.metrics:
            if font_path.endswith(".ttc"):
                font = TTFont(font_path, fontNumber=0)
            else:
                font = TTFont(font_path)
            cmap = font["cmap"]
            hhea: table__h_h_e_a = font["hhea"]  # type: ignore
            head: table__h_e_a_d = font["head"]  # type: ignore
            ascent = hhea.ascent
            descent = hhea.descent
            units_per_em = head.unitsPerEm  # type: ignore
            if "glyf" in font:
                y_min = head.yMin
            else:
                # TODO: OTF check "CFF " table?
                y_min = 0
            cls.metrics[font_path] = FontMetrics(ascent, descent, y_min,
                                                 units_per_em)
            cls.cmaps[font_path] = cmap

    @classmethod
    def get_metrics(cls, font_path: str, font_size: float) -> FontMetrics:
        cls.init_font(font_path)
        result = deepcopy(cls.metrics[font_path])
        result.ascent *= font_size / result.units_per_em
        result.descent *= font_size / result.units_per_em
        result.y_min *= font_size / result.units_per_em
        return result

    @classmethod
    def supports_glyph(cls, font_path: str, glyph: str) -> bool:
        cls.init_font(font_path)
        for table in cls.cmaps[font_path].tables:
            if ord(glyph) in table.cmap.keys():
                return True
        return False

    @classmethod
    @wraps(ImageFont.truetype)
    @lru_cache()
    def load_font(cls, *args, **kwargs) -> ImageFont.FreeTypeFont:
        try:
            return ImageFont.truetype(*args, **kwargs)
        except OSError:
            raise ValueError(f"Font file not found: {kwargs['font']}")

    @classmethod
    @lru_cache()
    def get_padding(cls, font_path: str, font_size: float) -> int:
        """Calculate the padding needed to fix the overshooting ascender
        by rendering the font with and without the ascender and measuring
        the difference in height.

        It is a little bit hacky and inefficient, but it works.
        """
        font = cls.load_font(font_path, font_size)
        ascent, descent = font.getmetrics()
        text = string.ascii_letters
        width = round(font.getlength(text))
        height = ascent + descent
        im1 = Image.new("RGBA", (width, height), color=(255, 255, 255, 0))
        im2 = Image.new("RGBA", (width, height + 100),
                        color=(255, 255, 255, 0))
        draw1 = ImageDraw.Draw(im1)
        draw2 = ImageDraw.Draw(im2)
        draw1.text(xy=(0, 0), text=text, fill=(0, 0, 0), font=font)
        draw2.text(xy=(0, 0), text=text, fill=(0, 0, 0), font=font)
        bbox1 = im1.getbbox()
        bbox2 = im2.getbbox()
        assert bbox1 is not None
        assert bbox2 is not None
        return max(bbox2[3] - bbox1[3] + bbox1[1] - bbox2[1], 0)
