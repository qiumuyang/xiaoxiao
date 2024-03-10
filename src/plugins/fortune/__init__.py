from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, MessageEvent

from src.ext import MessageSegment

from .fortune import get_fortune
from .render import FortuneRender

matcher = on_command("今日运势",
                     aliases={"jrys"},
                     block=True,
                     force_whitespace=True)


@matcher.handle()
async def _(bot: Bot, event: MessageEvent):
    user_id = event.user_id
    if isinstance(event, GroupMessageEvent):
        member = await bot.get_group_member_info(group_id=event.group_id,
                                                 user_id=user_id,
                                                 no_cache=True)
        user_name = member["card"] or member["nickname"] or str(user_id)
    else:
        user_name = event.sender.card or event.sender.nickname or str(user_id)
    fortune = get_fortune(user_id, user_name)
    image = await FortuneRender.render(fortune)
    await matcher.finish(MessageSegment.image(image))
