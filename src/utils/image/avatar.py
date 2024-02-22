from datetime import datetime, timedelta
from functools import lru_cache
from io import BytesIO

import requests
from PIL import Image


class Avatar:

    last_update = datetime.now()

    # set a short expire time to update in time
    EXPIRE = timedelta(minutes=5)
    MAX_SIZE = 64
    TIMEOUT = 5

    DEFAULT_COLOR = (255, 255, 255)
    DEFAULT_SIZE = (128, 128)

    GROUP_URL = "http://p.qlogo.cn/gh/{id}/{id}/0"
    USER_URL = "http://q1.qlogo.cn/g?b=qq&nk={id}&s=640"

    @staticmethod
    @lru_cache(maxsize=MAX_SIZE)
    def _fetch(url: str) -> Image.Image:
        try:
            resp = requests.get(url, timeout=Avatar.TIMEOUT)
            resp.raise_for_status()
            return Image.open(BytesIO(resp.content))
        except Exception as e:
            raise e

    @staticmethod
    def fetch(id: int,
              is_group: bool = False,
              default: Image.Image | None = None) -> Image.Image:
        if (datetime.now() - Avatar.last_update) > Avatar.EXPIRE:
            Avatar._fetch.cache_clear()
            Avatar.last_update = datetime.now()
        url = Avatar.GROUP_URL.format(
            id=id) if is_group else Avatar.USER_URL.format(id=id)
        try:
            avatar = Avatar._fetch(url)
        except:
            avatar = None
        if avatar is not None:
            return avatar
        return default or Image.new("RGB", Avatar.DEFAULT_SIZE,
                                    Avatar.DEFAULT_COLOR)

    @staticmethod
    def user(user_id: int, default: Image.Image | None = None) -> Image.Image:
        return Avatar.fetch(user_id, False, default)

    @staticmethod
    def group(group_id: int,
              default: Image.Image | None = None) -> Image.Image:
        return Avatar.fetch(group_id, True, default)
