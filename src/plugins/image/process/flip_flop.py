from io import BytesIO
from typing import Literal

from PIL import Image

from src.utils.auto_arg import Argument
from src.utils.doc import CommandCategory, command_doc

from .processor import ImageProcessor


@command_doc("左右横跳", category=CommandCategory.IMAGE, visible_in_overview=False)
class FlipFlop(ImageProcessor):
    """
    通过**水平翻转**生成动图

    Special:
        警告！激活水平镜像同步协议//载入光学实验设备日志……多普勒效应模拟中。

    Usage:
        {FlipFlop.format_args()}

    Examples:
        {FlipFlop.format_example()}
    """

    TRANS = {
        "horizontal": Image.Transpose.FLIP_LEFT_RIGHT,
        "vertical": Image.Transpose.FLIP_TOP_BOTTOM,
    }

    fps = Argument(6.0, range=(0.5, 40), positional=True, doc="翻转频率 (次/秒)")

    def __init__(self, direction: Literal["horizontal", "vertical"]) -> None:
        super().__init__()
        self.direction = direction

    def process(self, image: Image.Image, fps: float) -> BytesIO:
        fps = min(max(0.5, fps), 40)
        state_duration = round(1000 / fps)
        if self.is_gif(image):
            durations, frames = [], []
            current_duration = 0
            current_state = 0
            flips = 0
            while 1:
                for frame in self.gif_iter(image):
                    # in some cases, the duration is 0,
                    # which causes the loop to run forever
                    duration = frame.info["duration"] or 100
                    durations.append(duration)
                    if current_duration >= state_duration:
                        current_state = 1 - current_state
                        current_duration -= state_duration
                        flips += 1
                    if current_state:
                        frame = frame.transpose(self.TRANS[self.direction])
                    current_duration += duration
                    frames.append(frame)
                if flips >= 2:
                    break
        else:
            # 2 frames: original and flipped
            has_flipped = image.transpose(self.TRANS[self.direction])
            frames = [image, has_flipped]
            durations = state_duration
        io = BytesIO()
        frames[0].save(io,
                       format="GIF",
                       save_all=True,
                       append_images=frames[1:],
                       duration=durations,
                       loop=0,
                       disposal=2)
        io.seek(0)
        return io

    def process_frame(self, image: Image.Image, *args,
                      **kwargs) -> Image.Image:
        raise NotImplementedError
