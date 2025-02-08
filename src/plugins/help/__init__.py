from pathlib import Path

from nonebot import on_command
from nonebot.adapters import Message
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent
from nonebot.params import CommandArg
from nonebot.permission import SUPERUSER
from PIL import Image

# from src.ext import MessageExtension
from src.ext import MessageSegment
from src.utils.doc import CommandMeta, DocManager
from src.utils.render_ext.markdown import Markdown

matcher = on_command("帮助",
                     aliases={"help"},
                     force_whitespace=True,
                     block=True,
                     permission=SUPERUSER)


class Wrapper:

    def export_markdown(self) -> str:
        return DocManager.overview()


def render_or_load(doc: CommandMeta | Wrapper, cmd: str):
    cache = Path("data/dynamic/doc-markdown")
    if not cache.exists():
        cache.mkdir(parents=True)
    file = cache / f"{cmd}.png"
    if file.exists():
        try:
            return Image.open(file)
        except:
            pass
    renderer = Markdown(doc.export_markdown())
    image = renderer.render().to_pil()
    image.save(file)
    return image


@matcher.handle()
async def _(bot: Bot, event: GroupMessageEvent, arg_: Message = CommandArg()):
    arg = arg_.extract_plain_text().strip()
    if not arg:
        doc = Wrapper()
        arg = "overview"
    else:
        doc = DocManager.get(arg)
    if doc:
        image = render_or_load(doc, arg)
        await matcher.finish(MessageSegment.image(image, summary=f"帮助-{arg}"))
        # message = await MessageExtension.markdown(doc.export_markdown(),
        #                                           int(bot.self_id),
        #                                           "鸮鸮",
        #                                           bot=bot)
        # await bot.send_group_forward_msg(messages=message,
        #                                  group_id=event.group_id)
        # await matcher.finish()
    else:
        await matcher.finish("未找到该命令或尚未编写帮助文档")
