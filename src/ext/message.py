from io import BytesIO
from pathlib import Path
from typing import Any

from nonebot.adapters.onebot.v11 import Message
from nonebot.adapters.onebot.v11 import MessageSegment as _MessageSegment
from PIL import Image
from typing_extensions import override


class MessageSegment(_MessageSegment):

    @classmethod
    @override
    def image(  # type: ignore
        cls,
        image: str | bytes | BytesIO | Path | Image.Image,
        type_: str | None = None,
        cache: bool = True,
        proxy: bool = True,
        timeout: int | None = None,
    ) -> _MessageSegment:
        if isinstance(image, Image.Image):
            io = BytesIO()
            image.save(io, format="PNG")
            io.seek(0)
            file = io
        else:
            file = image
        return _MessageSegment.image(file, type_, cache, proxy, timeout)

    @classmethod
    def serialize(cls, message: Message) -> list[dict[str, Any]]:
        return [{
            "type": segment.type,
            "data": {
                k: cls.serialize(v) if isinstance(v, Message) else v
                for k, v in segment.data.items()
            }
        } for segment in message]

    @classmethod
    def deserialize(cls, data: list[dict[str, Any]]) -> Message:
        return Message([
            _MessageSegment(
                segment["type"], {
                    k: cls.deserialize(v) if isinstance(v, list) else v
                    for k, v in segment["data"].items()
                }) for segment in data
        ])
