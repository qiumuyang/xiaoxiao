from dataclasses import dataclass, field
from enum import IntEnum
from typing import ClassVar, TypeVar, cast

from nonebot import get_driver
from pydantic import BaseModel

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


class ConfigType(IntEnum):
    GROUP = 1
    USER = 2


@dataclass
class StoreConfig:
    id: int
    type: ConfigType
    name: str
    config: Config = field(default_factory=Config)


class ConfigManager:

    config: Collection[dict, StoreConfig] = Mongo.collection("config")

    name_to_cfg: dict[str, type[Config]] = {}
    cfg_to_name: dict[type[Config], str] = {}
    user_friendly_to_cfg: dict[str, type[Config]] = {}

    PRIVATE = 0
    ANY_USER = 0

    @classmethod
    def config_name(cls, cfg: type[Config]) -> str:
        cls_name = cfg.__name__
        if not cls_name.endswith("Config"):
            raise ValueError("Config class name must end with 'Config'")
        name = cls_name.removesuffix("Config").lower()
        return name

    @classmethod
    def init(cls):
        """检查所有继承自 Config 的类，并将其注册到 ConfigManager 中。

        """
        queue = [Config]
        while queue:
            cfg = queue.pop()
            for sub_cfg in cfg.__subclasses__():
                queue.append(sub_cfg)
            if cfg is Config:
                continue

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
        id: int,
        type: ConfigType,
        config: type[T_Config],
    ) -> T_Config:
        name = cls.config_name(config)
        result = await cls.config.find_one({
            "id": id,
            "type": type,
            "name": name
        })
        if result is not None:
            return cast(T_Config, result.config)
        return config()

    @classmethod
    async def set(
        cls,
        id: int,
        type: ConfigType,
        value: Config,
    ) -> None:
        name = cls.config_name(value.__class__)
        await cls.config.update_one(
            {
                "id": id,
                "type": type,
                "name": name
            },
            {"$set": {
                "config": value.model_dump(mode="json")
            }},
            upsert=True,
        )

    @classmethod
    async def get_user(cls, user_id: int, config: type[T_Config]) -> T_Config:
        return await cls.get(user_id, ConfigType.USER, config)

    @classmethod
    async def set_user(cls, user_id: int, value: Config) -> None:
        await cls.set(user_id, ConfigType.USER, value)

    @classmethod
    async def get_group(cls, group_id: int,
                        config: type[T_Config]) -> T_Config:
        return await cls.get(group_id, ConfigType.GROUP, config)

    @classmethod
    async def set_group(cls, group_id: int, value: Config) -> None:
        await cls.set(group_id, ConfigType.GROUP, value)


@get_driver().on_startup
async def _():
    ConfigManager.init()
    await ConfigManager.config.collection.create_index(
        keys=[("id", 1), ("type", 1), ("name", 1)])

    cfg = " | ".join(c.__name__ for c in ConfigManager.cfg_to_name)
    logger.info(f"Registered {len(ConfigManager.name_to_cfg)} configs: "
                f"{cfg}")


@ConfigManager.config.serialize()
def serialize_config(cfg: StoreConfig):
    return {
        "id": cfg.id,
        "type": cfg.type,
        "name": cfg.name,
        "config": cfg.config.model_dump(mode="json"),
    }


@ConfigManager.config.deserialize()
def deserialize_config(data: dict):
    cls = ConfigManager.name_to_cfg[data["name"]]
    # since config class may be modified (inconsistent with the database),
    # we only load fields from database that are present in the class
    fields = [key for key in cls.model_fields]
    config = {
        key: value
        for key, value in data["config"].items() if key in fields
    }
    # warn the missing and duplicated fields
    name = (f"{'user' if data['type'] == ConfigType.USER else 'group'}"
            f"{data['id']}")
    miss = set(cls.model_fields) - set(data["config"].keys())
    if miss:
        logger.warning(f"Missing fields in {cls.__name__} ({name}): {miss}")
    dup = set(data["config"].keys()) - set(cls.model_fields)
    if dup:
        logger.warning(f"Duplicated fields in {cls.__name__} ({name}): {dup}")
    return StoreConfig(
        id=data["id"],
        type=ConfigType(data["type"]),
        name=data["name"],
        config=cls(**config),
    )
