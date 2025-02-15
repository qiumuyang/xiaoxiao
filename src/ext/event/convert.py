from typing import Generic, TypeVar

from nonebot.adapters.onebot.v11 import Event
from pydantic import ValidationError

T = TypeVar("T", bound=Event)


class EventConvert(Generic[T]):

    def __init__(self, type: type[T]) -> None:
        self.type = type

    async def __call__(self, event: Event) -> T | None:
        try:
            return self.type.model_validate(event.model_dump())
        except ValidationError as e:
            return None
