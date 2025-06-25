import asyncio
from typing import TypedDict

from nonebot.adapters.onebot.v11 import Message as MessageObject
from PIL import Image
from typing_extensions import NotRequired

from src.ext import MessageSegment, get_group_member_name
from src.utils.persistence import FileStorage
from src.utils.render import (Alignment, BoxSizing, CircleCrop, Color,
                              Container, Decorations, Direction,
                              FixedContainer, FontFamily)
from src.utils.render import Image as ImageObject
from src.utils.render import (Interpolation, JustifyContent, Palette,
                              Paragraph, RectCrop, RenderImage, RenderObject,
                              Space, Spacer, TextStyle)

from ..font import FontUtils
from ..markdown.components.utils.builder import Builder


class Conversation(TypedDict):
    avatar: str | Image.Image
    content: MessageObject
    nickname: NotRequired[str]
    alignment: NotRequired[Alignment]


class MessageRender:

    AVATAR_RADIUS = 28
    AVATAR_SIZE = 2 * AVATAR_RADIUS

    COLOR_BG = Color.from_hex("#F2F2F2")
    COLOR_NICKNAME = Color.from_hex("#A1A1A1")
    COLOR_CONTENT = Color.from_hex("#02071A")

    FONT = FontFamily.of(regular="data/static/fonts/MiSans-Regular.ttf",
                         bold="data/static/fonts/MiSans-Bold.ttf",
                         fallbacks=FontUtils.FALLBACK)

    STYLE_NICKNAME = TextStyle(font=FONT, size=18, color=COLOR_NICKNAME)
    STYLE_CONTENT = TextStyle(font=FONT, size=24, color=COLOR_CONTENT)

    FULL_MAX_WIDTH = 600
    MAX_WIDTH = 360
    MAX_IMAGE_DIM_R = 1.0
    MIN_IMAGE_DIM_R = 1.0 / 6
    SPACE_AVATAR_CONTENT = 14
    SPACE_NAME_CONTENT = 10
    CONTENT_ROUND_RADIUS = 15
    CONTENT_PADDING = Space.of_side(14, 16)
    CONTENT_DECO = Decorations.of(
        RectCrop.of(border_radius=CONTENT_ROUND_RADIUS,
                    box_sizing=BoxSizing.BORDER_BOX))
    PADDING = Space.of_side(26, 18)
    FACE_TEMPLATE = "data/static/face/{id}.png"
    FACE_SIZE = 30

    @classmethod
    async def render_content(
        cls,
        content: MessageObject,
        max_width: int | None = None,
        group_id: int | None = None,
        background: Color = Palette.WHITE,
        text_truncate: int | None = None,
    ) -> RenderObject:
        storage = await FileStorage.get_instance()
        builder = Builder(default=cls.STYLE_CONTENT, max_width=max_width)
        shortcut = None
        max_image_dim = round(
            (max_width or cls.MAX_WIDTH) * cls.MAX_IMAGE_DIM_R)
        min_image_dim = round(
            (max_width or cls.MAX_WIDTH) * cls.MIN_IMAGE_DIM_R)
        for i, segment in enumerate(content):
            segment = MessageSegment.from_onebot(segment)
            match segment.type:
                case "image" | "mface":
                    # load image
                    image = None
                    try:
                        filename = segment.extract_filename()
                        url = segment.extract_url()
                        data = await storage.load_image(url, filename)
                        if data is not None:
                            image = ImageObject.from_image(
                                data,
                                decorations=cls.CONTENT_DECO,
                            )
                    except Exception:
                        pass
                    if image is not None:
                        image = image.thumbnail(
                            max_image_dim,
                            max_image_dim,
                            Interpolation.LANCZOS,
                        ).cover(
                            min_image_dim,
                            min_image_dim,
                            Interpolation.LANCZOS,
                        )
                        if image.width > max_image_dim or image.height > max_image_dim:
                            image.resize(min(image.width, max_image_dim),
                                         min(image.height, max_image_dim))
                        builder.image(image, inline=False)
                    else:
                        builder.text("[图片]", inline=False)
                        # TODO: invalidate storage
                    if len(content) == 1:
                        shortcut = image
                        break
                case "at":
                    # convert to nickname
                    name = str(segment.extract_at())
                    try:
                        if group_id is not None:
                            name = await get_group_member_name(
                                group_id=group_id,
                                user_id=segment.extract_at())
                    except Exception:
                        pass
                    builder.text("@" + name)
                case "text":
                    text = segment.extract_text()
                    if i + 1 < len(content):
                        next_seg = MessageSegment.from_onebot(content[i + 1])
                        if next_seg.type in ("image", "mface"):
                            text = text.removesuffix("\n")
                    if text_truncate:
                        text_truncate = max(text_truncate, 3)
                        if len(text) >= text_truncate - 3:
                            text = text[:text_truncate - 3] + "..."
                    builder.text(text)
                case "face":
                    face_id = segment.extract_face()
                    try:
                        builder.image(
                            RenderImage.from_file(
                                cls.FACE_TEMPLATE.format(
                                    id=face_id)).thumbnail(
                                        cls.FACE_SIZE,
                                        cls.FACE_SIZE,
                                    ),
                            inline=True,
                        )
                    except Exception:
                        builder.text("[表情]", inline=True)
        # When there is only one image, directly use it as the main content
        if shortcut is None:
            return builder.build(spacing=4,
                                 background=background,
                                 padding=cls.CONTENT_PADDING,
                                 decorations=cls.CONTENT_DECO)
        return shortcut

    @classmethod
    def render_avatar(cls,
                      avatar: str | Image.Image,
                      avatar_size: int | None = None) -> RenderObject:
        if avatar_size is None:
            avatar_size = cls.AVATAR_SIZE
        if isinstance(avatar, str):
            avatar_ = ImageObject.from_url(avatar,
                                           decorations=[CircleCrop.of()])
        else:
            avatar_ = ImageObject.from_image(avatar,
                                             decorations=[CircleCrop.of()])
        avatar_.resize(avatar_size, avatar_size)
        return avatar_

    @classmethod
    async def create(
        cls,
        avatar: str | Image.Image,
        content: MessageObject,
        nickname: str = "",
        alignment: Alignment = Alignment.START,
        group_id: int | None = None,
    ) -> RenderObject:
        avatar_ = cls.render_avatar(avatar)
        nickname_ = None
        if nickname:
            nickname_ = Paragraph.of(nickname, style=cls.STYLE_NICKNAME)

        rendered_content = await cls.render_content(content, cls.MAX_WIDTH,
                                                    group_id)
        # assemble
        if nickname_:
            spacer = Spacer.of(height=cls.SPACE_NAME_CONTENT)
            components = [nickname_, spacer, rendered_content]
        else:
            components = [rendered_content]
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
            padding=cls.PADDING,
        )

    @classmethod
    async def create_conversation(
        cls,
        conversation: list[Conversation],
        group_id: int | None = None,
    ) -> RenderObject:
        children = await asyncio.gather(*(cls.create(
            avatar=conv["avatar"],
            content=conv["content"],
            nickname=conv.get("nickname", ""),
            alignment=conv.get("alignment", Alignment.START),
            group_id=group_id,
        ) for conv in conversation))
        return Container.from_children(
            [
                FixedContainer.from_children(
                    width=cls.FULL_MAX_WIDTH,
                    height=item.height,
                    justify_content=JustifyContent.START if conv.get(
                        "alignment", Alignment.START) == Alignment.START else
                    JustifyContent.END,
                    children=[item],
                    direction=Direction.HORIZONTAL)
                for item, conv in zip(children, conversation)
            ],
            direction=Direction.VERTICAL,
            background=cls.COLOR_BG,
        )
