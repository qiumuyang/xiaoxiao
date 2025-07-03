import functools

from PIL import Image

from src.utils.doc import CommandCategory, command_doc
from src.utils.render import Alignment, Container, Direction
from src.utils.render import Image as ImageR
from src.utils.render import (Palette, Paragraph, RenderImage, RenderObject,
                              Space, Stack, TextStyle)

from .processor import ImageAvatarProcessor


@command_doc("我老婆", category=CommandCategory.IMAGE, visible_in_overview=False)
class ThisIsMyWaifu(ImageAvatarProcessor):
    """
    她是我老婆！！！

    Special:
        我就是县长！我就是马邦德！(大雾
    """

    NotoSansHansBold = "data/static/fonts/NotoSansHans-Bold.otf"

    MIN_WIDTH = 128
    MAX_WIDTH = 512
    FONT_RATIO = 0.2
    VSPACE_RATIO = 0.25

    TEMPLATE = ("如果你的老婆长这样\n"
                "<image:inline/>\n"
                "那么这就不是你的老婆\n"
                "这是我的老婆")

    POINT_RATIO = 0.6
    POINT_ASSET = "data/static/image/point.png"
    TEXT_POINT = "滚去找你\n自己的老婆去"

    @classmethod
    @functools.lru_cache(maxsize=32)
    def point_text(cls, font_size: int) -> RenderObject:
        return Paragraph.of(
            cls.TEXT_POINT,
            style=TextStyle(
                font=cls.NotoSansHansBold,
                size=font_size,
                color=Palette.BLACK,
            ),
            alignment=Alignment.CENTER,
        )

    @classmethod
    def make_avatar_point(cls, avatar: Image.Image, width: int,
                          font_size: int) -> RenderObject:
        text = cls.point_text(font_size)
        size = width - text.width - font_size // 2
        point = ImageR.from_file(cls.POINT_ASSET)
        point = point.rescale(cls.POINT_RATIO * size / point.width)
        pavatar = Stack.from_children(
            [ImageR.from_image(avatar).resize(size, size), point],
            vertical_alignment=Alignment.END,
            horizontal_alignment=Alignment.START)
        return Container.from_children(
            [text, pavatar],
            alignment=Alignment.CENTER,
            direction=Direction.HORIZONTAL,
            spacing=font_size // 2,
        )

    def _make_avatar_point(self, avatar: Image.Image, width: int,
                           font_size: int) -> RenderObject:
        ctx = self._context.get()
        if "avatar_point" not in ctx:
            ctx["avatar_point"] = self.make_avatar_point(
                avatar, width, font_size)
        return ctx["avatar_point"]

    def process_frame(self, image: Image.Image, avatar: Image.Image, *args,
                      **kwargs) -> Image.Image:
        image = self.scale(image,
                           min_size=(self.MIN_WIDTH, self.MIN_WIDTH),
                           max_size=(self.MAX_WIDTH, self.MAX_WIDTH))
        font_size = round(image.width * self.FONT_RATIO)
        vspace = round(font_size * self.VSPACE_RATIO)
        main = Paragraph.from_template(
            self.TEMPLATE,
            values={},
            images=dict(image=RenderImage.from_pil(image)),
            default=TextStyle(
                font=self.NotoSansHansBold,
                size=font_size,
                color=Palette.BLACK,
            ),
            alignment=Alignment.CENTER,
            line_spacing=vspace,
        )
        point = self._make_avatar_point(avatar, main.width, font_size)
        return Container.from_children(
            [main, point],
            alignment=Alignment.CENTER,
            direction=Direction.VERTICAL,
            spacing=vspace,
            padding=Space.all(10),
            background=Palette.WHITE,
        ).render().to_pil()
