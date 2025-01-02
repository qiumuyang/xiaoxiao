from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import orjson
from nonebot import get_bot
from nonebot.adapters.onebot.utils import b2s, f2s
from nonebot.adapters.onebot.v11 import Bot, Message
from nonebot.adapters.onebot.v11 import MessageSegment as _MessageSegment
from nonebot.log import logger
from PIL import Image
from typing_extensions import override

from .button import ButtonGroup


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
    ) -> "MessageSegment":
        if isinstance(image, Image.Image):
            io = BytesIO()
            image.save(io, format="PNG")
            io.seek(0)
            file = io
        else:
            file = image
        return cls(type="image",
                   data={
                       "file": f2s(file),
                       "type": type_,
                       "cache": b2s(cache),
                       "proxy": b2s(proxy),
                       "timeout": timeout,
                   })

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
            if not "url" in seg1.data or not "url" in seg2.data:
                return False
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

    @classmethod
    def from_onebot(cls, obseg: _MessageSegment) -> "MessageSegment":
        """Create a MessageSegment from a OneBot MessageSegment."""
        return cls(obseg.type, obseg.data)

    @classmethod
    def node_lagrange(
        cls,
        user_id: int,
        nickname: str,
        content: Message,
    ) -> "MessageSegment":
        return cls(type="node",
                   data={
                       "name": nickname,
                       "uin": str(user_id),
                       "content": content
                   })

    @classmethod
    def markdown(cls, content: str) -> "MessageSegment":
        inner = {"content": content}
        return cls(type="markdown",
                   data={"content": orjson.dumps(inner).decode()})

    @classmethod
    def longmsg(cls, id_: str) -> "MessageSegment":
        return cls(type="longmsg", data={"id": id_})

    @classmethod
    def keyboard(cls, buttons: ButtonGroup) -> "MessageSegment":
        return cls(type="keyboard", data={"content": buttons.dict()})

    def is_empty(self) -> bool:
        return self.type == "text" and not self.data["text"]

    def is_at(self) -> bool:
        return self.type == "at"

    def is_image(self) -> bool:
        return self.type == "image"

    def is_face(self) -> bool:
        return self.type == "face"

    def is_mface(self) -> bool:
        return self.type == "mface"

    def extract_text(self) -> str:
        if not self.is_text():
            raise ValueError("Not a text segment")
        return self.data["text"]

    def extract_text_args(self) -> list[str]:
        if not self.is_text():
            raise ValueError("Not a text segment")
        return [_.strip() for _ in self.data["text"].split(" ") if _.strip()]

    def extract_at(self) -> int:
        if not self.is_at():
            raise ValueError("Not an at segment")
        return int(self.data["qq"])

    def extract_url(self, force_http: bool = True) -> str:
        if "url" not in self.data:
            raise ValueError("Segment does not contain a URL")
        url = self.data["url"]
        if force_http:
            url = url.replace("https://", "http://")
        return url

    def extract_face(self) -> int:
        if not self.is_face():
            raise ValueError("Not a face segment")
        return int(self.data["id"])

    @classmethod
    def normalize(cls, message: Message) -> Message:
        """Normalize a message by removing empty segments."""
        segments = []
        for segment in message:
            if segment.type == "text" and not segment.data["text"]:
                continue
            segments.append(segment)
        return Message(segments)


class MessageExtension:

    @classmethod
    def get_bot(cls) -> Bot:
        bot = get_bot()
        if not isinstance(bot, Bot):
            raise ValueError("OneBot instance required")
        return bot

    @classmethod
    async def forward(
        cls,
        segments: list[MessageSegment],
        bot: Bot | None = None,
    ) -> Message:
        bot = bot or cls.get_bot()
        forward_id = await bot.call_api("send_forward_msg",
                                        messages=Message(segments))
        return Message(MessageSegment.forward(id_=forward_id))

    @classmethod
    async def markdown(
        cls,
        content: str,
        user_id: int,
        nickname: str,
        *,
        keyboard: ButtonGroup | None = None,
        bot: Bot | None = None,
    ) -> Message:
        bot = bot or cls.get_bot()
        markdown = MessageSegment.markdown(content)
        if keyboard:
            buttons = MessageSegment.keyboard(keyboard)
            message = markdown + buttons
        else:
            message = Message(markdown)
        node = MessageSegment.node_lagrange(user_id, nickname, message)
        forward_id = await bot.call_api("send_forward_msg",
                                        messages=Message(node))
        return Message(MessageSegment.longmsg(id_=forward_id))
