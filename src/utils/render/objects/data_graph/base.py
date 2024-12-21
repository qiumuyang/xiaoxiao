from typing import Any, Protocol

from typing_extensions import Unpack

from ...base import BaseStyle, Color, RenderObject


class DataGraph(RenderObject):

    def __init__(
        self,
        data: list[float] | dict[Any, float] | list[int] | dict[Any, int],
        **kwargs: Unpack[BaseStyle],
    ):
        super().__init__(**kwargs)
        if not data:
            raise ValueError("Data must not be empty")
        self._data = data if isinstance(data, dict) else {
            i: v
            for i, v in enumerate(data)
        }
        self._max = max(self._data.values())
        self._min = min(self._data.values())

    @property
    def max(self) -> float:
        return self._max

    @property
    def min(self) -> float:
        return self._min

    @property
    def data(self) -> dict[Any, float] | dict[Any, int]:
        return self._data


class ColorPolicy(Protocol):

    def __call__(self, v: float, min: float, max: float) -> Color:
        ...
