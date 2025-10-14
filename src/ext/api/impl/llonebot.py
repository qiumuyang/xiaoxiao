from src.ext.message import MessageSegment

from ..base import API, ForwardMessage


class LLOneBotAPI(API):

    async def set_emoji_reaction(self, group_id: int, message_id: int,
                                 emoji: str) -> None:
        await self.bot.set_msg_emoji_like(message_id=message_id,
                                          emoji_id=int(emoji))

    async def unset_emoji_reaction(self, group_id: int, message_id: int,
                                   emoji: str) -> None:
        await self.bot.unset_msg_emoji_like(message_id=message_id,
                                            emoji_id=int(emoji))

    async def send_group_forward_msg(self, group_id: int,
                                     messages: list[ForwardMessage]) -> None:
        await self.bot.send_group_forward_msg(
            group_id=group_id,
            messages=[MessageSegment.node_message(**msg) for msg in messages],
        )
