from io import BytesIO

from nonebot import on_command
from nonebot.adapters.onebot.v11 import MessageEvent
from nonebot.adapters.onebot.v11.event import Reply
from nonebot.matcher import Matcher
from nonebot.typing import T_State
from PIL import Image

from src.ext import MessageSegment, ratelimit
from src.ext.on import on_reply
from src.utils.doc import CommandCategory, command_doc
from src.utils.persistence import FileStorage

from ..process import (Flip, FlipFlop, FourColorGrid, FourColorGridV2,
                       GrayScale, ImageProcessor, MultiRotate, Reflect,
                       Reverse, Shake, ShouldIAlways, Zoom)
from .share import driver, logger

image_procs = {
    "灰度": GrayScale(),
    "倒放": Reverse(),
    "翻转": Flip("vertical"),
    "镜像": Flip("horizontal"),
    "向左反射": Reflect("R2L"),
    ("憋不不憋", "向右反射"): Reflect("L2R"),
    "向上反射": Reflect("B2T"),
    "向下反射": Reflect("T2B"),
    "要我一直": ShouldIAlways(),
    "左右横跳": FlipFlop("horizontal"),
    ("大风车", "逆时针旋转"): MultiRotate("counterclockwise"),
    ("反向大风车", "顺时针旋转"): MultiRotate("clockwise"),
    "特大": FourColorGrid(),
    "特大2": FourColorGridV2(),
    ("抖动", "震动"): Shake(),
    "拉近": Zoom("in"),
    "拉远": Zoom("out"),
}


@command_doc("图片处理", category=CommandCategory.IMAGE, is_placeholder=True)
async def process_image_message(
    name: str,
    processor: ImageProcessor,
    matcher: Matcher,
    event: MessageEvent,
    state: T_State,
    storage: FileStorage,
):
    """
    对图片进行预设操作

    Special:
        加载莱茵生命影像重构协议//载入源石技艺驱动图形接口…

    Usage:
        <操作> <图片> [参数]     - 对图片进行目标操作
        `引用` <操作> [参数]     - 对*引用消息*中包含的图片进行目标操作
        可用的操作：{" | ".join(('`' + (x[0] if isinstance(x, tuple) else x) + '`')
                                  for x in image_procs)}

    Examples:
        >>> [图片]
        >>> [引用] {(lambda k: k[0] if isinstance(k, tuple) else k)(next(iter(image_procs)))}

    Notes:
        - 使用 `{cmdhelp} <操作>` 查看各操作的详细说明
    """
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
            filename = segment.extract_filename()
            data = await storage.load(url, filename)
            if data is None:
                continue
            image = Image.open(BytesIO(data))
            if not processor.supports(image):
                continue
            result = processor(image, *args)
            if result is not None:
                await matcher.finish(MessageSegment.image(result,
                                                          summary=name))


@driver.on_startup
async def register_process():
    storage = await FileStorage.get_instance()
    for name, processor in image_procs.items():
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
                await process_image_message(name, proc, matcher, event, state,
                                            storage)

            return _

        reply_matcher.handle()(fn(name[0], processor))
        cmd_matcher.handle()(fn(name[0], processor))

        logger.info(f"Registered image processor: {name}")
