from nonebot import on_command
from nonebot.adapters import Message
from nonebot.adapters.onebot.v11 import Bot, MessageEvent
from nonebot.params import CommandArg

from src.ext import MessageSegment, get_user_name
from src.utils.doc import CommandCategory, command_doc

from .config import FortuneConfig, RenderBackground
from .fortune import get_fortune
from .render import FortuneRender

matcher = on_command("今日运势",
                     aliases={"jrys"},
                     block=True,
                     force_whitespace=True)


@matcher.handle()
@command_doc("今日运势", aliases={"jrys"}, category=CommandCategory.FUN)
async def _(bot: Bot, event: MessageEvent, arg: Message = CommandArg()):
    """
    进行今天的赛博算命

    Special:
        启动罗德岛占卜协议，检测到源石能流扰动…占卜回路同步率74.5%//
        多维运势参数采样中。

    Usage:
        {cmd}                    - 查看今日运势
        {cmd} `白|黑|透明|自动` - 设置背景色

    Notes:
        - 运势仅供娱乐，不具有实际参考价值
        - 头像获取失败时，可使用`更新头像`手动更新
    """
    user_id = event.user_id
    color = arg.extract_plain_text().strip()
    cfg = await FortuneConfig.get(user_id=user_id)

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
        await FortuneConfig.set(cfg, user_id=user_id)

    bg = cfg.render_bg
    user_name = await get_user_name(event)
    fortune = get_fortune(user_id, user_name)
    image = await FortuneRender.render(fortune, background=bg)
    await matcher.finish(MessageSegment.image(image, summary="今日运势"))
