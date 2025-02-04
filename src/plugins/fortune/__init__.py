from nonebot import on_command
from nonebot.adapters import Message
from nonebot.adapters.onebot.v11 import Bot, MessageEvent
from nonebot.params import CommandArg

from src.ext import MessageSegment, get_user_name
from src.ext.config import ConfigManager

from .config import FortuneConfig, RenderBackground
from .fortune import get_fortune
from .render import FortuneRender

matcher = on_command("今日运势",
                     aliases={"jrys"},
                     block=True,
                     force_whitespace=True)


@matcher.handle()
async def _(bot: Bot, event: MessageEvent, arg: Message = CommandArg()):
    user_id = event.user_id
    color = arg.extract_plain_text().strip()
    cfg = await ConfigManager.get_user(user_id, FortuneConfig)

    if color:
        mapping = {
            "白": RenderBackground.WHITE,
            "黑": RenderBackground.BLACK,
            "透明": RenderBackground.TRANSPARENT,
            "自动": RenderBackground.AUTO,
        }
        if color not in mapping:
            await matcher.finish("可选背景色：自动/白/黑/透明")
        cfg.render_bg = mapping[color]
        await ConfigManager.set_user(user_id, cfg)

    bg = cfg.render_bg
    user_name = await get_user_name(event)
    fortune = get_fortune(user_id, user_name)
    image = await FortuneRender.render(fortune, background=bg)
    await matcher.finish(MessageSegment.image(image, summary="今日运势"))
