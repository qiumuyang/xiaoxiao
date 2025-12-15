from nonebot import get_bot
from nonebot.adapters.onebot.v11 import Bot, Message
from nonebot.adapters.onebot.v11 import MessageSegment as _MessageSegment

from src.ext.message.button import ButtonGroup
from src.ext.message.segment import MessageCodec, MessageSegment, MessageType
from src.utils.persistence import FileStorage


class MessageExtension:

    @classmethod
    def _get_bot(cls) -> Bot:
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
        bot = bot or cls._get_bot()
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
        bot = bot or cls._get_bot()
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
    def fix_mface(cls, message: Message) -> Message:
        # 部分表情(mface)会跟随一个同名文本，这里移除多余的文本
        if (len(message) == 2 and message[0].type == "mface"
                and message[1].type == "text"):
            mface, text = message
            if mface.data.get("summary", "") == text.data["text"]:
                return message[:1]
        return message
