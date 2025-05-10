from contextlib import asynccontextmanager
from typing import ClassVar, TypeVar, cast

from nonebot import get_driver
from pydantic import BaseModel
from typing_extensions import Self

from src.utils.log import logger_wrapper
from src.utils.persistence.mongo import Collection, Mongo

logger = logger_wrapper("Config")

T_Config = TypeVar("T_Config", bound="Config")


class Config(BaseModel):
    # the name users see / refer to
    user_friendly: ClassVar[str]
    # whether the feature can be disabled
    force_enable: ClassVar[bool] = False

    # whether the feature is enabled
    enabled: bool = True

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        ConfigManager.register(cls)

    @classmethod
    async def get(
        cls,
        *,
        user_id: int | None = None,
        group_id: int | None = None,
    ) -> Self:
        return await ConfigManager.get(cls, user_id=user_id, group_id=group_id)

    @classmethod
    async def set(
        cls,
        value: Self,
        *,
        user_id: int | None = None,
        group_id: int | None = None,
    ):
        await ConfigManager.set(value, user_id=user_id, group_id=group_id)

    @classmethod
    @asynccontextmanager
    async def edit(
        cls,
        *,
        user_id: int | None = None,
        group_id: int | None = None,
    ):
        cfg = await ConfigManager.get(cls, user_id=user_id, group_id=group_id)
        yield cfg
        await ConfigManager.set(cfg, user_id=user_id, group_id=group_id)


class StoreConfig(BaseModel):
    user_id: int | None
    group_id: int | None
    name: str
    config: Config


class ConfigManager:

    config: Collection[dict, StoreConfig] = Mongo.collection("config_v2")

    name_to_cfg: dict[str, type[Config]] = {}
    cfg_to_name: dict[type[Config], str] = {}
    user_friendly_to_cfg: dict[str, type[Config]] = {}

    @classmethod
    def config_name(cls, cfg: type[Config]) -> str:
        cls_name = cfg.__name__
        if not cls_name.endswith("Config"):
            raise ValueError("Config class name must end with 'Config'")
        name = cls_name.removesuffix("Config").lower()
        return name

    @classmethod
    def register(cls, cfg: type[Config]):
        """检查所有继承自 Config 的类，并将其注册到 ConfigManager 中。

        """
        if cfg in set(cls.name_to_cfg.values()):
            return
        name = cls.config_name(cfg)
        if name in cls.name_to_cfg:
            raise ValueError(f"Duplicate config name: {name}")
        if not hasattr(cfg, "user_friendly"):
            raise ValueError(f"Expected user_friendly classvar in {cfg}")
        if cfg.user_friendly in cls.user_friendly_to_cfg:
            raise ValueError(f"Duplicate user friendly name: "
                             f"{cfg.user_friendly}")
        cls.name_to_cfg[name] = cfg
        cls.cfg_to_name[cfg] = name
        cls.user_friendly_to_cfg[cfg.user_friendly] = cfg

    @classmethod
    async def get(
        cls,
        config: type[T_Config],
        *,
        user_id: int | None = None,
        group_id: int | None = None,
    ) -> T_Config:
        filter = {
            "name": cls.config_name(config),
            "user_id": user_id,
            "group_id": group_id,
        }
        result = await cls.config.find_one(filter)
        if result is not None:
            return cast(T_Config, result.config)
        return config()

    @classmethod
    async def set(
        cls,
        value: Config,
        *,
        user_id: int | None = None,
        group_id: int | None = None,
    ) -> None:
        await cls.config.update_one(
            {
                "name": cls.config_name(value.__class__),
                "user_id": user_id,
                "group_id": group_id,
            },
            {"$set": {
                "config": value.model_dump(mode="json")
            }},
            upsert=True,
        )


@get_driver().on_startup
async def _():
    await ConfigManager.config.collection.create_index(
        keys=[("user_id", 1), ("group_id", 1), ("name", 1)])

    cfg = " | ".join(c.__name__ for c in ConfigManager.cfg_to_name)
    logger.info(f"Registered {len(ConfigManager.name_to_cfg)} configs: "
                f"{cfg}")


@ConfigManager.config.deserialize()
def _(data: dict) -> StoreConfig:
    cls = ConfigManager.name_to_cfg[data["name"]]
    return StoreConfig(user_id=data["user_id"],
                       group_id=data["group_id"],
                       name=data["name"],
                       config=cls.model_validate(data["config"]))
