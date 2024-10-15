import os
from typing import get_args, get_origin


def _construct_parser(type):
    if get_origin(type) is list:
        vt = get_args(type)[0]
        return lambda v: [vt(_) for _ in v.split(",")]
    if get_origin(type) is dict:
        kt, vt = get_args(type)
        return lambda v: {
            kt(k): vt(v)
            for k, v in (pair.split(":") for pair in v.split(","))
        }
    return type


def inject_env(**types):

    def decorator(cls):
        for key, value_type in cls.__annotations__.items():
            if key.startswith("_"):
                continue
            env_value = os.getenv(key.upper(), None)
            if env_value is None:
                # check if value is set
                # if not, set None
                if not hasattr(cls, key):
                    setattr(cls, key, None)
                continue
            if key in types:
                value_type = types[key]
            value_type = _construct_parser(value_type)
            setattr(
                cls, key,
                value_type(env_value)
                if value_type != bool else env_value.lower() in {"true", "1"})
        return cls

    return decorator


if __name__ == "__main__":

    @inject_env()
    class Config:
        host: str = "localhost"
        ports: dict[int, int]
        names: list[str]

    print(Config.host, Config.ports, Config.names)
