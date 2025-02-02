import math
from io import BytesIO
from typing import Literal

import cv2
import numpy as np
from PIL import Image

from .processor import ImageProcessor


class Shake(ImageProcessor):
    """
    A class to generate and apply shake effects on an image.
    """

    AMP_RANGE = (0.05, 0.2)
    BLUR_RANGE = (0, 10)

    def __init__(
        self,
        amplitude: float = 0.1,
        mode: Literal["crop", "pad"] = "pad",
        blur: int = 5,
    ):
        self.amplitude = amplitude
        self.mode = mode
        self.blur = blur

    @classmethod
    def generate_shake_offsets(cls, num_frames: int, amplitude: int):
        """
        Generate random (dx, dy) offsets for a jittery shake effect.
        """
        return [(np.random.randint(-amplitude, amplitude + 1),
                 np.random.randint(-amplitude, amplitude + 1))
                for _ in range(num_frames)]

    @staticmethod
    def create_motion_blur_kernel(angle: float,
                                  kernel_size: int) -> np.ndarray:
        """
        Create a motion blur kernel for a given angle and kernel size.
        """
        kernel = np.zeros((kernel_size, kernel_size))
        theta = np.deg2rad(angle)
        x0, y0 = kernel_size // 2, kernel_size // 2
        x1 = int(x0 + np.cos(theta) * (kernel_size // 2))
        y1 = int(y0 + np.sin(theta) * (kernel_size // 2))
        cv2.line(kernel, (x0, y0), (x1, y1), (1, ), thickness=1)
        return kernel / np.sum(kernel)

    @staticmethod
    def apply_directional_blur(
        image: Image.Image,
        prev_offset: tuple[int, int],
        cur_offset: tuple[int, int],
        max_blur: int = 5,
    ) -> Image.Image:
        """
        Apply motion blur in the direction of the shake movement.
        """
        dx_prev, dy_prev = prev_offset
        dx_cur, dy_cur = cur_offset

        delta_dx = dx_cur - dx_prev
        delta_dy = dy_cur - dy_prev
        motion_magnitude = np.hypot(delta_dx, delta_dy)

        if motion_magnitude == 0:
            return image  # No motion, no blur

        angle = math.degrees(math.atan2(delta_dy, delta_dx))
        blur_kernel = Shake.create_motion_blur_kernel(
            angle, kernel_size=int(motion_magnitude * max_blur / 10) + 1)

        # Apply blur
        a = image.getchannel("A") if "A" in image.getbands() else None
        blurred_image = cv2.filter2D(np.array(image.convert("RGB")), -1,
                                     blur_kernel)
        blurred = Image.fromarray(blurred_image).convert("RGBA")
        if a:
            blurred.putalpha(a)
        return blurred

    def apply_shake_with_blur(
        self,
        image: Image.Image,
        offsets: list[tuple[int, int]],
        index: int,
        blur_intensity: int,
    ) -> Image.Image:
        """
        Apply a series of (dx, dy) offsets and blur to an image.
        """
        offset = offsets[index]
        fill = (255, 255, 255, 0) if image.mode == "RGBA" else (255, 255, 255)
        image = image.transform(image.size,
                                Image.Transform.AFFINE,
                                (1, 0, offset[0], 0, 1, offset[1]),
                                fillcolor=fill)

        # Apply blur if necessary
        if index > 0 and blur_intensity > 0:
            return self.apply_directional_blur(image,
                                               offsets[index - 1],
                                               offset,
                                               max_blur=blur_intensity)
        return image

    def process(self, image: Image.Image, *args, **kwargs) -> BytesIO:
        min_frames = 15
        default_frame_duration = 150
        if self.is_gif(image):
            frames, durations = [], []
            while len(frames) < min_frames:
                for frame in self.gif_iter(image):
                    durations.append(frame.info["duration"]
                                     or default_frame_duration)
                    frames.append(frame.convert("RGBA"))
        else:
            frames = [image.convert("RGBA")] * min_frames
            durations = [default_frame_duration] * min_frames

        shake_offsets = self.generate_shake_offsets(
            num_frames=len(frames) - 2, amplitude=max(image.size) // 10)
        for i in range(1, len(shake_offsets)):
            frames[i] = self.apply_shake_with_blur(frames[i], shake_offsets,
                                                   i - 1, self.blur)
        if self.mode == "crop":
            w, h = image.size
            lefts = [max(dx, 0) for dx, _ in shake_offsets]
            rights = [min(w + dx, w) for dx, _ in shake_offsets]
            tops = [max(dy, 0) for _, dy in shake_offsets]
            bottoms = [min(h + dy, h) for _, dy in shake_offsets]
            sx_min, sx_max = max(lefts), min(rights)
            sy_min, sy_max = max(tops), min(bottoms)
            if sx_min < sx_max and sy_min < sy_max:
                frames = [
                    frame.crop((sx_min, sy_min, sx_max, sy_max))
                    for frame in frames
                ]

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
        raise NotImplementedError()
