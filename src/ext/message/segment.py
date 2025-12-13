import shlex as shlex_
from enum import Enum
from io import BytesIO
from pathlib import Path
from typing import Any

import orjson
from nonebot import get_bot
from nonebot.adapters.onebot.utils import b2s, f2s
from nonebot.adapters.onebot.v11 import Bot, Message
from nonebot.adapters.onebot.v11 import MessageSegment as _MessageSegment
from PIL import Image
from typing_extensions import override

from src.utils.persistence import FileStorage

from .button import ButtonGroup


class MessageType(Enum):
    AT = "at"
    FACE = "face"
    IMAGE = "image"
    MFACE = "mface"
    REPLY = "reply"
    TEXT = "text"


class MessageSegment(_MessageSegment):

    @classmethod
    @override
    def image(  # type: ignore
        cls,
        image: str | bytes | BytesIO | Path | Image.Image,
        type_: str | None = None,
        summary: str | None = None,
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
        data = {
            "file": f2s(file),
            "type": type_,
            "cache": b2s(cache),
            "proxy": b2s(proxy),
            "timeout": timeout,
        }
        if summary:
            data["summary"] = f"[{summary}]"
        return cls(type="image", data=data)

    @classmethod
    def image_url(cls, url: str, filename: str) -> "MessageSegment":
        return cls(type="image", data={"url": url, "filename": filename})

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
        try:
            return Message(
                [cls._deserialize_segment(segment) for segment in data])
        except Exception as e:
            raise ValueError("Invalid data", data) from e

    @classmethod
    def _deserialize_segment(cls, segment: dict[str, Any]) -> _MessageSegment:

        if "type" not in segment or "data" not in segment:
            raise ValueError("Invalid message segment", segment)

        return _MessageSegment(segment["type"],
                               cls._deep_deserialize_data(segment["data"]))

    @classmethod
    def _deep_deserialize_data(cls, value: Any) -> Any:
        # dict → 递归处理
        if isinstance(value, dict):
            return {k: cls._deep_deserialize_data(v) for k, v in value.items()}

        # list → 递归处理，但不当成 message segment list
        if isinstance(value, list):
            return [cls._deep_deserialize_data(v) for v in value]

        # 其他 → 原样返回
        return value

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, _MessageSegment):
            return False
        return MessageSegment.equals(self, other)

    @classmethod
    def equals(cls, seg1: _MessageSegment, seg2: _MessageSegment) -> bool:
        """Add extra comparison for image segments."""
        if _MessageSegment.__eq__(seg1, seg2):
            return True
        if seg1.type == "image" and seg2.type == "image":
            return seg1.data.get("filename") == seg2.data.get("filename")
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
    def node_message(
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

    def extract_text_args(self,
                          shlex: bool = False,
                          quiet_errors: bool = False) -> list[str]:
        if not self.is_text():
            raise ValueError("Not a text segment")
        if not shlex:
            return self.data["text"].split()
        try:
            return shlex_.split(self.data["text"])
        except ValueError:
            if not quiet_errors:
                raise
            return []

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

    def extract_filename(self) -> str:
        if "filename" in self.data:
            return self.data["filename"]
        if "file" in self.data:
            return self.data["file"]
        if self.is_mface():
            return self.data["emoji_id"] + ".emoji"
        raise ValueError("Segment does not contain a filename")

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


class MessageCodec:
    """
    A codec for encoding and decoding Message objects using private Unicode characters.

    This class provides methods to convert Message objects (which contain various segment types)
    into a compact string representation with a symbol table, and vice versa.

    Attributes:
        PRIVATE_USE (int): The start of the Unicode Private Use Area (U+E000).
        PRIVATE_USE_END (int): The end of the Unicode Private Use Area (U+F8FF).

    Methods:
        encode(message: Message, start: int = 0) -> tuple[str, dict[str, _MessageSegment]]:

            Raises:
                ValueError: If the number of non-text segments exceeds the available
                           private use character range.

        decode(message: str, symbol_table: dict[str, _MessageSegment]) -> Message:

    """

    PRIVATE_USE = 0xE000
    PRIVATE_USE_END = 0xF8FF

    @classmethod
    def encode(cls,
               message: Message,
               start: int = 0) -> tuple[str, dict[str, _MessageSegment]]:
        """
        Encodes a Message object into a string and symbol table.

        Args:
            message: The Message object to encode.
            start: Optional starting offset for private use characters (default: 0).

        Returns:
            A tuple containing:
            - A string where text segments are preserved and other segments are replaced
                with private use Unicode characters.
            - A symbol table mapping private use characters to their corresponding segments.
        """
        text = []
        symbol_table = {}
        for segment in message:
            if segment.type == "text":
                text.append(segment.data["text"])
            elif cls.PRIVATE_USE + len(symbol_table) > cls.PRIVATE_USE_END:
                raise ValueError("Too many segments")
            else:
                char = chr(cls.PRIVATE_USE + len(symbol_table) + start)
                text.append(char)
                symbol_table[char] = segment
        return "".join(text), symbol_table

    @classmethod
    def decode(cls, message: str,
               symbol_table: dict[str, _MessageSegment]) -> Message:
        """
        Decodes a string and symbol table back into a Message object.

        Args:
            message: The encoded message string.
            symbol_table: The symbol table mapping private use characters to segments.

        Returns:
            A Message object reconstructed from the encoded string and symbol table.
        """
        segments = []
        text = ""
        for char in message:
            if char in symbol_table:
                if text:
                    segments.append(_MessageSegment.text(text))
                    text = ""
                segments.append(symbol_table[char])
            else:
                text += char
        if text:
            segments.append(_MessageSegment.text(text))
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
        """
        Example:
        ```python
            message = await MessageExtension.markdown(...)
            await bot.send_group_forward_msg(group_id=..., messages=message)
        ```
        """
        bot = bot or cls.get_bot()
        markdown = MessageSegment.markdown(content)
        if keyboard:
            buttons = MessageSegment.keyboard(keyboard)
            message = markdown + buttons
        else:
            message = Message(markdown)
        node = MessageSegment.node_message(user_id, nickname, message)
        forward_id = await bot.call_api("send_forward_msg",
                                        messages=Message(node))
        # return Message(MessageSegment.longmsg(id_=forward_id))
        return Message(
            MessageSegment.node_message(
                user_id=user_id,
                nickname=nickname,
                content=Message(MessageSegment.forward(id_=forward_id)),
            ))

    @classmethod
    async def replace_with_local_image(cls, message: Message) -> Message:
        storage = await FileStorage.get_instance()
        for i, seg in enumerate(message):
            segment = MessageSegment.from_onebot(seg)
            if segment.is_image():
                try:
                    data = await storage.load(
                        url=segment.extract_url(),
                        filename=segment.extract_filename())
                    if data is not None:
                        message[i] = MessageSegment.image(image=data)
                except Exception:
                    pass
        return message

    @classmethod
    def encode(
        cls,
        message: Message,
        start: int = 0,
    ) -> tuple[str, dict[str, _MessageSegment]]:
        return MessageCodec.encode(message, start)

    @classmethod
    def decode(
        cls,
        message: str,
        symbol_table: dict[str, _MessageSegment],
    ) -> Message:
        return MessageCodec.decode(message, symbol_table)

    @classmethod
    def discard(
        cls,
        message: Message,
        *discard_type: str | MessageType,
    ) -> Message:
        t = [
            t.value if isinstance(t, MessageType) else t for t in discard_type
        ]
        return Message([seg for seg in message if seg.type not in t])

    @classmethod
    def filter(
        cls,
        message: Message,
        *allow_type: str | MessageType,
    ) -> Message:
        t = [t.value if isinstance(t, MessageType) else t for t in allow_type]
        return Message([seg for seg in message if seg.type in t])

    @classmethod
    def fix_mface(cls, message: Message):
        # 部分表情(mface)会跟随一个同名文本，这里移除多余的文本
        if (len(message) == 2 and message[0].type == "mface"
                and message[1].type == "text"):
            mface, text = message
            if mface.data.get("summary", "") == text.data["text"]:
                return message[:1]
        return message
