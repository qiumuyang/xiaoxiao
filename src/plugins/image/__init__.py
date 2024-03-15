from io import BytesIO

from aiohttp import ClientSession, ClientTimeout
from nonebot import get_driver, on_command
from nonebot.adapters.onebot.v11 import MessageEvent
from nonebot.adapters.onebot.v11.event import Reply
from nonebot.matcher import Matcher
from nonebot.typing import T_State
from PIL import Image

from src.ext import MessageSegment, logger_wrapper, ratelimit
from src.ext.on import on_reply

from .process import *

logger = logger_wrapper("Image")


async def process_image_message(
    processor: ImageProcessor,
    matcher: Matcher,
    event: MessageEvent,
    state: T_State,
    session: ClientSession,
):
    if reply := state.get("reply"):
        reply: Reply | None
        message = reply.message
    else:
        message = event.message
    for seg in message:
        segment = MessageSegment.from_onebot(seg)
        if segment.is_image():
            url = segment.extract_image()
            async with session.get(url) as resp:
                resp.raise_for_status()
                image = Image.open(BytesIO(await resp.read()))
                if not processor.supports(image):
                    continue
                result = processor.process(image)
                await matcher.finish(MessageSegment.image(result))


@get_driver().on_startup
async def init():
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
    }
    for name, processor in processors.items():
        if isinstance(name, str):
            name = (name, )

        rule = ratelimit("IMAGE_" + name[0], type="group", seconds=5)
        reply_matcher = on_reply(name, rule=rule, block=True)
        cmd_matcher = on_command(name[0],
                                 aliases=set(name[1:]),
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
