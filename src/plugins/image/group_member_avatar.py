from enum import Enum

from src.utils.image.avatar import Avatar
from src.utils.render import *


class Item(Enum):
    TITLE = "title"
    AVATAR = "avatar"
    GROUP_AVATAR = "group_avatar"
    SP = "spacer"


RenderItem = Item | Text | Spacer

NotoSansHansBold = "data/static/fonts/NotoSansHans-Bold.otf"
SegUIEmoji = "data/static/fonts/seguiemj.ttf"


class GroupMemberAvatar:
    """
    GroupMemberAvatar is a class responsible for rendering group member avatars with titles.

    Renders the complete avatar with title and other elements as specified in `RENDER_LIST`.
    """

    AVATAR_RATIO = 0.9
    MARGIN_HOR_RATIO = 0.015
    MARGIN_VER_RATIO = 0.04
    SPACE_RATIO = 0.02

    TITLE_TEMPLATE = "{nickname}"
    TITLE_FONT = NotoSansHansBold
    TITLE_FALLBACK_FONT = SegUIEmoji
    TITLE_FONT_SIZE_RANGE = (4, 28)
    TITLE_ASPECT = 0.25
    TITLE_FILL = Palette.BLACK
    TITLE_STROKE = (None, 0)  # color and width
    BACKGROUND = Palette.WHITE

    DEFAULT_ALIGN = Alignment.CENTER
    RENDER_LIST: list[RenderItem | tuple[RenderItem, Alignment]] = []
    MAX_WIDTH: int = -1  # max width of fixed text

    @classmethod
    def get_max_width(cls) -> int:
        if cls.MAX_WIDTH == -1:
            size = 0
            for item in cls.RENDER_LIST:
                if isinstance(item, Text):
                    size = max(size, item.width)
            if size == -1:
                raise ValueError("No fixed width text found.")
            cls.MAX_WIDTH = size
        return cls.MAX_WIDTH

    @classmethod
    async def render_title(
        cls,
        nickname: str,
        alignment: Alignment,
        **kwargs,
    ) -> RenderObject:
        max_width = cls.get_max_width()
        max_height = round(max_width * cls.TITLE_ASPECT)
        stroke_fill, stroke_width = cls.TITLE_STROKE
        styled_parts = []
        for text, support in Text.split_font_unsupported(
                cls.TITLE_FONT, cls.TITLE_TEMPLATE.format(nickname=nickname)):
            styled_parts.append(text if support else f"<emoji>{text}</emoji>")
        font_size = StyledText.get_max_fitting_font_size(
            text="".join(styled_parts),
            styles={
                "emoji":
                TextStyle.of(
                    font=cls.TITLE_FALLBACK_FONT,
                    embedded_color=True,
                    ymin_correction=True,
                )
            },
            default=TextStyle.of(font=cls.TITLE_FONT,
                                 color=cls.TITLE_FILL,
                                 stroke_color=stroke_fill,
                                 stroke_width=stroke_width),
            font_size_range=cls.TITLE_FONT_SIZE_RANGE,
            max_size=(max_width, max_height),
        )
        return StyledText.of(
            text="".join(styled_parts),
            styles={
                "emoji":
                TextStyle.of(
                    font=cls.TITLE_FALLBACK_FONT,
                    embedded_color=True,
                    ymin_correction=True,
                )
            },
            default=TextStyle.of(font=cls.TITLE_FONT,
                                 size=font_size,
                                 color=cls.TITLE_FILL,
                                 stroke_color=stroke_fill,
                                 stroke_width=stroke_width),
            alignment=alignment,
            max_width=max_width,
        )

    @classmethod
    async def render_avatar(
        cls,
        *,
        user_id: int = -1,
        group_id: int = -1,
        **kwargs,
    ) -> RenderObject:
        width = round(cls.get_max_width() * cls.AVATAR_RATIO)
        if user_id > 0:
            im = await Avatar.user(user_id)
        elif group_id > 0:
            im = await Avatar.group(group_id)
        else:
            im = None
        if im is None:
            return Image.empty(width,
                               width,
                               Palette.WHITE,
                               border=Border.of(2))
        return Image.from_image(im).resize(width, width)

    @classmethod
    async def render(
        cls,
        *,
        user_id: int = -1,
        group_id: int = -1,
        nickname: str = "",
        group_name: str = "",
        **kwargs,
    ):
        margin_h = round(cls.get_max_width() * cls.MARGIN_HOR_RATIO)
        margin_v = round(cls.get_max_width() * cls.MARGIN_VER_RATIO)
        container = RelativeContainer(
            padding=Space.of_side(margin_h, margin_v),
            background=cls.BACKGROUND,
        )
        previous_obj: RenderObject | None = None
        sp = round(cls.get_max_width() * cls.SPACE_RATIO)
        for i, item in enumerate(cls.RENDER_LIST):
            align = cls.DEFAULT_ALIGN
            if isinstance(item, tuple):
                item, align = item
            if item == Item.TITLE:
                obj = await cls.render_title(nickname, align)
            elif item == Item.AVATAR:
                obj = await cls.render_avatar(user_id=user_id, **kwargs)
            elif item == Item.GROUP_AVATAR:
                obj = await cls.render_avatar(group_id=group_id, **kwargs)
            elif item == Item.SP:
                obj = Spacer.of(height=sp)
            else:
                obj = item
            rel: dict[str, RenderObject]
            match align:
                case Alignment.START:
                    rel = {"align_left": container}
                case Alignment.CENTER:
                    rel = {"center_horizontal": container}
                case Alignment.END:
                    rel = {"align_right": container}
            if previous_obj is None:
                rel["align_top"] = container
            else:
                rel["below"] = previous_obj
            offset = ((0, sp) if i > 0 and not isinstance(obj, Spacer) else
                      (0, 0))
            previous_obj = obj
            container.add_child(obj, **rel, offset=offset)  # type: ignore
        return container.render().to_pil()


class LittleAngel(GroupMemberAvatar):

    RENDER_LIST = [
        Item.TITLE,
        Item.SP,
        Item.AVATAR,
        Item.SP,
        Text.of("非常可爱！简直就是小天使",
                font=NotoSansHansBold,
                size=32,
                alignment=Alignment.CENTER),
        Text.of("她没失踪也没怎么样 我只是觉得你们都该看一下",
                font=NotoSansHansBold,
                size=18,
                alignment=Alignment.CENTER),
    ]

    TITLE_TEMPLATE = "请问你们看到{nickname}了吗？"


class Mesugaki(GroupMemberAvatar):

    RENDER_LIST = [
        Item.TITLE,
        Item.SP,
        Item.AVATAR,
        Item.SP,
        Text.of("非常欠艹！简直就是雌小鬼",
                font=NotoSansHansBold,
                size=32,
                alignment=Alignment.CENTER),
        Text.of("她没失踪也没怎么样 我只是觉得你们都该调教一下",
                font=NotoSansHansBold,
                size=18,
                alignment=Alignment.CENTER),
    ]

    TITLE_TEMPLATE = "请问你们看到{nickname}了吗？"


class RBQ(GroupMemberAvatar):

    RENDER_LIST = [
        Item.TITLE,
        Item.SP,
        Item.AVATAR,
        Item.SP,
        Text.of("非常可爱！简直就是RBQ",
                font=NotoSansHansBold,
                size=32,
                alignment=Alignment.CENTER),
        Text.of("她没失踪也没怎么样 我只是觉得你们都该玩一下",
                font=NotoSansHansBold,
                size=18,
                alignment=Alignment.CENTER),
    ]

    TITLE_TEMPLATE = "请问你们看到{nickname}了吗？"


__all__ = [
    "GroupMemberAvatar",
    "LittleAngel",
    "Mesugaki",
    "RBQ",
]
