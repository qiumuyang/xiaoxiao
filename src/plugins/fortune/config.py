from enum import IntEnum
from typing import ClassVar

from src.ext.config import Config


class RenderBackground(IntEnum):
    WHITE = 0
    BLACK = 1
    TRANSPARENT = 2


class FortuneConfig(Config):

    user_friendly: ClassVar[str] = "今日运势"

    render_bg: RenderBackground = RenderBackground.WHITE


__all__ = ["FortuneConfig", "RenderBackground"]
