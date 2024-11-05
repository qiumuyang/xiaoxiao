"""
Fix fonts overshooting ascender.
"""

from copy import deepcopy
from dataclasses import dataclass

from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._h_e_a_d import table__h_e_a_d
from fontTools.ttLib.tables._h_h_e_a import table__h_h_e_a


@dataclass
class FontMetrics:
    ascent: float
    descent: float
    y_min: float  # distance from ascender to top of the glyph (negative)
    units_per_em: int


class TextFont:

    metrics: dict[str, FontMetrics] = {}

    @classmethod
    def init_font(cls, font_path: str) -> FontMetrics:
        if font_path not in cls.metrics:
            if font_path.endswith(".ttc"):
                font = TTFont(font_path, fontNumber=0)
            else:
                font = TTFont(font_path)
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
        return cls.metrics[font_path]

    @classmethod
    def get_metrics(cls, font_path: str, font_size: int) -> FontMetrics:
        cls.init_font(font_path)
        result = deepcopy(cls.metrics[font_path])
        result.ascent *= font_size / result.units_per_em
        result.descent *= font_size / result.units_per_em
        result.y_min *= font_size / result.units_per_em
        return result
