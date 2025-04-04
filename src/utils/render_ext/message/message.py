from typing import Literal

from PIL import Image
from typing_extensions import Unpack

from src.utils.render import (Alignment, BaseStyle, BoxSizing, CircleCrop,
                              Color, Container, Decorations, Direction)
from src.utils.render import Image as ImageObject
from src.utils.render import (Interpolation, Palette, Paragraph, RectCrop,
                              RenderImage, RenderObject, Space, Spacer,
                              TextStyle, cached, volatile)


class MessageRender:

    AVATAR_RADIUS = 28
    AVATAR_SIZE = 2 * AVATAR_RADIUS

    COLOR_BG = Color.from_hex("#F2F2F2")
    COLOR_NICKNAME = Color.from_hex("#A1A1A1")
    COLOR_CONTENT = Color.from_hex("#02071A")

    FONT = "data/static/fonts/MiSans-Regular.ttf"

    STYLE_NICKNAME = TextStyle(font=FONT, size=18, color=COLOR_NICKNAME)
    STYLE_CONTENT = TextStyle(font=FONT, size=24, color=COLOR_CONTENT)

    MAX_WIDTH = 360
    MAX_IMAGE_DIM = MAX_WIDTH
    MIN_IMAGE_DIM = MAX_IMAGE_DIM // 6
    SPACE_AVATAR_CONTENT = 14
    SPACE_NAME_CONTENT = 10
    CONTENT_ROUND_RADIUS = 15
    CONTENT_PADDING = Space.of_side(14, 16)
    CONTENT_DECO = Decorations.of(
        RectCrop.of(border_radius=CONTENT_ROUND_RADIUS,
                    box_sizing=BoxSizing.BORDER_BOX))
    PADDING = Space.of_side(26, 18)

    @classmethod
    def create(cls,
               avatar: str | Image.Image,
               content: str | Image.Image,
               nickname: str = "",
               alignment: Alignment = Alignment.START) -> RenderObject:
        if isinstance(avatar, str):
            avatar_ = ImageObject.from_url(avatar,
                                           decorations=[CircleCrop.of()])
        else:
            avatar_ = ImageObject.from_image(avatar,
                                             decorations=[CircleCrop.of()])
        avatar_.resize(cls.AVATAR_SIZE, cls.AVATAR_SIZE)
        nickname_ = None
        if nickname:
            nickname_ = Paragraph.of(nickname, style=cls.STYLE_NICKNAME)
        if isinstance(content, str):
            if "multimedia.nt.qq.com" in content:
                # image url
                content_ = ImageObject.from_url(content,
                                                decorations=cls.CONTENT_DECO)
            else:
                content_ = Paragraph.of(content,
                                        style=cls.STYLE_CONTENT,
                                        max_width=cls.MAX_WIDTH,
                                        line_spacing=4,
                                        background=Palette.WHITE,
                                        padding=cls.CONTENT_PADDING,
                                        decorations=cls.CONTENT_DECO)
        else:
            content_ = ImageObject.from_image(
                content,
                decorations=cls.CONTENT_DECO,
            )
        if isinstance(content_, ImageObject):
            content_.thumbnail(
                cls.MAX_IMAGE_DIM,
                cls.MAX_IMAGE_DIM,
                Interpolation.LANCZOS,
            ).cover(
                cls.MIN_IMAGE_DIM,
                cls.MIN_IMAGE_DIM,
                Interpolation.LANCZOS,
            )
            if content_.width > cls.MAX_IMAGE_DIM or content_.height > cls.MAX_IMAGE_DIM:
                content_.resize(min(content_.width, cls.MAX_IMAGE_DIM),
                                min(content_.height, cls.MAX_IMAGE_DIM))

        # assemble
        if nickname_:
            spacer = Spacer.of(height=cls.SPACE_NAME_CONTENT)
            components = [nickname_, spacer, content_]
        else:
            components = [content_]
        name_with_content = Container.from_children(
            components, alignment=alignment, direction=Direction.VERTICAL)
        items = [
            avatar_,
            Spacer.of(width=cls.SPACE_AVATAR_CONTENT), name_with_content
        ]
        if alignment is Alignment.END:
            items.reverse()
        return Container.from_children(
            items,
            alignment=Alignment.START,  # align top
            direction=Direction.HORIZONTAL,
            background=cls.COLOR_BG,
            padding=cls.PADDING)


class Message(RenderObject):

    def __init__(self,
                 avatar: str | Image.Image,
                 content: str | Image.Image,
                 nickname: str = "",
                 alignment: Alignment
                 | Literal["start", "end"] = Alignment.START,
                 **kwargs: Unpack[BaseStyle]):
        super().__init__(**kwargs)
        with volatile(self):
            self.avatar_obj = avatar
            self.content = content
            self.nickname_obj = nickname
            match alignment:
                case "start":
                    self.alignment = Alignment.START
                case "end":
                    self.alignment = Alignment.END
                case _:
                    assert isinstance(alignment, Alignment)
                    self.alignment = alignment

    @property
    @cached
    def content_width(self) -> int:
        return self.render_content().width

    @property
    @cached
    def content_height(self) -> int:
        return self.render_content().height

    @cached
    def render_content(self) -> RenderImage:
        return MessageRender.create(self.avatar_obj, self.content,
                                    self.nickname_obj,
                                    self.alignment).render()
