from aiohttp import ClientSession, ClientTimeout
from nonebot import get_driver
from PIL import Image

from src.ext.log import logger_wrapper
from src.utils.env import inject_env

from .fetch import Fetcher, UpdateStatus
from .manager import Manager

logger = logger_wrapper(__name__)
driver = get_driver()


@inject_env()
class Avatar:

    default = Image.open("data/static/avatar/fail.png").resize((640, 640))

    avatar_timeout: float

    session: ClientSession

    @classmethod
    async def _shared(cls, id: int, is_group: bool,
                      default: Image.Image | None) -> Image.Image:
        if not is_group:
            if custom := Fetcher.load_custom_avatar(id=id):
                return custom
        image = await Fetcher.fetch_avatar_async(cls.session,
                                                 id=id,
                                                 is_group=is_group)
        if image is not None:
            return image
        # on failure: fetch at background, load local or return default
        Manager.enqueue(id=id, is_group=is_group)
        logger.warning(f"Failed to fetch {'group' if is_group else 'user'} "
                       f"{id} avatar.")
        cached = Fetcher.load_local_avatar(id=id, is_group=is_group)
        return cached or default or cls.default.copy()

    @classmethod
    async def user(
        cls,
        user_id: int,
        default: Image.Image | None = None,
    ) -> Image.Image:
        return await cls._shared(user_id, is_group=False, default=default)

    @classmethod
    async def group(
        cls,
        group_id: int,
        default: Image.Image | None = None,
    ) -> Image.Image:
        return await cls._shared(group_id, is_group=True, default=default)

    @classmethod
    async def update(cls, user_id: int, image: Image.Image | str | None):
        return await Fetcher.update_user_avatar(cls.session,
                                                user_id=user_id,
                                                avatar=image)

    @classmethod
    async def startup(cls):
        cls.session = ClientSession(timeout=ClientTimeout(
            total=cls.avatar_timeout))
        Manager.start_worker()

    @classmethod
    async def shutdown(cls):
        Manager.stop_worker()
        await cls.session.close()


@driver.on_startup
async def _():
    await Avatar.startup()


@driver.on_shutdown
async def _():
    await Avatar.shutdown()


__all__ = ["Avatar", "UpdateStatus"]
