from datetime import timedelta
from io import BytesIO

from aiohttp import ClientSession, ClientTimeout
from async_lru import alru_cache
from PIL import Image

from src.ext import logger_wrapper

logger = logger_wrapper(__name__)


class Avatar:
    """A class to fetch QQ avatar images and maintain a cache of them."""

    GROUP_URL = "http://p.qlogo.cn/gh/{id}/{id}/0"
    USER_URL = "http://q1.qlogo.cn/g?b=qq&nk={id}&s=640"

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
            cls._session = ClientSession(timeout=ClientTimeout(total=30))

        url = (cls.GROUP_URL if is_group else cls.USER_URL).format(id=id)
        try:
            avatar = await cls._fetch(cls._session, url)
        except Exception as e:
            type_ = "User" if not is_group else "Group"
            logger.error(f"{type_} {id} avatar fetch failed", e)
            avatar = None
        return avatar or default

    @staticmethod
    async def user(user_id: int,
                   default: Image.Image | None = None) -> Image.Image | None:
        return await Avatar.fetch(user_id, is_group=False, default=default)

    @staticmethod
    async def group(group_id: int,
                    default: Image.Image | None = None) -> Image.Image | None:
        return await Avatar.fetch(group_id, is_group=True, default=default)
