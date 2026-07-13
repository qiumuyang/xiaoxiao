import asyncio
from collections.abc import Sequence
from typing import Literal, NamedTuple, cast

from nonebot.adapters.onebot.v11 import Message

from src.utils.image.avatar import Avatar
from src.utils.persistence import FileStorage
from src.utils.render import (
    Alignment,
    BaseStyle,
    BoxShadow,
    BoxSizing,
    Color,
    Container,
    Decorations,
    Direction,
    FixedContainer,
    Image,
    Palette,
    Paragraph,
    RectCrop,
    RenderObject,
    Space,
    TextDecoration,
    TextShading,
    TextStyle,
    WaterfallContainer,
    ZeroSpacingSpacer,
)
from src.utils.render_ext.message import MessageRender
from src.utils.userlist import (
    MessageItem,
    ReferenceItem,
    UserList,
    UserListMetadata,
    UserListPagination,
)

DiffStatus = Literal["added", "skipped", "forced", "removed", "remove_failed"]


class DiffEntry(NamedTuple):
    status: DiffStatus
    item_index: int | None
    item: MessageItem | ReferenceItem | None
    fail_text: str | None


_STATUS_COLORS: dict[DiffStatus, Color] = {
    "added": Color.from_hex("#22a45d"),
    "forced": Color.from_hex("#22a45d"),
    "skipped": Color.from_hex("#0077cc"),
    "removed": Color.from_hex("#d14b4b"),
    "remove_failed": Color.from_hex("#666666"),
}


class ChoiceRender:
    PAGE_SIZE = 20

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
    INDEX_STYLE = TextStyle(
        font="data/static/fonts/arialbd.ttf", size=BASE_SIZE, color=INDEX_COLOR
    )
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
        label: str | None = None,
        label_color: Color | None = None,
        index_color: Color | None = None,
    ):
        """
        Adds a heading and a decoration to the content.

        The heading is a horizontal line consisting of the following parts:
            - index or label (left)
            - title (left)
            - extra (left)
            - avatar (right)
            - horizontal line (between above components and content)

        The decoration is shadow effect if `shadow` is True.
        If `label` is set, it overrides the `index` display with custom text.
        If both `label` and `index` are set, both are displayed side-by-side.
        """
        rescale = max(1, rescale)
        update_style = TextStyle(size=round(cls.BASE_SIZE * rescale))
        if label is not None:
            color = label_color or cast(Color, cls.INDEX_STYLE.get("color"))
            label_obj = Paragraph.of(
                label,
                style=cls.INDEX_STYLE
                | update_style
                | TextStyle(color=color, bold=True),
            )
            if index is not None:
                idx_obj = Paragraph.of(
                    f"# {index + 1}", style=cls.INDEX_STYLE | update_style
                )
                index_obj = Container.from_children(
                    [label_obj, idx_obj],
                    direction=Direction.HORIZONTAL,
                    alignment=Alignment.CENTER,
                    spacing=3,
                )
            else:
                index_obj = label_obj
        elif index is not None:
            style = cls.INDEX_STYLE | update_style
            if index_color is not None:
                style = style | TextStyle(color=index_color)
            index_obj = Paragraph.of(
                f"# {index + 1}", style=style
            )
        else:
            index_obj = None
        if user_id is not None:
            avatar = MessageRender.render_avatar(
                await Avatar.user(user_id),
                avatar_size=round(cls.BASE_AVATAR_SIZE * rescale),
            )
        else:
            avatar = None

        heading_height = max(
            (o.height for o in (index_obj, avatar, extra) if o is not None),
            default=round(cls.BASE_AVATAR_SIZE * rescale),
        )
        max_heading_width = max_width or cls.CARD_WIDTH_MAX
        max_title_w = max_heading_width - sum(
            (o.width + spacing) for o in (index_obj, avatar, extra) if o is not None
        )
        max_title_size = (max_title_w, heading_height)

        if title is not None:
            title_obj = Paragraph.from_template_with_font_range(
                "<b>{title}</b>",
                values=dict(title=title),
                default=cls.TITLE_STYLE | update_style,
                styles=dict(b=TextStyle(bold=True)),
                font_size=(0, round(cls.BASE_SIZE * rescale)),
                max_size=max_title_size,
            )
        else:
            title_obj = None
        left = Container.from_children(
            [obj for obj in (index_obj, title_obj, extra) if obj is not None],
            direction=Direction.HORIZONTAL,
            alignment=Alignment.CENTER,
            spacing=spacing,
        )

        if max_width is None:
            max_width = max(
                content.width,
                sum((o.width + spacing) for o in (left, avatar) if o is not None),
                cls.CARD_WIDTH_MAX,
            )

        if avatar is not None:
            heading = Container.from_children(
                [
                    left,
                    ZeroSpacingSpacer.of(width=max_width - left.width - avatar.width),
                    avatar,
                ],
                direction=Direction.HORIZONTAL,
                alignment=Alignment.CENTER,
                spacing=spacing,
            )
        else:
            heading = left

        if shadow:
            style = BaseStyle(
                padding=Space.all(round(0.05 * max_width)),
                margin=Space.all(round(0.06 * max_width)),
                background=Palette.WHITE,
                decorations=[
                    RectCrop.of(border_radius=7, box_sizing=BoxSizing.PADDING_BOX),
                    BoxShadow.of(
                        blur_radius=35, spread=8, color=Color.of(0, 0, 0, 0.1)
                    ),
                ],
            )
        else:
            style = BaseStyle(
                padding=Space.all(round(0.05 * max_width)), background=Palette.WHITE
            )
        card = Container.from_children(
            [
                heading,
                Image.horizontal_line(
                    max_width, width=1, color=cast(Color, cls.INDEX_STYLE.get("color"))
                ),
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
        index: int | None,
        item: MessageItem | ReferenceItem,
        valid: bool = True,
        cached: bool = True,
        status: DiffStatus | None = None,
    ):
        cache_name = f"choice-cache-{item.uuid}-{index}"
        storage = await FileStorage.get_instance(db_name="cache", ttl="1d")
        if cached and isinstance(item, MessageItem):  # ref is not cached
            try:
                image = await storage.load_image(url="", filename=cache_name)
                if image is not None:
                    image = Image.from_image(image)
                    await storage.refresh(cache_name)
                    return image
            except Exception:
                pass
        # cache miss
        rm_style = (
            TextStyle(
                color=_STATUS_COLORS["removed"],
                decoration=TextDecoration.line_through(),
            )
            if status == "removed"
            else None
        )
        if isinstance(item, MessageItem):
            content = await MessageRender.render_content(
                item.content,
                max_width=cls.CARD_WIDTH,
                group_id=group_id,
                background=cls.MSG_BG,
                text_truncate=40,
                text_style=rm_style,
            )
            background = Palette.TRANSPARENT
            decoration = Decorations.of()
        else:
            style = cls.REF_STYLE if valid else cls.REF_STYLE_INVALID
            if rm_style is not None:
                style = style | rm_style
            content = Paragraph.of(
                f"🔗 [{item.name}]",
                style=style,
                max_width=cls.CARD_WIDTH,
            )
            background = cls.REF_BG if valid else cls.REF_BG_INVALID
            decoration = MessageRender.CONTENT_DECO
        content = FixedContainer.from_children(
            width=cls.CARD_WIDTH_MAX,
            height=content.height,
            children=[content],
            direction=Direction.VERTICAL,
            background=background,
            decorations=decoration,
        )

        if status is not None:
            obj = await cls.add_heading_and_decoration(
                content=content,
                index=index,
                index_color=_STATUS_COLORS[status],
                user_id=item.creator_id,
                max_width=cls.CARD_WIDTH_MAX,
            )
        else:
            obj = await cls.add_heading_and_decoration(
                content=content,
                index=index,
                user_id=item.creator_id,
                max_width=cls.CARD_WIDTH_MAX,
            )
        image = obj.render().to_pil()
        if cached and isinstance(item, MessageItem):
            await storage.store_as_temp(storage.encode_image(image), cache_name)
        return obj

    @classmethod
    async def render_item_count(
        cls, userlist: UserList | UserListMetadata, rescale: float = 1.0
    ):
        if isinstance(userlist, UserListMetadata):
            num_msg = userlist.num_messages
            num_ref = userlist.num_references
        else:
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
        items: Sequence[tuple[int, MessageItem | ReferenceItem]] | None = None,
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
            children = await asyncio.gather(
                *(
                    cls.render_item_card(
                        group_id=group_id,
                        index=index,
                        item=item,
                        cached=cached,
                        valid=isinstance(item, MessageItem) or item.name in valid_ref,
                    )
                    for index, item in items
                )
            )
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
            (
                f"第 {pagination.page_id + 1} / {pagination.num_pages} 页\n"
                f"输入 “帮助 选择困难” 以查看翻页指令\n"
            ),
            style=cls.PAGE_STYLE,
            alignment=Alignment.CENTER,
            max_width=main_list.width,
        )
        return Container.from_children(
            [main_list, page_info],
            direction=Direction.VERTICAL,
            alignment=Alignment.CENTER,
            spacing=5,
            background=Palette.WHITE,
        )

    @classmethod
    async def _render_diff_item(
        cls,
        *,
        group_id: int,
        entry: DiffEntry,
    ) -> RenderObject:
        if entry.item is not None:
            return await cls.render_item_card(
                group_id=group_id,
                index=entry.item_index,
                item=entry.item,
                valid=True,
                cached=False,
                status=entry.status,
            )

        fail_text = str(entry.fail_text or "")
        if len(fail_text) > 37:
            fail_text = fail_text[:37] + "..."
        fail_text += "（未匹配）"
        content = await MessageRender.render_content(
            Message(fail_text),
            max_width=cls.CARD_WIDTH,
            group_id=group_id,
            background=cls.MSG_BG,
            text_style=TextStyle(
                color=_STATUS_COLORS["remove_failed"]
            ),
        )
        content = FixedContainer.from_children(
            width=cls.CARD_WIDTH_MAX,
            height=content.height,
            children=[content],
            direction=Direction.VERTICAL,
        )
        return await cls.add_heading_and_decoration(
            content=content,
            label="# ?",
            label_color=_STATUS_COLORS["remove_failed"],
            max_width=cls.CARD_WIDTH_MAX,
        )

    @classmethod
    async def render_diff(
        cls,
        *,
        group_id: int,
        userlist: UserList,
        diff_items: list[DiffEntry],
    ):
        rescale = max(min(len(diff_items) / 2, 2.0), 1.0)
        num_columns = 1

        if diff_items:
            cards = await asyncio.gather(
                *(
                    cls._render_diff_item(
                        group_id=group_id, entry=e
                    )
                    for e in diff_items
                )
            )
            content: RenderObject = WaterfallContainer.from_children(
                children=cards,
                columns=max(1, len(diff_items) // 3),
                alignment=Alignment.CENTER,
                ordered=False,
            )
            num_columns = min(max(1, len(diff_items) // 3), len(diff_items))
        else:
            content = Paragraph.of("无变更", style=cls.TITLE_STYLE)

        return await cls.add_heading_and_decoration(
            content=content,
            title=userlist.name,
            user_id=userlist.creator_id,
            shadow=False,
            rescale=rescale,
            max_width=max(cls.CARD_WIDTH_MAX * num_columns, content.width),
        )

    @classmethod
    async def _render_column_rows(cls, *lists: UserListMetadata) -> Container:
        columns = [[], [], []]
        creator_ids = list(set(userlist.creator_id for userlist in lists))
        avatars = await asyncio.gather(*(Avatar.user(uid) for uid in creator_ids))
        avatar_dict = dict(zip(creator_ids, avatars, strict=False))
        for userlist in sorted(lists, key=lambda x: -x.num_items):
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
                            width=width, height=obj.height, children=[obj]
                        )
                        for width, obj in zip(widths, row_elements, strict=False)
                    ],
                    direction=Direction.HORIZONTAL,
                    alignment=Alignment.CENTER,
                    spacing=40,
                )
            )
        return Container.from_children(
            children=rows,
            direction=Direction.VERTICAL,
            alignment=Alignment.CENTER,
            spacing=10,
            padding=Space.all(10),
        )

    @classmethod
    async def render_list_overview(cls, *lists: UserListMetadata):
        # single-column mode: use original path directly
        if len(lists) <= 30:
            content = await cls._render_column_rows(*lists)
            return await cls.add_heading_and_decoration(
                content=content,
                title="选择困难",
                rescale=1.5,
            )

        # multi-column mode: split into columns, render each, join with vertical lines
        num_cols = 3 if len(lists) > 45 else 2
        sorted_lists = sorted(lists, key=lambda x: -x.num_items)
        # round-robin distribute so each column gets a mix of popular and less-popular
        col_lists: list[list[UserListMetadata]] = [[] for _ in range(num_cols)]
        for i, lst in enumerate(sorted_lists):
            col_lists[i % num_cols].append(lst)

        columns = [await cls._render_column_rows(*col) for col in col_lists]

        col_height = max(c.height for c in columns)
        separator = Image.vertical_line(
            col_height,
            width=1,
            color=Color.from_hex("#e0e0e0"),
        )
        assembled: list[RenderObject] = [columns[0]]
        for col in columns[1:]:
            assembled.append(separator)
            assembled.append(col)
        content = Container.from_children(
            assembled,
            direction=Direction.HORIZONTAL,
            alignment=Alignment.START,
            spacing=30,
        )
        return await cls.add_heading_and_decoration(
            content=content,
            title="选择困难",
            rescale=1.5,
        )
