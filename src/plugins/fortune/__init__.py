from nonebot import on_command
from nonebot.adapters import Message
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, MessageEvent
from nonebot.params import CommandArg

from src.ext import MessageSegment
from src.ext.config import ConfigManager

from .config import FortuneConfig, RenderBackground
from .fortune import get_fortune
from .render import FortuneRender

matcher = on_command("今日运势",
                     aliases={"jrys"},
                     block=True,
                     force_whitespace=True)
set_bg = on_command("今日运势.背景",
                    aliases={"jrys.bg", "今日运势.bg", "jrys.背景"},
                    block=True,
                    force_whitespace=True)


@matcher.handle()
async def _(bot: Bot, event: MessageEvent):
    user_id = event.user_id
    bg = (await ConfigManager.get_user(user_id, FortuneConfig)).render_bg
    if isinstance(event, GroupMessageEvent):
        member = await bot.get_group_member_info(group_id=event.group_id,
                                                 user_id=user_id,
                                                 no_cache=True)
        user_name = member["card"] or member["nickname"] or str(user_id)
    else:
        user_name = event.sender.card or event.sender.nickname or str(user_id)
    fortune = get_fortune(user_id, user_name)
    image = await FortuneRender.render(fortune, background=bg)
    await matcher.finish(MessageSegment.image(image))


@set_bg.handle()
async def _(event: MessageEvent, arg: Message = CommandArg()):
    color = arg.extract_plain_text().strip()
    user_id = event.user_id
    cfg = await ConfigManager.get_user(user_id, FortuneConfig)
    mapping = {
        "白": RenderBackground.WHITE,
        "黑": RenderBackground.BLACK,
        "透明": RenderBackground.TRANSPARENT
    }
    if color not in mapping:
        await set_bg.finish("可选背景色：白/黑/透明")
    cfg.render_bg = mapping[color]
    await ConfigManager.set_user(user_id, cfg)
