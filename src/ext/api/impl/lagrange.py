from src.ext.message import MessageSegment

from ..base import API, ForwardMessage


class LagrangeAPI(API):

    async def set_emoji_reaction(self, group_id: int, message_id: int,
                                 emoji: str) -> None:
        await self.bot.set_group_reaction(group_id=group_id,
                                          message_id=message_id,
                                          code=emoji,
                                          is_add=True)

    async def unset_emoji_reaction(self, group_id: int, message_id: int,
                                   emoji: str) -> None:
        await self.bot.set_group_reaction(group_id=group_id,
                                          message_id=message_id,
                                          code=emoji,
                                          is_add=False)

    async def send_group_forward_msg(self, group_id: int,
                                     messages: list[ForwardMessage]) -> None:
        # the only difference between node_message and node_custom "uin" vs "user_id"
        # lagrange is now "user_id"
        await self.bot.send_group_forward_msg(
            group_id=group_id,
            messages=[MessageSegment.node_custom(**msg) for msg in messages],
        )
