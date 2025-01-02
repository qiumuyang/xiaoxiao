import asyncio
import collections
from datetime import timedelta
from io import BytesIO
from pathlib import Path
from typing import Deque, Literal

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
    GROUP_HEADER = {}
    # USER_URL = "http://q{k}.qlogo.cn/g?b=qq&nk={id}&s=640"
    USER_URL = "http://q.qlogo.cn/headimg_dl?dst_uin={id}&spec=640&img_type=png"
    USER_HEADER = {
        "accept":
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
        "cache-control": "no-cache",
        "pragma": "no-cache",
        "priority": "u=0, i",
        "sec-ch-ua":
        "\"Google Chrome\";v=\"129\", \"Not=A?Brand\";v=\"8\", \"Chromium\";v=\"129\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\"",
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "none",
        "sec-fetch-user": "?1",
        "upgrade-insecure-requests": "1"
    }

    LOCAL_FALLBACK_DIR = "data/dynamic/avatar"
    GROUP_PATH = "group/{id}.png"
    USER_PATH = "user/{id}.png"
    USER_CUSTOM_PATH = "user-custom/{id}.jpg"

    avatar_timeout: float
    avatar_concurrency: int

    _session: ClientSession | None = None

    _queue_handled = False
    _queue: Deque[tuple[int, bool]] = collections.deque()

    @classmethod
    def session(cls) -> ClientSession:
        if cls._session is None:
            cls._session = ClientSession(timeout=ClientTimeout(
                total=cls.avatar_timeout))
        return cls._session

    @staticmethod
    @alru_cache(ttl=timedelta(minutes=5).total_seconds())
    async def _fetch(session: ClientSession, url: str) -> Image.Image:
        async with session.get(url) as resp:
            resp.raise_for_status()
            return Image.open(BytesIO(await resp.read()))

    @classmethod
    async def _fetch_with_local(
        cls,
        session: ClientSession,
        id: int,
        is_group: bool = False,
    ) -> Image.Image | None:
        url = (cls.GROUP_URL if is_group else cls.USER_URL).format(id=id)
        file = Path(cls.LOCAL_FALLBACK_DIR) / (cls.GROUP_PATH if is_group else
                                               cls.USER_PATH).format(id=id)
        try:
            avatar = await cls._fetch(session, url)
        except Exception:
            cls._queue.append((id, is_group))
            avatar = Image.open(file) if file.exists() else None
        else:
            file.parent.mkdir(parents=True, exist_ok=True)
            avatar.save(file)
        return avatar

    @classmethod
    async def fetch(
        cls,
        id: int,
        is_group: bool = False,
        default: Image.Image | None = None,
    ) -> Image.Image | None:
        return await cls._fetch_with_local(cls.session(), id,
                                           is_group) or default

    @classmethod
    def load_custom(cls, user_id: int) -> Image.Image | None:
        file = Path(
            cls.LOCAL_FALLBACK_DIR) / cls.USER_CUSTOM_PATH.format(id=user_id)
        if file.exists():
            try:
                return Image.open(file)
            except Exception:
                file.unlink()
        return None

    @classmethod
    async def user(cls,
                   user_id: int,
                   default: Image.Image | None = None) -> Image.Image | None:
        await cls._start_queue()
        if avatar := cls.load_custom(user_id):
            return avatar
        return await Avatar.fetch(user_id, is_group=False, default=default)

    @classmethod
    async def group(cls,
                    group_id: int,
                    default: Image.Image | None = None) -> Image.Image | None:
        await cls._start_queue()
        return await Avatar.fetch(group_id, is_group=True, default=default)

    @classmethod
    async def update_user_avatar(
        cls,
        user_id: int,
        avatar: str | Image.Image | None,
    ) -> Literal["updated", "cache", "custom", "none"]:
        if avatar is None:
            # remove both
            for template in (cls.USER_CUSTOM_PATH, cls.USER_PATH):
                file = Path(
                    cls.LOCAL_FALLBACK_DIR) / template.format(id=user_id)
                if file.exists():
                    file.unlink()
                    return "cache" if template == cls.USER_PATH else "custom"
            return "none"
        else:
            file = Path(cls.LOCAL_FALLBACK_DIR) / cls.USER_CUSTOM_PATH.format(
                id=user_id)
            file.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(avatar, str):
                avatar = await cls._fetch(cls.session(), avatar)
            dim = min(avatar.size)
            l = (avatar.width - dim) // 2
            t = (avatar.height - dim) // 2
            r = l + dim
            b = t + dim
            cropped = avatar.crop((l, t, r, b))
            cropped.thumbnail((640, 640))
            cropped.convert("RGB").save(file)
            return "updated"

    @classmethod
    async def _start_queue(cls):
        if not cls._queue_handled:
            cls._queue_handled = True
            asyncio.create_task(cls._handle_queue())

    @classmethod
    async def _handle_queue(cls):
        async with ClientSession(timeout=ClientTimeout(60)) as session:
            while True:
                tasks = []
                ids = []
                while cls._queue and len(tasks) < cls.avatar_concurrency:
                    id, is_group = cls._queue.popleft()
                    ids.append(str(id))
                    tasks.append(
                        asyncio.create_task(
                            cls._fetch_with_local(session, id, is_group)))
                if tasks:
                    logger.info(
                        f"Fetching {len(tasks)} avatars at background ({' | '.join(ids)})"
                    )
                    await asyncio.gather(*tasks)
                await asyncio.sleep(1)
