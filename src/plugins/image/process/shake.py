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
    def generate_random_shake(cls, num_frames=10, amplitude=5):
        """
        Generate random (dx, dy) offsets for a jittery shake effect.
        """
        return [(np.random.randint(-amplitude, amplitude + 1),
                 np.random.randint(-amplitude, amplitude + 1))
                for _ in range(num_frames)]

    @classmethod
    def generate_smooth_shake(cls, num_frames=10, amplitude=5, frequency=2):
        """
        Generate smooth oscillating (dx, dy) offsets using a sine wave.
        """
        t = np.linspace(0, 2 * np.pi * frequency, num_frames)
        dx = (amplitude * np.sin(t)).astype(int)
        dy = (amplitude * np.cos(t)).astype(int)
        return list(zip(dx, dy))

    @classmethod
    def generate_perlin_shake(cls, num_frames=10, scale=0.1, amplitude=5):
        """
        Generate smooth, random shake offsets using Perlin noise.
        """
        from perlin_noise import PerlinNoise
        noise = PerlinNoise(octaves=1)
        t = np.linspace(0, num_frames * scale, num_frames)
        dx = (amplitude * np.array([noise(x) for x in t])).astype(int)
        dy = (amplitude * np.array([noise(x + 100)
                                    for x in t])).astype(int)  # Offset Y noise
        return list(zip(dx, dy))

    @staticmethod
    def create_motion_blur_kernel(angle, kernel_size=30):
        """
        Create a motion blur kernel in the given direction.

        angle: Motion direction in degrees.
        kernel_size: Strength of motion blur.
        """
        kernel = np.zeros((kernel_size, kernel_size))

        # Convert angle to radians
        theta = np.deg2rad(angle)

        # Compute start and end points of motion blur
        x0, y0 = kernel_size // 2, kernel_size // 2
        x1 = int(x0 + np.cos(theta) * (kernel_size // 2))
        y1 = int(y0 + np.sin(theta) * (kernel_size // 2))

        cv2.line(kernel, (x0, y0), (x1, y1), (1, ), thickness=1)
        kernel /= np.sum(kernel)  # Normalize

        return kernel

    @staticmethod
    def apply_directional_blur(image, prev_offset, cur_offset, max_blur=5):
        """
        Apply motion blur in the direction of movement.

        prev_offset: (dx_prev, dy_prev)
        cur_offset: (dx_cur, dy_cur)
        max_blur: Maximum blur intensity.
        """
        dx_prev, dy_prev = prev_offset
        dx_cur, dy_cur = cur_offset

        # Compute motion direction
        delta_dx = dx_cur - dx_prev
        delta_dy = dy_cur - dy_prev
        motion_magnitude = np.hypot(delta_dx, delta_dy)

        if motion_magnitude == 0:
            return image  # No motion, no blur

        # Compute angle in degrees
        angle = math.degrees(math.atan2(delta_dy, delta_dx))

        # Generate motion blur kernel
        blur_kernel = Shake.create_motion_blur_kernel(
            angle, kernel_size=int(motion_magnitude * max_blur / 10) + 1)

        # Apply blur using OpenCV
        blurred_image = cv2.filter2D(np.array(image), -1, blur_kernel)

        return Image.fromarray(blurred_image)

    @classmethod
    def apply_shake_with_blur(cls, image: Image.Image, offsets, index,
                              blur_intensity):
        """
        Apply a series of (dx, dy) offsets to an image.
        """
        fill = (255, 255, 255, 0) if image.mode == "RGBA" else (255, 255, 255)
        # translate
        offset = offsets[index]
        image = image.transform(image.size,
                                Image.Transform.AFFINE,
                                (1, 0, offset[0], 0, 1, offset[1]),
                                fillcolor=fill)
        # blur
        if index > 0 and blur_intensity > 0:
            image = cls.apply_directional_blur(image,
                                               offsets[index - 1],
                                               offset,
                                               max_blur=blur_intensity)
        return image

    def process(self, image: Image.Image, *args, **kwargs) -> BytesIO:
        method = self.generate_random_shake
        if self.is_gif(image):
            durations, frames = [], []
            for frame in self.gif_iter(image):
                duration = frame.info["duration"] or 100
                durations.append(duration)
                frames.append(frame)
        else:
            n_frames = 15
            durations = [100] * n_frames
            frames = [image] * n_frames

        shake_offsets = method(num_frames=len(frames) - 2,
                               amplitude=max(image.size) // 10)
        for i, _ in enumerate(shake_offsets, 1):
            frames[i] = self.apply_shake_with_blur(frames[i], shake_offsets,
                                                   i - 1, self.blur)
        # TODO: crop out of canvas
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
