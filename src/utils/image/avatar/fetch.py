import random
from datetime import timedelta
from enum import Enum
from io import BytesIO
from pathlib import Path

import requests
from aiohttp import ClientSession
from async_lru import alru_cache
from PIL import Image

from src.utils.env import inject_env


class UpdateStatus(Enum):
    UPDATED = 1
    REMOVE_CACHE = 2
    REMOVE_CUSTOM = 3
    FAIL = 0


@inject_env()
class Fetcher:
    """Handles synchronous fetching and saving of avatars."""

    GROUP_URL = "http://p.qlogo.cn/gh/{id}/{id}/0"
    USER_URL = "https://q.qlogo.cn/headimg_dl?dst_uin={id}&spec=640&img_type=png"
    USER_URL2 = "https://q{k}.qlogo.cn/g?b=qq&nk={id}&s=640"

    LOCAL_FALLBACK_DIR = "data/dynamic/avatar"
    GROUP_PATH = "group/{id}.png"
    USER_PATH = "user/{id}.png"
    USER_CUSTOM_PATH = "user-custom/{id}.jpg"

    avatar_timeout_long: float

    @classmethod
    def user_template(cls, user_id: int) -> str:
        k = random.randint(1, 5)
        if k == 5:
            return cls.USER_URL.format(id=user_id)
        return cls.USER_URL2.format(k=k, id=user_id)

    @classmethod
    def url(cls, id: int, is_group: bool) -> str:
        return cls.GROUP_URL.format(
            id=id) if is_group else cls.user_template(id)

    @classmethod
    def path(cls, id: int, is_group: bool) -> Path:
        return Path(cls.LOCAL_FALLBACK_DIR) / (cls.GROUP_PATH if is_group else
                                               cls.USER_PATH).format(id=id)

    @staticmethod
    @alru_cache(ttl=timedelta(minutes=5).total_seconds())
    async def afetch(session: ClientSession, url: str) -> Image.Image:
        async with session.get(url) as resp:
            resp.raise_for_status()
            return Image.open(BytesIO(await resp.read()))

    @classmethod
    def fetch(cls, url: str) -> Image.Image:
        resp = requests.get(url, timeout=cls.avatar_timeout_long)
        resp.raise_for_status()
        return Image.open(BytesIO(resp.content))

    @classmethod
    def fetch_avatar(
        cls,
        *,
        id: int,
        is_group: bool,
    ) -> Image.Image | None:
        """Fetches an avatar synchronously from the internet."""
        url = cls.url(id, is_group)
        file_path = cls.path(id, is_group)
        try:
            image = cls.fetch(url)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            image.save(file_path)
            return image
        except Exception as e:
            return None

    @classmethod
    async def fetch_avatar_async(
        cls,
        session: ClientSession,
        *,
        id: int,
        is_group: bool,
    ) -> Image.Image | None:
        """Fetches an avatar asynchronously from the internet."""
        url = cls.url(id, is_group)
        file_path = cls.path(id, is_group)
        try:
            img = await cls.afetch(session, url)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            img.save(file_path)
            return img
        except Exception as e:
            return None

    @classmethod
    def load_local_avatar(
        cls,
        *,
        id: int,
        is_group: bool,
    ) -> Image.Image | None:
        """Loads an avatar from local storage if available."""
        file_path = cls.path(id, is_group)
        if file_path.exists():
            try:
                return Image.open(file_path)
            except Exception as e:
                file_path.unlink()
        return None

    @classmethod
    def load_custom_avatar(
        cls,
        *,
        id: int,
    ) -> Image.Image | None:
        """Loads a custom avatar from local storage if available."""
        file_path = Path(
            cls.LOCAL_FALLBACK_DIR) / cls.USER_CUSTOM_PATH.format(id=id)
        if file_path.exists():
            try:
                return Image.open(file_path)
            except Exception as e:
                file_path.unlink()
        return None

    @classmethod
    async def update_user_avatar(
        cls,
        session: ClientSession | None,
        *,
        user_id: int,
        avatar: str | Image.Image | None,
    ) -> UpdateStatus:
        if avatar is None:
            # remove custom, then cache
            for template in (cls.USER_CUSTOM_PATH, cls.USER_PATH):
                file = Path(
                    cls.LOCAL_FALLBACK_DIR) / template.format(id=user_id)
                if file.exists():
                    file.unlink()
                return UpdateStatus.REMOVE_CACHE if template == cls.USER_PATH else UpdateStatus.REMOVE_CUSTOM
        else:
            file = Path(cls.LOCAL_FALLBACK_DIR) / cls.USER_CUSTOM_PATH.format(
                id=user_id)
            file.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(avatar, str):
                if session is None:
                    avatar = cls.fetch_avatar(id=user_id, is_group=False)
                else:
                    avatar = await cls.fetch_avatar_async(session,
                                                          id=user_id,
                                                          is_group=False)
                if avatar is None:
                    return UpdateStatus.FAIL
            # process custom image
            dim = min(avatar.size)
            l = (avatar.width - dim) // 2
            t = (avatar.height - dim) // 2
            r = l + dim
            b = t + dim
            crop = avatar.crop((l, t, r, b))
            crop.thumbnail((640, 640))
            crop.convert("RGB").save(file)
            return UpdateStatus.UPDATED
        return UpdateStatus.FAIL
