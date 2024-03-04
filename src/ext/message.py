from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from nonebot.adapters.onebot.v11 import Message
from nonebot.adapters.onebot.v11 import MessageSegment as _MessageSegment
from nonebot.log import logger
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

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, _MessageSegment):
            return False
        return MessageSegment.equals(self, other)

    @classmethod
    def equals(cls, seg1: _MessageSegment, seg2: _MessageSegment) -> bool:
        """Fixed version of comparing image segments."""
        if seg1 == seg2:
            return True
        if seg1.type == "image" and seg2.type == "image":
            url1 = urlparse(seg1.data["url"])
            url2 = urlparse(seg2.data["url"])
            # http://gchat.qpic.cn/gchatpic_new/<uid>/aaa-bbb-ccc/0?term=255
            path1 = url1.path.split("/")
            path2 = url2.path.split("/")
            if path1[-1] != "0" or path2[-1] != "0":
                logger.warning("Unexpected image url format: %s, %s", url1,
                               url2)
                return False
            cmp1 = path1[-2].split("-")[-1]
            cmp2 = path2[-2].split("-")[-1]
            return cmp1 == cmp2
        return False

    @classmethod
    def message_equals(cls, msg1: Message, msg2: Message) -> bool:
        if len(msg1) != len(msg2):
            return False
        for seg1, seg2 in zip(msg1, msg2):
            if not cls.equals(seg1, seg2):
                return False
        return True
