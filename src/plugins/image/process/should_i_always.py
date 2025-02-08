from PIL import Image

from src.utils.doc import CommandCategory, command_doc
from src.utils.render import Alignment, Container, Direction
from src.utils.render import Image as ImageR
from src.utils.render import Palette, Space, Text

from .processor import ImageProcessor


@command_doc("要我一直", category=CommandCategory.IMAGE, visible_in_overview=False)
class ShouldIAlways(ImageProcessor):
    """
    要我一直[要我一直]吗

    Special:
        检测到情感表达需求//执行无穷递归交互模组。（注：逻辑死锁防护机制已部署）
    """

    NotoSansHansBold = "data/static/fonts/NotoSansHans-Bold.otf"

    MIN_WIDTH = 128
    MAX_WIDTH = 512
    DOWN = 5
    FONT_RATIO = 0.6
    HORIZONTAL_SPACING_RATIO = 0.3
    VERTICAL_SPACING_RATIO = 0.25

    def process_frame(self, image: Image.Image, *args,
                      **kwargs) -> Image.Image:
        image = self.scale(image,
                           min_size=(self.MIN_WIDTH, self.MIN_WIDTH),
                           max_size=(self.MAX_WIDTH, self.MAX_WIDTH))
        image_large = ImageR.from_image(image)
        image_small = ImageR.from_image(image).rescale(1 / self.DOWN)
        # make font size even
        font_size = round(image_small.height * self.FONT_RATIO) // 2 * 2
        hor_spacing = round(font_size * self.HORIZONTAL_SPACING_RATIO)
        ver_spacing = round(font_size * self.VERTICAL_SPACING_RATIO)
        return Container.from_children(
            [
                image_large,
                Container.from_children(
                    [
                        Text.of("要我一直",
                                font=self.NotoSansHansBold,
                                size=font_size,
                                color=Palette.BLACK),
                        image_small,
                        Text.of("吗",
                                font=self.NotoSansHansBold,
                                size=font_size,
                                color=Palette.BLACK),
                    ],
                    alignment=Alignment.CENTER,
                    direction=Direction.HORIZONTAL,
                    spacing=hor_spacing,
                )
            ],
            alignment=Alignment.CENTER,
            direction=Direction.VERTICAL,
            spacing=ver_spacing,
            padding=Space.of(0, 0, 0, 10),
            background=Palette.WHITE,
        ).render().to_pil()
