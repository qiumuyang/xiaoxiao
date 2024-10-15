from datetime import datetime
from types import UnionType
from typing import Any, get_args, get_origin


def serialize(obj: Any) -> Any:

    def _(obj: Any):
        if isinstance(obj, (int, float, str, bool, datetime)):
            return obj
        if isinstance(obj, dict):
            return {k: _(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_(v) for v in obj]
        return serialize(obj)

    if hasattr(obj, "__dict__"):
        return {
            k: _(v)
            for k, v in obj.__dict__.items() if not k.startswith("_")
        }
    if hasattr(obj, "__slots__"):
        return {
            k: _(getattr(obj, k))
            for k in obj.__slots__ if not k.startswith("_")
        }
    return obj  # give up


def deserialize(data: dict[str, Any], cls: type) -> Any:
    obj = object.__new__(cls)

    def _(v, t):
        if t in (int, float, str, bool, datetime, type(None)):
            return v
        if get_origin(t) is list:
            return [_(d, get_args(t)[0]) for d in v]
        if get_origin(t) is dict:
            return {k: _(v, get_args(t)[1]) for k, v in v.items()}
        if get_origin(t) is UnionType:
            for arg in get_args(t):
                try:
                    return _(v, arg)
                except:
                    pass
            raise ValueError(f"Cannot match {v} to {t}")
        return deserialize(v, t)

    for member_name, member_type in cls.__annotations__.items():
        if member_name not in data:
            setattr(obj, member_name, None)
        else:
            setattr(obj, member_name, _(data[member_name], member_type))
    return obj
