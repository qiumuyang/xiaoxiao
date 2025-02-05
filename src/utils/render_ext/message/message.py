from typing import Literal

from PIL import Image

from src.utils.render import (Alignment, BoxSizing, CircleCrop, Color,
                              Container, Decorations, Direction)
from src.utils.render import Image as ImageObject
from src.utils.render import (Palette, RectCrop, RenderObject, Space, Spacer,
                              Text, TextStyle)


class Message:

    AVATAR_RADIUS = 28
    AVATAR_SIZE = 2 * AVATAR_RADIUS

    COLOR_BG = Color.from_hex("#F2F2F2")
    COLOR_NICKNAME = Color.from_hex("#A1A1A1")
    COLOR_CONTENT = Color.from_hex("#02071A")

    FONT = "data/static/fonts/MiSans-Regular.ttf"

    STYLE_NICKNAME = TextStyle.of(font=FONT, size=18, color=COLOR_NICKNAME)
    STYLE_CONTENT = TextStyle.of(font=FONT, size=24, color=COLOR_CONTENT)

    MAX_WIDTH = 500
    MAX_HEIGHT = 550
    SPACE_AVATAR_CONTENT = 10
    SPACE_NAME_CONTENT = 6
    CONTENT_ROUND_RADIUS = 11
    CONTENT_PADDING = Space.of_side(14, 12)
    CONTENT_DECO = Decorations.of(
        RectCrop.of(border_radius=CONTENT_ROUND_RADIUS,
                    box_sizing=BoxSizing.BORDER_BOX))
    PADDING = Space.of_side(26, 17)

    def __init__(self,
                 avatar: Image.Image,
                 content: str | Image.Image,
                 nickname: str = "",
                 alignment: Alignment
                 | Literal["start", "end"] = Alignment.START):
        self.avatar = avatar
        self.content = content
        self.nickname = nickname
        match alignment:
            case "start":
                self.alignment = Alignment.START
            case "end":
                self.alignment = Alignment.END
            case _:
                assert isinstance(alignment, Alignment)
                self.alignment = alignment

    def create(self) -> RenderObject:
        avatar = ImageObject.from_image(
            self.avatar,
            decorations=[CircleCrop.of()],
        ).resize(self.AVATAR_SIZE, self.AVATAR_SIZE)
        nickname = None
        if self.nickname:
            nickname = Text.from_style(self.nickname,
                                       style=self.STYLE_NICKNAME)
        if isinstance(self.content, str):
            content = Text.from_style(self.content,
                                      style=self.STYLE_CONTENT,
                                      max_width=self.MAX_WIDTH,
                                      line_spacing=8,
                                      background=Palette.WHITE,
                                      padding=self.CONTENT_PADDING,
                                      decorations=self.CONTENT_DECO)
        else:
            content = ImageObject.from_image(
                self.content,
                decorations=self.CONTENT_DECO,
            ).rescale(0.6).thumbnail(self.MAX_WIDTH, self.MAX_HEIGHT)
        # assemble
        if nickname:
            content_components = [
                nickname,
                Spacer.of(height=self.SPACE_NAME_CONTENT), content
            ]
        else:
            content_components = [content]
        name_with_content = Container.from_children(
            content_components,
            alignment=self.alignment,
            direction=Direction.VERTICAL)
        items = [
            avatar,
            Spacer.of(width=self.SPACE_AVATAR_CONTENT), name_with_content
        ]
        if self.alignment is Alignment.END:
            items.reverse()
        return Container.from_children(
            items,
            alignment=Alignment.START,  # align top
            direction=Direction.HORIZONTAL,
            background=self.COLOR_BG,
            padding=self.PADDING)
