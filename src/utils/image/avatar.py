import asyncio
from datetime import datetime, timedelta
from functools import lru_cache
from io import BytesIO

import aiohttp
from PIL import Image

from src.ext import logger_wrapper

logger = logger_wrapper(__name__)


class Avatar:
    """A class to fetch QQ avatar images and maintain a cache of them."""

    # set a short expire time to update in time
    EXPIRE = timedelta(minutes=5)
    MAX_CACHE_SIZE = 64
    TIMEOUT = 5

    DEFAULT_COLOR = (255, 255, 255)
    DEFAULT_SIZE = (128, 128)

    GROUP_URL = "http://p.qlogo.cn/gh/{id}/{id}/0"
    USER_URL = "http://q1.qlogo.cn/g?b=qq&nk={id}&s=640"

    _session: aiohttp.ClientSession | None = None
    last_update = datetime.min

    @staticmethod
    @lru_cache(maxsize=MAX_CACHE_SIZE)
    async def _fetch(url: str) -> Image.Image:
        # no error handling here
        # always return a valid Image to make sure cache is no None
        if Avatar._session is None:
            Avatar._session = aiohttp.ClientSession()
        async with Avatar._session.get(url) as resp:
            if resp.status != 200:
                raise ValueError(
                    f"Failed to fetch image from {url}. Status code: {resp.status}"
                )
            return Image.open(BytesIO(await resp.read()))

    @classmethod
    async def fetch(cls,
                    id: int,
                    is_group: bool = False,
                    default: Image.Image | None = None) -> Image.Image:
        await cls.maintain_cache()  # maintain cache every time fetch is called
        url = (cls.GROUP_URL if is_group else cls.USER_URL).format(id=id)
        try:
            avatar = await asyncio.wait_for(cls._fetch(url),
                                            timeout=cls.TIMEOUT)
        except Exception as e:
            type_ = "User" if not is_group else "Group"
            logger.error(f"{type_} {id} avatar fetch failed", e)
            avatar = None
        return avatar if avatar else default or Image.new(
            "RGB", cls.DEFAULT_SIZE, cls.DEFAULT_COLOR)

    @staticmethod
    async def user(user_id: int,
                   default: Image.Image | None = None) -> Image.Image:
        return await Avatar.fetch(user_id, is_group=False, default=default)

    @staticmethod
    async def group(group_id: int,
                    default: Image.Image | None = None) -> Image.Image:
        return await Avatar.fetch(group_id, is_group=True, default=default)

    @classmethod
    async def update_cache(cls):
        cls._fetch.cache_clear()
        if cls._session is not None:
            await cls._session.close()
        cls._session = aiohttp.ClientSession()

    @classmethod
    async def maintain_cache(cls):
        if (datetime.now() - cls.last_update) > cls.EXPIRE:
            await cls.update_cache()
            cls.last_update = datetime.now()
