import json

from nonebot import on_command
from nonebot.adapters.onebot.v11.event import Reply
from nonebot.permission import SUPERUSER
from nonebot.typing import T_State

from src.ext.message.segment import MessageSegment
from src.ext.on import on_reply
from src.utils.persistence import FileStorage
from src.utils.render_ext.markdown import Markdown

check_message_repr = on_reply("repr", permission=SUPERUSER, block=True)
check_reply_repr = on_reply("reply", permission=SUPERUSER, block=True)
check_storage = on_command("storage",
                           force_whitespace=True,
                           permission=SUPERUSER,
                           block=True)


@check_message_repr.handle()
async def _(state: T_State):
    reply: Reply = state["reply"]
    content = reply.message
    message_json = json.dumps(MessageSegment.serialize(content),
                              ensure_ascii=False,
                              indent=2)
    markdown_content = f"```json\n{message_json}\n```"
    image = Markdown(text=markdown_content).render().to_pil()
    await check_message_repr.finish(MessageSegment.image(image))


@check_reply_repr.handle()
async def _(state: T_State):
    reply: Reply = state["reply"]
    reply_json = reply.model_dump_json(indent=2)
    markdown_content = f"```json\n{reply_json}\n```"
    image = Markdown(text=markdown_content).render().to_pil()
    await check_reply_repr.finish(MessageSegment.image(image))


@check_storage.handle()
async def _():

    def format_size(size_b: int) -> str:
        size_mb = size_b / 1024 / 1024
        if size_mb > 1024:
            size = f"{size_mb/1024:.2f} GB"
        else:
            size = f"{size_mb:.2f} MB"
        return size

    storage = await FileStorage.get_instance()
    stat = await storage.get_stats()
    if not stat:
        text = "Failed to get storage stats."
    else:
        header = ["Type", "Size", "Files"]
        sep = ["-" * len(s) for s in header]
        data = [
            [
                "Ephemeral",
                format_size(stat.ephemeral_file_size),
                str(stat.ephemeral_file_count)
            ],
            [
                "Persistent",
                format_size(stat.persistent_file_size),
                str(stat.persistent_file_count)
            ],
        ]
        text = "\n".join(
            ["| " + " | ".join(line) + " |" for line in [header, sep, *data]])

    im = Markdown(text).render().to_pil()
    await check_storage.finish(MessageSegment.image(im))
