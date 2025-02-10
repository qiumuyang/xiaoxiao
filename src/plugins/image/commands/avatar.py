from nonebot import on_command
from nonebot.adapters import Message
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, MessageEvent
from nonebot.adapters.onebot.v11.event import Reply
from nonebot.matcher import Matcher
from nonebot.params import CommandArg
from nonebot.typing import T_State

from src.ext import MessageSegment, get_group_member_name, ratelimit
from src.ext.on import on_reply
from src.utils.doc import CommandCategory, command_doc
from src.utils.image.avatar import Avatar, UpdateStatus

from ..group_member_avatar import RBQ, GroupMemberAvatar, LittleAngel, Mesugaki
from .share import driver, logger

avatar_update = on_command("更新头像",
                           aliases={"设置头像"},
                           block=True,
                           force_whitespace=True,
                           priority=2)
avatar_update_reply = on_reply("更新头像", block=True)

avatar_procs = {
    "小天使": LittleAngel,
    "RBQ": RBQ,
    "雌小鬼": Mesugaki,
}


@command_doc("群友头像", category=CommandCategory.IMAGE, is_placeholder=True)
async def response_avatar(
    name: str,
    avatar: type[GroupMemberAvatar],
    *,
    bot: Bot,
    matcher: Matcher,
    event: GroupMessageEvent,
):
    """
    基于群友头像生成图片

    Special:
        欢迎来到罗德岛基建会客室，请在此进行生物数据采集。

        ——访客头像已记录。

    Usage:
        <操作>         - 以自己的头像生成图片
        <操作> `@用户` - 以群友的头像生成图片
        可用的操作：{" | ".join(('`' + _ + '`'
                                  for _ in avatar_procs))}

    Notes:
        - 使用 `{cmdhelp} <操作>` 查看各操作的详细说明
    """
    user_id = event.user_id
    for seg in event.message:
        segment = MessageSegment.from_onebot(seg)
        if segment.is_at():
            user_id = segment.extract_at()
            break
    else:
        if event.is_tome():
            user_id = int(bot.self_id)

    nickname = await get_group_member_name(group_id=event.group_id,
                                           user_id=user_id)
    result = await avatar.render(user_id=user_id, nickname=nickname)
    await matcher.finish(MessageSegment.image(result, summary=name))


@driver.on_startup
async def register_avatar():
    rule = ratelimit("AVATAR", type="group", seconds=5)
    cmd = {
        "小天使": LittleAngel,
        "RBQ": RBQ,
        "雌小鬼": Mesugaki,
    }
    for name, avatar in cmd.items():
        matcher = on_command(name,
                             rule=rule,
                             block=True,
                             force_whitespace=True)

        def fn(name: str, avatar: type[GroupMemberAvatar]):
            """Create a closure to keep the avatar."""

            async def _(bot: Bot, matcher: Matcher, event: GroupMessageEvent):
                await response_avatar(name,
                                      avatar,
                                      bot=bot,
                                      matcher=matcher,
                                      event=event)

            return _

        matcher.handle()(fn(name, avatar))
        logger.info(f"Registered group avatar: {name}")


@avatar_update.handle()
@command_doc("更新头像", aliases={"设置头像"}, category=CommandCategory.IMAGE)
async def _(bot: Bot, event: MessageEvent, arg: Message = CommandArg()):
    """
    设置自定义头像/清除头像缓存

    Special:
        申请覆盖博士面容数据库…拒绝访问。

        执行备用方案：「伪装成伊芙利特的烤面包机维修报告」。

    Usage:
        {cmd}               - 清除自定义头像；不存在时清除头像缓存
        {cmd} `<图片>`      - 设置自定义头像
        `[引用消息]` {cmd}  - 设置自定义头像为*引用消息*中的图片
        设置自定义头像后，所有使用头像的指令都将使用自定义头像

    Notes:
        - 由于QQ的头像接口不稳定，采取本地缓存策略以保证可用
        - 若持续无法获取头像，可使用本指令手动设置头像
        - 除非手动清除，自定义头像将持续有效
    """
    for seg in arg:
        segment = MessageSegment.from_onebot(seg)
        if segment.is_image() or segment.is_mface():
            result = await Avatar.update(event.user_id, segment.extract_url())
            if result == UpdateStatus.UPDATED:
                await avatar_update.finish("头像已更新")
                break
    else:
        # remove avatar
        match await Avatar.update(event.user_id, None):
            case UpdateStatus.REMOVE_CACHE:
                await avatar_update.finish("已清除头像缓存")
            case UpdateStatus.REMOVE_CUSTOM:
                await avatar_update.finish("已清除自定义头像")


@avatar_update_reply.handle()
async def _(bot: Bot, event: MessageEvent, state: T_State):
    reply: Reply | None = state.get("reply")
    if not reply:
        return
    for seg in reply.message:
        segment = MessageSegment.from_onebot(seg)
        if segment.is_image() or segment.is_mface():
            result = await Avatar.update(event.user_id, segment.extract_url())
            if result == UpdateStatus.UPDATED:
                await avatar_update_reply.finish("头像已更新")
    # if no image, do nothing since implicit
