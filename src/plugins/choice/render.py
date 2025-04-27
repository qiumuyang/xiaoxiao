import asyncio
from typing import cast

from src.utils.image.avatar import Avatar
from src.utils.persistence import FileStorage
from src.utils.render import *
from src.utils.render_ext.message import MessageRender
from src.utils.userlist import (MessageItem, ReferenceItem, UserList,
                                UserListPagination)


class ChoiceRender:

    PAGE_SIZE = 15

    CARD_WIDTH = 220
    CARD_WIDTH_MAX = 250

    BASE_SIZE = cast(int, MessageRender.STYLE_CONTENT.get("size"))
    BASE_AVATAR_SIZE = 40

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
    PAGE_STYLE = MessageRender.STYLE_CONTENT.copy()
    PAGE_STYLE["color"] = INDEX_COLOR
    PAGE_STYLE["size"] = round(BASE_SIZE * 0.8)

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
            avatar = MessageRender.render_avatar(
                await Avatar.user(user_id),
                avatar_size=round(cls.BASE_AVATAR_SIZE * rescale))
        else:
            avatar = None

        heading_height = max(
            (o.height for o in (index_obj, avatar, extra) if o is not None),
            default=round(cls.BASE_AVATAR_SIZE * rescale),
        )
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
        cached: bool = True,
    ):
        cache_name = f"choice-cache-{item.uuid}"
        storage = await FileStorage.get_instance(db_name="cache", ttl="1d")
        if cached and isinstance(item, MessageItem):  # ref is not cached
            try:
                image = await storage.load_image(url="", filename=cache_name)
            except Exception:
                image = None
            if image is not None:
                # cache hit
                im = Image.from_image(image)
                await storage.refresh(cache_name)
                return im
        # cache miss
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
        obj = await cls.add_heading_and_decoration(
            content=content,
            index=index,
            user_id=item.creator_id,
            max_width=cls.CARD_WIDTH_MAX,
        )
        image = obj.render().to_pil()
        if cached and isinstance(item, MessageItem):
            await storage.store_as_temp(storage.encode_image(image),
                                        cache_name)
        return obj

    @classmethod
    async def render_item_count(cls, userlist: UserList, rescale: float = 1.0):
        num_msg = sum(isinstance(_, MessageItem) for _ in userlist.items)
        num_ref = sum(isinstance(_, ReferenceItem) for _ in userlist.items)
        style = TextStyle(
            size=round(cls.BASE_SIZE * rescale * 0.8),
            color=cls.INDEX_COLOR,
            shading=TextShading(color=cls.MSG_BG, padding=Space.of_side(8, 2)),
        )
        return Paragraph.of(
            f"{num_msg}📝 {num_ref}🔗",
            style=cls.TITLE_STYLE | style,
            margin=Space.of_side(5, 0),
        )

    @classmethod
    async def render_list(
        cls,
        *,
        group_id: int,
        userlist: UserList,
        cached: bool = True,
        pagination: UserListPagination | None = None,
        items: list[tuple[int, MessageItem | ReferenceItem]] | None = None,
        deleted_uuids: list[str] | None = None,
    ):
        deleted_uuids = deleted_uuids or []
        if pagination is not None and items is not None:
            raise ValueError("Cannot specify both page_id and items")
        elif pagination is not None:
            items = list(pagination.enumerate())
        elif items is None:
            items = list(enumerate(userlist.items))

        num_columns = max(3, len(items) // 15)
        rescale = max(min(len(items) / 2, 2.0), 1.0)
        if items:
            valid_ref = await userlist.valid_references
            children = await asyncio.gather(*(cls.render_item_card(
                group_id=group_id,
                index=index,
                item=item,
                cached=cached,
                valid=isinstance(item, MessageItem) or item.name in valid_ref)
                                              for index, item in items))
            content = WaterfallContainer.from_children(
                children,
                columns=num_columns,
                alignment=Alignment.CENTER,
                ordered=False,
            )
            num_columns = min(num_columns, len(items))
            extra = await cls.render_item_count(userlist, rescale=rescale)
        else:
            num_columns = 1
            content = Paragraph.of("空空如也", style=cls.TITLE_STYLE)
            extra = None
        main_list = await cls.add_heading_and_decoration(
            content=content,
            title=userlist.name,
            user_id=userlist.creator_id,
            extra=extra,
            shadow=False,
            rescale=rescale,
            max_width=max(cls.CARD_WIDTH_MAX * num_columns, content.width),
        )
        if not pagination or pagination.num_pages == 1:
            return main_list
        # add page info
        page_info = Paragraph.of(
            (f"第 {pagination.page_id + 1} / {pagination.num_pages} 页\n"
             f"输入 “帮助 选择困难” 以查看翻页指令\n"),
            style=cls.PAGE_STYLE,
            alignment=Alignment.CENTER,
            max_width=main_list.width)
        return Container.from_children([main_list, page_info],
                                       direction=Direction.VERTICAL,
                                       alignment=Alignment.CENTER,
                                       spacing=5,
                                       background=Palette.WHITE)

    @classmethod
    async def render_list_overview(cls, *lists: UserList):
        columns = [[] for _ in range(3)]
        creator_ids = list(set(userlist.creator_id for userlist in lists))
        avatars = await asyncio.gather(*(Avatar.user(uid)
                                         for uid in creator_ids))
        avatar_dict = dict(zip(creator_ids, avatars))
        for userlist in sorted(lists, key=lambda x: -len(x.items)):
            title = Paragraph.of(userlist.name, style=cls.TITLE_STYLE)
            count = await cls.render_item_count(userlist)
            avatar = MessageRender.render_avatar(
                avatar=avatar_dict[userlist.creator_id],
                avatar_size=cls.BASE_AVATAR_SIZE,
            )
            columns[0].append(title)
            columns[1].append(count)
            columns[2].append(avatar)
        widths = [max(obj.width for obj in column) for column in columns]
        rows = []
        for i, _ in enumerate(lists):
            row_elements = [column[i] for column in columns]
            rows.append(
                Container.from_children(
                    [
                        FixedContainer.from_children(
                            width=width, height=obj.height, children=[obj])
                        for width, obj in zip(widths, row_elements)
                    ],
                    direction=Direction.HORIZONTAL,
                    alignment=Alignment.CENTER,
                    spacing=40,
                ))
        summary = Container.from_children(
            children=rows,
            direction=Direction.VERTICAL,
            alignment=Alignment.CENTER,
            spacing=10,
            padding=Space.all(10),
        )
        return await cls.add_heading_and_decoration(
            content=summary,
            title="选择困难",
            rescale=1.5,
        )
