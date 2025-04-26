import asyncio
from typing import cast

from src.utils.image.avatar import Avatar
from src.utils.render import *
from src.utils.render_ext.message import MessageRender
from src.utils.userlist import MessageItem, ReferenceItem, UserList


class ChoiceRender:

    CARD_WIDTH = 220
    CARD_WIDTH_MAX = 250

    BASE_SIZE = cast(int, MessageRender.STYLE_CONTENT.get("size"))

    REF_BG = Color.from_hex("#f5faff")
    REF_BG_INVALID = Color.from_hex("#fcebec")
    MSG_BG = Color.from_hex("#f0f1f2")

    REF_STYLE = MessageRender.STYLE_CONTENT.copy()
    REF_STYLE["color"] = Color.from_hex("#0077cc")
    REF_STYLE_INVALID = REF_STYLE.copy()
    REF_STYLE_INVALID["color"] = Color.from_hex("#a04545")
    # REF_STYLE_INVALID["decoration"] = TextDecoration.line_through()

    INDEX_COLOR = Color.from_hex("#666666")
    INDEX_STYLE = TextStyle(font="data/static/fonts/arialbd.ttf",
                            size=BASE_SIZE,
                            color=INDEX_COLOR)
    TITLE_STYLE = MessageRender.STYLE_CONTENT.copy()
    TITLE_STYLE["color"] = Palette.BLACK

    @classmethod
    async def add_heading_and_decoration(
        cls,
        *,
        content: RenderObject,
        index: int | None = None,
        title: str | None = None,
        extra: RenderObject | None = None,
        user_id: int | None = None,
        spacing: int = 5,
        max_width: int | None = None,
        shadow: bool = True,
        rescale: float = 1.0,
    ):
        """
        Adds a heading and a decoration to the content.

        The heading is a horizontal line consisting of the following parts:
            - index (left)
            - title (left)
            - extra (left)
            - avatar (right)
            - horizontal line (between above components and content)

        The decoration is shadow effect if `shadow` is True.
        """
        rescale = max(1, rescale)
        update_style = TextStyle(size=round(cls.BASE_SIZE * rescale))
        if index is not None:
            index_obj = Paragraph.of(f"# {index+1}",
                                     style=cls.INDEX_STYLE | update_style)
        else:
            index_obj = None
        if user_id is not None:
            avatar = MessageRender.render_avatar(await Avatar.user(user_id),
                                                 avatar_size=round(40 *
                                                                   rescale))
        else:
            avatar = None

        heading_height = max(o.height for o in (index_obj, avatar, extra)
                             if o is not None)
        max_heading_width = max_width or cls.CARD_WIDTH_MAX
        max_title_w = max_heading_width - sum(
            (o.width + spacing)
            for o in (index_obj, avatar, extra) if o is not None)
        max_title_size = (max_title_w, heading_height)

        if title is not None:
            title_obj = Paragraph.from_template_with_font_range(
                "<b>{title}</b>",
                values=dict(title=title),
                default=cls.TITLE_STYLE | update_style,
                styles=dict(b=TextStyle(bold=True)),
                font_size=(0, round(cls.BASE_SIZE * rescale)),
                max_size=max_title_size)
        else:
            title_obj = None
        left = Container.from_children(
            [obj for obj in (index_obj, title_obj, extra) if obj is not None],
            direction=Direction.HORIZONTAL,
            alignment=Alignment.CENTER,
            spacing=spacing)

        if max_width is None:
            max_width = max(
                content.width,
                sum((o.width + spacing) for o in (left, avatar)
                    if o is not None), cls.CARD_WIDTH_MAX)

        if avatar is not None:
            heading = Container.from_children(
                [
                    left,
                    ZeroSpacingSpacer.of(width=max_width - left.width -
                                         avatar.width), avatar
                ],
                direction=Direction.HORIZONTAL,
                alignment=Alignment.CENTER,
                spacing=spacing,
            )
        else:
            heading = left

        if shadow:
            style = BaseStyle(padding=Space.all(round(0.05 * max_width)),
                              margin=Space.all(round(0.06 * max_width)),
                              background=Palette.WHITE,
                              decorations=[
                                  RectCrop.of(
                                      border_radius=7,
                                      box_sizing=BoxSizing.PADDING_BOX),
                                  BoxShadow.of(blur_radius=35,
                                               spread=8,
                                               color=Color.of(0, 0, 0, 0.1))
                              ])
        else:
            style = BaseStyle(padding=Space.all(round(0.05 * max_width)),
                              background=Palette.WHITE)
        card = Container.from_children(
            [
                heading,
                Image.horizontal_line(
                    max_width,
                    width=1,
                    color=cast(Color, cls.INDEX_STYLE.get("color"))),
                content,
            ],
            spacing=10,
            direction=Direction.VERTICAL,
            alignment=Alignment.START,
            **style,
        )
        return Container.from_children([card], background=Palette.WHITE)

    @classmethod
    async def render_item_card(
        cls,
        *,
        group_id: int,
        index: int,
        item: MessageItem | ReferenceItem,
        valid: bool = True,
    ):
        if isinstance(item, MessageItem):
            content = await MessageRender.render_content(
                item.content,
                max_width=cls.CARD_WIDTH,
                group_id=group_id,
                background=cls.MSG_BG)
            background = Palette.TRANSPARENT
            decoration = Decorations.of()
        else:
            content = Paragraph.of(
                f"🔗 [{item.name}]",
                style=cls.REF_STYLE if valid else cls.REF_STYLE_INVALID,
                max_width=cls.CARD_WIDTH,
            )
            background = cls.REF_BG if valid else cls.REF_BG_INVALID
            decoration = MessageRender.CONTENT_DECO
        content = FixedContainer.from_children(width=cls.CARD_WIDTH_MAX,
                                               height=content.height,
                                               children=[content],
                                               direction=Direction.VERTICAL,
                                               background=background,
                                               decorations=decoration)
        return await cls.add_heading_and_decoration(
            content=content,
            index=index,
            user_id=item.creator_id,
            max_width=cls.CARD_WIDTH_MAX,
        )

    @classmethod
    async def render_list(
        cls,
        *,
        group_id: int,
        userlist: UserList,
    ):
        num_columns = max(3, len(userlist.items) // 15)
        rescale = max(min(len(userlist.items) / 2, 2.0), 1.0)
        if userlist.items:
            valid_ref = await userlist.valid_references
            children = await asyncio.gather(
                *(cls.render_item_card(group_id=group_id,
                                       index=index,
                                       item=item,
                                       valid=isinstance(item, MessageItem)
                                       or item.name in valid_ref)
                  for index, item in enumerate(userlist.items)))
            content = WaterfallContainer.from_children(
                children,
                columns=num_columns,
                alignment=Alignment.CENTER,
            )
            num_columns = min(num_columns, len(userlist.items))
            num_msg = sum(isinstance(_, MessageItem) for _ in userlist.items)
            num_ref = sum(isinstance(_, ReferenceItem) for _ in userlist.items)
            extra_style = TextStyle(
                size=round(cls.BASE_SIZE * rescale * 0.8),
                color=cls.INDEX_COLOR,
                shading=TextShading(color=cls.MSG_BG,
                                    padding=Space.of_side(8, 2)),
            )
            extra = Paragraph.of(
                f"{num_msg}📝 {num_ref}🔗",
                style=cls.TITLE_STYLE | extra_style,
                margin=Space.of_side(5, 0),
            )
        else:
            num_columns = 1
            content = Paragraph.of("空空如也", style=cls.TITLE_STYLE)
            extra = None
        return await cls.add_heading_and_decoration(
            content=content,
            title=userlist.name,
            user_id=userlist.creator_id,
            extra=extra,
            shadow=False,
            rescale=rescale,
            max_width=max(cls.CARD_WIDTH_MAX * num_columns, content.width),
        )
