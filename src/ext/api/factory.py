from nonebot import get_bot

from src.utils.env import inject_env

from .base import API
from .impl.lagrange import LagrangeAPI
from .impl.llonebot import LLOneBotAPI


@inject_env()
class _APIFactory:

    BACKEND: str = "llonebot"  # or "lagrange"

    _instance: API | None = None

    @classmethod
    def get_instance(cls) -> API:
        if cls._instance is None:
            bot = get_bot()
            match cls.BACKEND.lower():
                case "llonebot":
                    cls._instance = LLOneBotAPI(bot)
                case "lagrange":
                    cls._instance = LagrangeAPI(bot)
                case _:
                    raise ValueError(f"Unsupported backend: {cls.BACKEND}")
        return cls._instance


def _get_api() -> API:
    return _APIFactory.get_instance()
