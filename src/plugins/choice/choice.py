import asyncio
import random
from typing import NamedTuple

from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, Message, MessageSegment
from nonebot.exception import FinishedException
from nonebot.matcher import Matcher

from src.ext import MessageExtension
from src.ext import MessageSegment as ExtMessageSegment
from src.ext.message.comparator import ImagePHashComparator
from src.utils.log import logger_wrapper
from src.utils.render import Interpolation, RenderObject
from src.utils.userlist import (
    ListPermissionError,
    MessageItem,
    ReferenceItem,
    TooManyItemsError,
    TooManyListsError,
    UserList,
    UserListError,
    UserListService,
)

from .config import ChoiceConfig
from .exception import (
    ChoiceError,
    InvalidIndexError,
    InvalidItemOpError,
    InvalidListNameError,
    ListExistsError,
    ListNotExistsError,
    NonPlainTextError,
)
from .parse import Action, Op
from .render import ChoiceRender, DiffEntry

logger = logger_wrapper(__name__)


class Number(NamedTuple):
    num: int
    is_page: bool
    is_all: bool = False


def extract_plain_text(
    content: str, symtab: dict[str, MessageSegment], exception: Exception | None = None
):
    message = MessageExtension.decode(content, symtab)
    if any(not seg.is_text() for seg in message) and exception is not None:
        raise exception
    return message.extract_plain_text()


def parse_page_or_item_number(
    action: Action,
    symtab: dict[str, MessageSegment],
) -> Number:
    if not action.items:
        return Number(0, True)
    s = extract_plain_text(
        action.items[0].content, symtab, NonPlainTextError("页码/索引")
    )
    if s.lower() == "all":
        return Number(0, True, True)
    if s.startswith("#"):
        if not s[1:].isdecimal():
            raise InvalidIndexError(s[1:], "索引")
        return Number(int(s[1:]) - 1, False)
    try:
        num = int(s)
        if num == 0:
            raise ValueError
    except ValueError as e:
        raise InvalidIndexError(s, "页码") from e
    return Number(num - 1 if num > 0 else num, True)


class ChoiceHandler:
    MAX_LIST_NAME_LEN = 20
    NUM_ITEMS_PER_PAGE = ChoiceRender.PAGE_SIZE

    ERR_MSG = {
        ListPermissionError: "仅创建者或管理员可进行该操作",
        TooManyListsError: "列表数已达上限",
        TooManyItemsError: "该列表中项目数量已达上限",
    }

    def __init__(self, bot: Bot, event: GroupMessageEvent, matcher: type[Matcher]):
        self.bot = bot
        self.event = event
        self.matcher = matcher
        self.comparator = ImagePHashComparator()

    @property
    def group_id(self):
        return self.event.group_id

    async def overview(self):
        lst_meta = await UserListService.find_all_list_meta(self.group_id)
        if not lst_meta:
            await self.matcher.finish("还没有创建任何列表")
        obj = await ChoiceRender.render_list_overview(*lst_meta)
        await self.matcher.finish(ExtMessageSegment.image(obj.render().to_pil()))

    async def execute_search(
        self,
        content: Message,
        action: Action,
        symtab: dict[str, MessageSegment],
    ):
        try:
            list_name = extract_plain_text(
                action.name, symtab, NonPlainTextError("列表名称")
            )
            lst = await UserListService.find_list(self.group_id, list_name)
            if lst is None:
                raise ListNotExistsError(list_name)
        except ChoiceError as e:
            await self.matcher.finish(str(e))
        except UserListError as e:
            await self.matcher.finish(self.ERR_MSG[type(e)])
        except FinishedException:
            # caused by matcher.finish
            raise
        except Exception as e:
            logger.error("Unexpected error", exception=e)
            await self.matcher.finish(f"未知错误: {e}")

        message_items = [
            (index, item)
            for index, item in enumerate(lst.items)
            if isinstance(item, MessageItem)
        ]
        match_result = await asyncio.gather(
            *[self.comparator(content, item.content) for _, item in message_items]
        )
        matched: list[tuple[int, MessageItem | ReferenceItem]] = [
            (index, item)
            for (index, item), matched in zip(message_items, match_result, strict=False)
            if matched
        ]

        # process reference items
        ref_items = [
            (index, item)
            for index, item in enumerate(lst.items)
            if isinstance(item, ReferenceItem)
        ]
        for index, item in ref_items:
            ref_list = await UserListService.find_list(self.group_id, item.name)
            if ref_list is None:
                continue
            ref_match = await asyncio.gather(
                *[
                    self.comparator(content, ref_item.content)
                    for ref_item in ref_list.items
                    if isinstance(ref_item, MessageItem)
                ]
            )
            if any(ref_match):
                matched.append((index, item))

        if not matched:
            await self.matcher.finish("未找到匹配条目")

        matched.sort(key=lambda x: x[0])  # sort by index
        obj = await ChoiceRender.render_list(
            group_id=self.group_id,
            userlist=lst,
            items=matched,
        )
        await self.matcher.finish(ExtMessageSegment.image(obj.render().to_pil()))

    async def execute(
        self,
        operator_id: int,
        action: Action,
        symtab: dict[str, MessageSegment],
        sudo: bool = False,
    ):
        try:
            lst_name = extract_plain_text(
                action.name, symtab, NonPlainTextError("列表名称")
            )
            if len(lst_name) > self.MAX_LIST_NAME_LEN:
                raise InvalidListNameError(
                    f"列表名称至多包含{self.MAX_LIST_NAME_LEN}个字符"
                )
            if not lst_name:
                raise InvalidListNameError("列表名称不可为空")

            match action.op:
                case Op.SHOW | Op.ADD | Op.REMOVE | Op.TOGGLE:
                    handler = self.handle_list
                case Op.NONE:
                    handler = self.handle_list_items
                case _:
                    raise AssertionError("unexpected list operation")
            await handler(operator_id, lst_name, action, symtab, sudo)
        except ChoiceError as e:
            await self.matcher.finish(str(e))
        except UserListError as e:
            await self.matcher.finish(self.ERR_MSG[type(e)])
        except FinishedException:
            # caused by matcher.finish
            raise
        except Exception as e:
            logger.error("Unexpected error", exception=e)
            await self.matcher.finish(f"未知错误: {e}")

    async def handle_list(
        self,
        operator_id: int,
        list_name: str,
        action: Action,
        symtab: dict[str, MessageSegment],
        sudo: bool,
    ):
        lst = await UserListService.find_list(self.group_id, list_name)
        match action.op:
            case Op.SHOW:
                if lst is None:
                    raise ListNotExistsError(list_name)
                parsed = parse_page_or_item_number(action, symtab)
                if parsed.is_page:
                    if parsed.is_all:
                        pagination = None
                    else:
                        pagination = lst.paginate(parsed.num, self.NUM_ITEMS_PER_PAGE)
                    obj = await ChoiceRender.render_list(
                        group_id=self.group_id, userlist=lst, pagination=pagination
                    )
                elif not 0 <= parsed.num < len(lst):
                    raise InvalidIndexError(str(parsed.num + 1))
                else:
                    item = lst.items[parsed.num]
                    if isinstance(item, ReferenceItem):
                        obj = f"[引用] {item.name}"
                    else:
                        obj = item.content
                        obj = await MessageExtension.replace_with_local_image(obj)
                if isinstance(obj, RenderObject):
                    result = ExtMessageSegment.image(
                        obj.render()
                        .thumbnail(max_height=2000, interpolation=Interpolation.LANCZOS)
                        .to_pil()
                    )
                else:
                    result = obj
                await self.matcher.finish(result)
            case Op.REMOVE:
                if lst is None:
                    raise ListNotExistsError(list_name)
                if action.items:
                    raise InvalidItemOpError("删除列表时不可包含其他参数")
                await UserListService.remove_list(
                    self.group_id, list_name, operator_id, sudo
                )
                # display a grayscale image for the deleted list
                obj = await ChoiceRender.render_list(
                    group_id=self.group_id, userlist=lst
                )
                await self.matcher.finish(
                    Message(
                        [
                            ExtMessageSegment.text(f"列表 [{list_name}] 已删除"),
                            ExtMessageSegment.image(
                                obj.render().to_grayscale().to_pil()
                            ),
                        ]
                    )
                )
            case Op.ADD:
                if lst is not None:
                    raise ListExistsError(list_name)
                await UserListService.create_list(self.group_id, list_name, operator_id)
                await self.matcher.finish(f"列表 [{list_name}] 已创建")
            case Op.TOGGLE:
                async with ChoiceConfig.edit(
                    user_id=operator_id, group_id=self.group_id
                ) as cfg:
                    if list_name not in cfg.shortcuts:
                        if lst is None:
                            raise ListNotExistsError(list_name)
                        cfg.shortcuts.append(list_name)
                        op = "添加"
                    else:
                        cfg.shortcuts.remove(list_name)
                        op = "移除"
                await self.matcher.finish(f"列表 [{list_name}] {op}快捷随机")
            case _:
                raise AssertionError("unreachable")

    async def _item_exists(
        self,
        lst: "UserList",
        content: Message,
        pending_msgs: list[Message],
    ) -> tuple[bool, "MessageItem | None", int | None]:
        for i, existing_item in enumerate(lst.items):
            if isinstance(existing_item, MessageItem):
                if await self.comparator(content, existing_item.content):
                    return True, existing_item, i
        for pending in pending_msgs:
            if await self.comparator(content, pending):
                return True, None, None
        return False, None, None

    async def _ref_exists(
        self,
        lst: "UserList",
        ref_name: str,
        pending_refs: list[str],
    ) -> tuple[bool, "ReferenceItem | None", int | None]:
        for i, item in enumerate(lst.items):
            if isinstance(item, ReferenceItem) and item.name == ref_name:
                return True, item, i
        if ref_name in pending_refs:
            return True, None, None
        return False, None, None

    async def random_list_items(self, list_name: str) -> Message | None:
        lst = await UserListService.find_list(self.group_id, list_name)
        if lst is None:
            return

        choices = await lst.expanded_items
        if not choices:
            await self.matcher.finish("(null)")
        choice = random.choice(choices)
        return await MessageExtension.replace_with_local_image(choice)

    async def handle_list_items(
        self,
        operator_id: int,
        list_name: str,
        action: Action,
        symtab: dict[str, MessageSegment],
        sudo: bool,
    ):
        lst = await UserListService.find_list(self.group_id, list_name)

        if lst is None:
            raise ListNotExistsError(list_name)

        # Case 1: no items => choose from list
        if not action.items:
            # random choice
            choices = await lst.expanded_items
            if not choices:
                await self.matcher.finish("(null)")
            choice = random.choice(choices)
            choice = await MessageExtension.replace_with_local_image(choice)
            await self.matcher.finish(choice)

        # Case 2: add/remove items — must be all same type
        ops = set(item.op for item in action.items)
        has_add = bool(ops & {Op.ADD, Op.FORCE_ADD})
        has_remove = Op.REMOVE in ops
        if has_add and has_remove:
            raise InvalidItemOpError("不能同时增删条目，请分两次操作")

        add_msg: list[Message] = []
        add_ref: list[str] = []
        remove_index: list[int] = []
        diff_items: list[DiffEntry] = []
        for item in action.items:
            content = MessageExtension.decode(item.content, symtab)
            if not content:
                continue
            plain_text = content.extract_plain_text()
            match item.op:
                case Op.FORCE_ADD:
                    if item.type == "reference":
                        if not all(seg.is_text() for seg in content):
                            raise NonPlainTextError("引用条目")
                        add_ref.append(plain_text)
                        ref_item = ReferenceItem(
                            name=plain_text, creator_id=operator_id
                        )
                        diff_items.append(
                            DiffEntry("forced", None, ref_item, None)
                        )
                    else:
                        add_msg.append(content)
                        msg_item = MessageItem(
                            content=content, creator_id=operator_id
                        )
                        diff_items.append(
                            DiffEntry("forced", None, msg_item, None)
                        )
                case Op.ADD:
                    if item.type == "reference":
                        if not all(seg.is_text() for seg in content):
                            raise NonPlainTextError("引用条目")
                        exists, ref_item, ref_index = await self._ref_exists(
                            lst, plain_text, add_ref
                        )
                        if exists:
                            if ref_item is not None:
                                diff_items.append(
                                    DiffEntry("skipped", ref_index, ref_item, None)
                                )
                            else:
                                diff_items.append(
                                    DiffEntry(
                                        "skipped", None,
                                        ReferenceItem(name=plain_text, creator_id=operator_id),
                                        None,
                                    )
                                )
                        else:
                            add_ref.append(plain_text)
                            diff_items.append(
                                DiffEntry(
                                    "added", None,
                                    ReferenceItem(name=plain_text, creator_id=operator_id),
                                    None,
                                )
                            )
                    else:
                        exists, msg_item, msg_index = await self._item_exists(
                            lst, content, add_msg
                        )
                        if exists:
                            if msg_item is not None:
                                diff_items.append(
                                    DiffEntry("skipped", msg_index, msg_item, None)
                                )
                            else:
                                diff_items.append(
                                    DiffEntry(
                                        "skipped", None,
                                        MessageItem(content=content, creator_id=operator_id),
                                        None,
                                    )
                                )
                        else:
                            add_msg.append(content)
                            diff_items.append(
                                DiffEntry(
                                    "added", None,
                                    MessageItem(content=content, creator_id=operator_id),
                                    None,
                                )
                            )
                case Op.REMOVE:
                    if plain_text.isdecimal():
                        index = int(plain_text) - 1
                        if not 0 <= index < len(lst.items):
                            raise InvalidIndexError(plain_text)
                        remove_index.append(index)
                        diff_items.append(
                            DiffEntry(
                                "removed", index, lst.items[index], None
                            )
                        )
                    else:
                        for i, lst_item in enumerate(lst.items):
                            if isinstance(lst_item, MessageItem):
                                item_content = lst_item.content
                                if (
                                    all(seg.is_text() for seg in item_content)
                                    and item_content.extract_plain_text()
                                    == plain_text
                                ):
                                    remove_index.append(i)
                                    diff_items.append(
                                        DiffEntry(
                                            "removed", i, lst_item, None
                                        )
                                    )
                                    break
                        else:
                            diff_items.append(
                                DiffEntry(
                                    "remove_failed", None, None, plain_text
                                )
                            )
                case _:
                    raise InvalidItemOpError
        if remove_index:
            await UserListService.remove_by_index(
                self.group_id, list_name, *set(remove_index)
            )
        if add_msg:
            await UserListService.append_message(
                self.group_id, list_name, operator_id, *add_msg
            )
        if add_ref:
            await UserListService.append_reference(
                self.group_id, list_name, operator_id, *add_ref
            )

        num_removed = len(set(remove_index))
        post_remove_len = len(lst.items) - num_removed

        msg_counter = 0
        ref_counter = 0
        indexed_diff: list[DiffEntry] = []
        for entry in diff_items:
            if entry.status in ("added", "forced"):
                if isinstance(entry.item, MessageItem):
                    entry = entry._replace(item_index=post_remove_len + msg_counter)
                    msg_counter += 1
                elif isinstance(entry.item, ReferenceItem):
                    entry = entry._replace(item_index=post_remove_len + len(add_msg) + ref_counter)
                    ref_counter += 1
            indexed_diff.append(entry)
        diff_items = indexed_diff

        if not diff_items:
            await self.matcher.finish(f"列表 [{list_name}] 未更新")

        lst = await UserListService.find_list(self.group_id, list_name)
        if lst is None:
            raise RuntimeError("List missing")

        obj = await ChoiceRender.render_diff(
            group_id=self.group_id, userlist=lst, diff_items=diff_items
        )
        await self.matcher.finish(
            ExtMessageSegment.image(
                obj.render()
                .thumbnail(max_height=2000, interpolation=Interpolation.LANCZOS)
                .to_pil()
            )
        )
