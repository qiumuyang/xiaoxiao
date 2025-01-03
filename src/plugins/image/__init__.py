from io import BytesIO

from aiohttp import ClientSession, ClientTimeout
from nonebot import get_driver, on_command
from nonebot.adapters import Message
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, MessageEvent
from nonebot.adapters.onebot.v11.event import Reply
from nonebot.matcher import Matcher
from nonebot.params import CommandArg
from nonebot.typing import T_State
from PIL import Image

from src.ext import MessageSegment, logger_wrapper, ratelimit
from src.ext.on import on_reply
from src.utils.image.avatar import Avatar, UpdateStatus

from .color import parse_color, random_color, render_color
from .group_member_avatar import RBQ, GroupMemberAvatar, LittleAngel, Mesugaki
from .process import (Flip, FlipFlop, GrayScale, ImageProcessor, Reflect,
                      Reverse, Rotate, ShouldIAlways)

logger = logger_wrapper("Image")
driver = get_driver()


async def process_image_message(
    processor: ImageProcessor,
    matcher: Matcher,
    event: MessageEvent,
    state: T_State,
    session: ClientSession,
):
    # extract text args
    arg_message = event.message
    args = [
        s.extract_text_args() for seg in arg_message
        if (s := MessageSegment.from_onebot(seg)) and s.is_text()
    ]
    args = [_ for a in args for arg in a if (_ := arg.strip())]
    # extract image
    if reply := state.get("reply"):
        reply: Reply | None
        im_message = reply.message
    else:
        im_message = event.message
    for seg in im_message:
        segment = MessageSegment.from_onebot(seg)
        if segment.is_image() or segment.is_mface():
            url = segment.extract_url()
            async with session.get(url) as resp:
                resp.raise_for_status()
                image = Image.open(BytesIO(await resp.read()))
                if not processor.supports(image):
                    continue
                result = processor.process(image, *args)
                if result is not None:
                    await matcher.finish(MessageSegment.image(result))


@driver.on_startup
async def register_process():
    session = ClientSession(timeout=ClientTimeout(total=10))
    processors = {
        "灰度": GrayScale(),
        "倒放": Reverse(),
        "翻转": Flip("vertical"),
        "镜像": Flip("horizontal"),
        "向左反射": Reflect("R2L"),
        ("向右反射", "憋不不憋"): Reflect("L2R"),
        "向上反射": Reflect("B2T"),
        "向下反射": Reflect("T2B"),
        "要我一直": ShouldIAlways(),
        "左右横跳": FlipFlop("horizontal"),
        ("顺时针旋转", "大风车"): Rotate("clockwise"),
        ("逆时针旋转", "反向大风车"): Rotate("counterclockwise"),
    }
    for name, processor in processors.items():
        if isinstance(name, str):
            name = (name, )

        rule = ratelimit("IMAGE_" + name[0], type="group", seconds=5)
        reply_matcher = on_reply(name, rule=rule, block=True)
        cmd_matcher = on_command(
            name[0],
            aliases=set(name[1:]),
            priority=2,  # lower than reply
            rule=rule,
            block=True)

        def fn(name: str, proc: ImageProcessor):
            """Create a closure to keep the processor."""

            async def _(matcher: Matcher, event: MessageEvent, state: T_State):
                await process_image_message(proc, matcher, event, state,
                                            session)

            return _

        reply_matcher.handle()(fn(name[0], processor))
        cmd_matcher.handle()(fn(name[0], processor))

        logger.info(f"Registered image processor: {name}")


async def response_avatar(
    avatar: type[GroupMemberAvatar],
    *,
    bot: Bot,
    matcher: Matcher,
    event: GroupMessageEvent,
):
    user_id = event.user_id
    for seg in event.message:
        segment = MessageSegment.from_onebot(seg)
        if segment.is_at():
            user_id = segment.extract_at()
            break
    else:
        if event.is_tome():
            user_id = int(bot.self_id)

    member = await bot.get_group_member_info(group_id=event.group_id,
                                             user_id=user_id)
    nickname = member["card"] or member["nickname"]
    result = await avatar.render(user_id=user_id, nickname=nickname)
    await matcher.finish(MessageSegment.image(result))


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
                await response_avatar(avatar,
                                      bot=bot,
                                      matcher=matcher,
                                      event=event)

            return _

        matcher.handle()(fn(name, avatar))
        logger.info(f"Registered group avatar: {name}")


color_ = on_command("颜色", block=True, force_whitespace=True)
image_url = on_reply(("链接", "url"), block=True)
avatar_update = on_command("更新头像",
                           block=True,
                           force_whitespace=True,
                           priority=2)
avatar_update_reply = on_reply("更新头像", block=True)


@color_.handle()
async def _(arg: Message = CommandArg()):
    colors = list(parse_color(arg.extract_plain_text()))
    if not colors:
        colors = list(random_color(3))
    await color_.finish(MessageSegment.image(render_color(*colors)))


@image_url.handle()
async def _(bot: Bot, event: MessageEvent, state: T_State):
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


@avatar_update.handle()
async def _(bot: Bot, event: MessageEvent, arg: Message = CommandArg()):
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
