from io import BytesIO
from typing import Literal

from PIL import Image

from src.utils.auto_arg import Argument
from src.utils.doc import CommandCategory, command_doc

from .processor import ImageProcessor


@command_doc("大风车",
             aliases={"逆时针旋转"},
             category=CommandCategory.IMAGE,
             visible_in_overview=False)
class MultiRotate(ImageProcessor):
    """
    通过**90°旋转**生成动图

    Special:
        源石能源驱动模块启动//执行四象限90°相位循环。

    Usage:
        {MultiRotate.format_args()}

    Examples:
        {MultiRotate.format_example()}

    Note:
        - 非正方形图片会被裁剪或填充为正方形
    """

    TRANS = {
        "clockwise": Image.Transpose.ROTATE_270,
        "counterclockwise": Image.Transpose.ROTATE_90,
    }

    rps = Argument(4.0, range=(0.5, 40), positional=True, doc="旋转频率 (次/秒)")
    mode = Argument("crop",
                    choices=["crop", "pad"],
                    positional=True,
                    doc="非正方形图片处理方式")

    def __init__(self, direction: Literal["clockwise",
                                          "counterclockwise"]) -> None:
        super().__init__()
        self.direction = direction

    def process(
        self,
        image: Image.Image,
        rps: float,
        mode: Literal["crop", "pad"],
    ) -> BytesIO:
        state_duration = round(1000 / rps)
        if self.is_gif(image):
            durations, frames = [], []
            current_duration = 0
            current_state = 0
            rotates = 0
            while 1:
                for frame in self.gif_iter(image):
                    duration = frame.info["duration"] or 100
                    durations.append(duration)
                    frame = self.to_square(frame, mode=mode)  # type: ignore
                    if current_duration > state_duration:
                        current_state = (current_state + 1) % 4
                        current_duration -= state_duration
                        rotates += 1
                    if current_state > 0:
                        for _ in range(current_state):
                            frame = frame.transpose(self.TRANS[self.direction])
                    current_duration += duration
                    frames.append(frame)
                if rotates >= 4:
                    break
        else:
            # 4 frames: 0, 90, 180, 270
            image = self.to_square(image, mode=mode)  # type: ignore
            frames = [image]
            durations = [state_duration] * 4
            for _ in range(3):
                image = image.transpose(self.TRANS[self.direction])
                frames.append(image)
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


# for documentation purposes
command_doc("反向大风车",
            aliases={"顺时针旋转"},
            category=CommandCategory.IMAGE,
            visible_in_overview=False)(MultiRotate)
