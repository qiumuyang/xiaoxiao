from nonebot import on_command
from nonebot.adapters import Message
from nonebot.adapters.onebot.v11.event import GroupMessageEvent, Reply
from nonebot.params import CommandArg
from nonebot.typing import T_State

from src.ext import MessageSegment, get_user_name
from src.ext.on import on_reply
from src.utils.doc import CommandCategory, command_doc
from src.utils.image.avatar import Avatar
from src.utils.message.receive import MessageData as RMD
from src.utils.message.receive import ReceivedMessageTracker as RMT
from src.utils.persistence import FileStorage
from src.utils.render_ext.message import MessageRender

from .color import parse_color, random_color, render_color
from .commands import avatar, markdown, process

# mark as used
__ = markdown
__ = avatar
__ = process

color_ = on_command("颜色", aliases={"查看颜色"}, block=True, force_whitespace=True)
image_url = on_reply(("链接", "url"), block=True)
quote = on_reply("入典", block=True)


@color_.handle()
@command_doc("颜色", aliases={"查看颜色"}, category=CommandCategory.IMAGE)
async def _(arg: Message = CommandArg()):
    """
    预览颜色及其色系

    Special:
        激活色彩预览接口…色谱采样数据流已启动…

        色系演算中……博士，请观察渐变效果。

    Usage:
        {cmd}                - 随机生成颜色
        {cmd} `<#RRGGBB>`... - 预览指定颜色
    """
    colors = list(parse_color(arg.extract_plain_text()))
    if not colors:
        colors = list(random_color(3))
    await color_.finish(MessageSegment.image(render_color(*colors)))


@image_url.handle()
@command_doc("链接", aliases={"url"}, category=CommandCategory.IMAGE)
async def _(state: T_State):
    """
    提取图片下载链接

    Special:
        激活影像捕获协议…正在检索未加密网络地址……执行莱茵生命数据锚点定位程序。

    Usage:
        `引用` {cmd} - 提取*引用消息*中的图片链接

    Notes:
        - 支持提取部分大表情链接
        - 如遇链接过期，可转发原消息重试
    """
    reply: Reply | None = state.get("reply")
    if not reply:
        return
    urls = []
    for seg in reply.message:
        segment = MessageSegment.from_onebot(seg)
        if segment.is_image() or segment.is_mface():
            urls.append(segment.extract_url(force_http=False))
    await image_url.finish(
        MessageSegment.reply(reply.message_id) +
        MessageSegment.text("\n".join(urls)))


@quote.handle()
@command_doc("入典", category=CommandCategory.IMAGE)
async def _(event: GroupMessageEvent, state: T_State):
    """
    生成消息图片

    Usage:
        `引用` {cmd} - 生成*引用消息*的图片
    """
    reply: Reply | None = state.get("reply")
    if not reply:
        return
    if not reply.sender.user_id:
        await quote.finish("无法获取发送者ID")
    avatar = await Avatar.user(reply.sender.user_id)
    name = await get_user_name(reply, group_id=event.group_id)
    msg = await MessageRender.create(avatar,
                                     reply.message,
                                     group_id=event.group_id,
                                     nickname=name)
    await quote.finish(MessageSegment.image(msg.render().to_pil()))


@RMT.on_receive
async def add_to_storage(_, data: RMD) -> None:
    # Since the download url expires quickly,
    # we keep a local cache of images in case later use.
    # message send is different from message receive
    storage = await FileStorage.get_instance()
    for seg in data.content:
        segment = MessageSegment.from_onebot(seg)
        if segment.is_image():
            await storage.load(segment.extract_url(),
                               segment.extract_filename())
