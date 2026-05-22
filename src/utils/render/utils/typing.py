from __future__ import annotations

from pathlib import Path
from typing import Any, Generic, TypeVar

import numpy as np
import numpy.typing as npt

ImageMask = npt.NDArray[np.uint8] | npt.NDArray[np.bool_]
PathLike = str | Path

T = TypeVar("T")
D = TypeVar("D")

Flex = T | list[T] | None


class Undefined:
    _inst = None

    def __new__(cls) -> Undefined:
        if cls._inst is None:
            cls._inst = super().__new__(cls)
        return cls._inst

    def __repr__(self) -> str:
        return "Undefined"

    @staticmethod
    def default(value: T | Undefined, default: D) -> T | D:
        if isinstance(value, Undefined):
            return default
        return value


undefined = Undefined()


class cast(Generic[T]):
    def __new__(cls, value: Any) -> T:
        return value
