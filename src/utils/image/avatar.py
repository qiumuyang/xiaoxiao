from datetime import timedelta
from io import BytesIO
from pathlib import Path

from aiohttp import ClientSession, ClientTimeout
from async_lru import alru_cache
from PIL import Image

from src.ext import logger_wrapper
from src.utils.env import inject_env

logger = logger_wrapper(__name__)


@inject_env()
class Avatar:
    """A class to fetch QQ avatar images and maintain a cache of them."""

    GROUP_URL = "http://p.qlogo.cn/gh/{id}/{id}/0"
    USER_URL = "http://q1.qlogo.cn/g?b=qq&nk={id}&s=640"

    LOCAL_FALLBACK_DIR = "data/dynamic/avatar"
    GROUP_PATH = "group/{id}.png"
    USER_PATH = "user/{id}.png"

    avatar_timeout: float = 3.0

    _session: ClientSession | None = None

    @staticmethod
    @alru_cache(ttl=timedelta(minutes=5).total_seconds())
    async def _fetch(session: ClientSession, url: str) -> Image.Image:
        async with session.get(url) as resp:
            resp.raise_for_status()
            return Image.open(BytesIO(await resp.read()))

    @classmethod
    async def fetch(
        cls,
        id: int,
        is_group: bool = False,
        default: Image.Image | None = None,
    ) -> Image.Image | None:
        if cls._session is None:
            cls._session = ClientSession(timeout=ClientTimeout(
                total=cls.avatar_timeout))

        url = (cls.GROUP_URL if is_group else cls.USER_URL).format(id=id)
        file = Path(cls.LOCAL_FALLBACK_DIR) / (cls.GROUP_PATH if is_group else
                                               cls.USER_PATH).format(id=id)
        try:
            avatar = await cls._fetch(cls._session, url)
        except Exception as e:
            type_ = "User" if not is_group else "Group"
            logger.error(f"{type_} {id} avatar fetch failed", e)
            avatar = Image.open(file) if file.exists() else None
        else:
            file.parent.mkdir(parents=True, exist_ok=True)
            avatar.save(file)
        return avatar or default

    @staticmethod
    async def user(user_id: int,
                   default: Image.Image | None = None) -> Image.Image | None:
        return await Avatar.fetch(user_id, is_group=False, default=default)

    @staticmethod
    async def group(group_id: int,
                    default: Image.Image | None = None) -> Image.Image | None:
        return await Avatar.fetch(group_id, is_group=True, default=default)
