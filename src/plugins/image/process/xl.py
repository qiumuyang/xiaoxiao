import colorsys

import cv2
import numpy as np
from PIL import Image

from src.utils.render import Color, Container, Direction
from src.utils.render import Image as RImage

from .processor import ImageProcessor


class FourColorGrid(ImageProcessor):
    """Adjust image color to four colors to create a grid.

    Also known as "特大(XL)".
    """

    GREEN = "#0d8828"
    YELLOW = "#f7d916"
    RED = "#f6070a"
    BLUE = "#0d24b2"
    COLORS = [[YELLOW, RED], [BLUE, GREEN]]

    @classmethod
    def adjust_tint(cls,
                    image: Image.Image,
                    target_rgb: tuple[int, int, int],
                    saturation: int = 255) -> Image.Image:
        """
        将图像整体色调调整为任意 RGB 目标颜色。

        参数:
            saturation (int): 调整后的饱和度（0-255），默认最大
        """
        # 将目标 RGB 颜色转换为 HSV 颜色空间
        target_hsv = colorsys.rgb_to_hsv(*[x / 255.0 for x in target_rgb])
        target_hue = int(target_hsv[0] * 179)

        # Ensure saturation is within valid range
        saturation = np.clip(saturation, 0, 255)

        # Extract alpha channel if present
        a = image.getchannel("A") if "A" in image.getbands() else None

        # Convert image to HSV
        img_np = np.array(image.convert("RGB"))
        hsv = cv2.cvtColor(img_np, cv2.COLOR_RGB2HSV)
        h, s, v = cv2.split(hsv)

        # Modify hue and saturation
        h[:] = target_hue
        s[:] = saturation

        # Merge channels and convert back to RGB
        adjusted_hsv = cv2.merge([h, s, v])
        adjusted_rgb = cv2.cvtColor(adjusted_hsv, cv2.COLOR_HSV2RGB)

        # Convert back to PIL image
        result = Image.fromarray(adjusted_rgb, "RGB").convert("RGBA")
        if a is not None:
            result.putalpha(a)

        return result

    def process_frame(self, image: Image.Image, *args,
                      **kwargs) -> Image.Image:
        image = self.scale(image, max_size=(512, 512))
        rows = []
        for row in self.COLORS:
            cols = []
            for color_hex in row:
                color = Color.from_hex(color_hex).to_rgb()
                cols.append(RImage.from_image(self.adjust_tint(image, color)))
            rows.append(
                Container.from_children(cols, direction=Direction.HORIZONTAL))
        return Container.from_children(
            rows,
            direction=Direction.VERTICAL,
        ).render().to_pil()
