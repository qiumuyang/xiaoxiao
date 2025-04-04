from enum import Enum

from src.utils.doc import CommandCategory, command_doc
from src.utils.image.avatar import Avatar
from src.utils.render import *


class Item(Enum):
    TITLE = "title"
    AVATAR = "avatar"
    GROUP_AVATAR = "group_avatar"
    SP = "spacer"


RenderItem = Item | Paragraph | Spacer

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
    TITLE_FONT = FontFamily.of(regular=NotoSansHansBold,
                               fallbacks=FontFamily.of(
                                   regular=SegUIEmoji,
                                   embedded_color=True,
                                   scale=0.85,
                                   baseline_correction=True))
    TITLE_FONT_SIZE_RANGE = (4, 28)
    TITLE_ASPECT = 0.25
    TITLE_FILL = Palette.BLACK
    TITLE_STROKE: TextStroke | None = None
    TITLE_EXTRA_STYLES: dict[str, TextStyle] = {}
    BACKGROUND = Palette.WHITE

    DEFAULT_ALIGN = Alignment.CENTER
    RENDER_LIST: list[RenderItem | tuple[RenderItem, Alignment]] = []
    MAX_WIDTH: int = -1  # max width of fixed text

    @classmethod
    def get_max_width(cls) -> int:
        if cls.MAX_WIDTH == -1:
            size = 0
            for item in cls.RENDER_LIST:
                if isinstance(item, Paragraph):
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
        return Paragraph.from_template_with_font_range(
            template=cls.TITLE_TEMPLATE,
            values=dict(nickname=nickname),
            max_size=(max_width, max_height),
            font_size=cls.TITLE_FONT_SIZE_RANGE,
            default=TextStyle(font=cls.TITLE_FONT,
                              color=cls.TITLE_FILL,
                              stroke=cls.TITLE_STROKE),
            styles=cls.TITLE_EXTRA_STYLES,
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
            raise ValueError
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


def text_large(s: str) -> Paragraph:
    return Paragraph.of(
        s,
        style=TextStyle(font=NotoSansHansBold, size=32),
        alignment=Alignment.CENTER,
    )


def text_small(s: str) -> Paragraph:
    return Paragraph.of(
        s,
        style=TextStyle(font=NotoSansHansBold, size=18),
        alignment=Alignment.CENTER,
    )


@command_doc("小天使", category=CommandCategory.IMAGE, visible_in_overview=False)
class LittleAngel(GroupMemberAvatar):
    """
    非常可爱！简直就是小天使

    Usage:
        {cmd} `@用户`  - 让群友们都来看一下
    """

    RENDER_LIST = [
        Item.TITLE,
        Item.SP,
        Item.AVATAR,
        Item.SP,
        text_large("非常可爱！简直就是小天使"),
        text_small("她没失踪也没怎么样 我只是觉得你们都该看一下"),
    ]

    TITLE_TEMPLATE = "请问你们看到{nickname}了吗？"


@command_doc("雌小鬼", category=CommandCategory.IMAGE, visible_in_overview=False)
class Mesugaki(GroupMemberAvatar):
    """
    非常欠艹！简直就是雌小鬼

    Usage:
        {cmd} `@用户`  - 让群友们都来调教一下
    """

    RENDER_LIST = [
        Item.TITLE,
        Item.SP,
        Item.AVATAR,
        Item.SP,
        text_large("非常欠艹！简直就是雌小鬼"),
        text_small("她没失踪也没怎么样 我只是觉得你们都该调教一下"),
    ]

    TITLE_TEMPLATE = "请问你们看到{nickname}了吗？"


@command_doc("RBQ", category=CommandCategory.IMAGE, visible_in_overview=False)
class RBQ(GroupMemberAvatar):
    """
    非常可爱！简直就是RBQ

    Usage:
        {cmd} `@用户`  - 让群友们都来玩一下
    """

    RENDER_LIST = [
        Item.TITLE,
        Item.SP,
        Item.AVATAR,
        Item.SP,
        text_large("非常可爱！简直就是RBQ"),
        text_small("她没失踪也没怎么样 我只是觉得你们都该玩一下"),
    ]

    TITLE_TEMPLATE = "请问你们看到{nickname}了吗？"
