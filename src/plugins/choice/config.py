from typing import ClassVar

from pydantic import Field

from src.ext.config import Config


class ChoiceConfig(Config):

    user_friendly: ClassVar[str] = "选择困难"

    shortcuts: list[str] = Field(default_factory=list)
