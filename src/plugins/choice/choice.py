import random

from nonebot.adapters.onebot.v11 import (Bot, GroupMessageEvent, Message,
                                         MessageSegment)
from nonebot.exception import FinishedException
from nonebot.matcher import Matcher

from src.ext import MessageExtension
from src.ext import MessageSegment as ExtMessageSegment
from src.utils.log import logger_wrapper
from src.utils.render import Interpolation, RenderObject
from src.utils.userlist import (ListPermissionError, MessageItem,
                                ReferenceItem, TooManyItemsError,
                                TooManyListsError, UserListError,
                                UserListService)

from .config import ChoiceConfig
from .exception import *
from .parse import Action, Op
from .render import ChoiceRender

logger = logger_wrapper(__name__)

IS_PAGE = bool


def extract_plain_text(content: str,
                       symtab: dict[str, MessageSegment],
                       exception: Exception | None = None):
    message = MessageExtension.decode(content, symtab)
    if any(not seg.is_text() for seg in message) and exception is not None:
        raise exception
    return message.extract_plain_text()


def parse_page_or_item_number(
    action: Action,
    symtab: dict[str, MessageSegment],
) -> tuple[int, IS_PAGE]:
    if not action.items:
        return 0, True
    s = extract_plain_text(action.items[0].content, symtab,
                           NonPlainTextError("页码/索引"))
    if s.startswith("#"):
        if not s[1:].isdecimal():
            raise InvalidIndexError(s[1:], "索引")
        return int(s[1:]) - 1, False
    if not s.isdecimal():
        raise InvalidIndexError(s, "页码")
    return int(s) - 1, True


class ChoiceHandler:

    MAX_LIST_NAME_LEN = 20
    NUM_ITEMS_PER_PAGE = ChoiceRender.PAGE_SIZE

    ERR_MSG = {
        ListPermissionError: "仅创建者或管理员可进行该操作",
        TooManyListsError: "列表数已达上限",
        TooManyItemsError: "该列表中项目数量已达上限",
    }

    def __init__(self, bot: Bot, event: GroupMessageEvent,
                 matcher: type[Matcher]):
        self.bot = bot
        self.event = event
        self.matcher = matcher

    @property
    def group_id(self):
        return self.event.group_id

    async def overview(self):
        lst_meta = await UserListService.find_all_list_meta(self.group_id)
        if not lst_meta:
            await self.matcher.finish("还没有创建任何列表")
        obj = await ChoiceRender.render_list_overview(*lst_meta)
        await self.matcher.finish(
            ExtMessageSegment.image(obj.render().to_pil()))

    async def execute(
        self,
        operator_id: int,
        action: Action,
        symtab: dict[str, MessageSegment],
        sudo: bool = False,
    ):
        try:
            lst_name = extract_plain_text(action.name, symtab,
                                          NonPlainTextError("列表名称"))
            if len(lst_name) > self.MAX_LIST_NAME_LEN:
                raise InvalidListNameError(
                    f"列表名称至多包含{self.MAX_LIST_NAME_LEN}个字符")
            if not lst_name:
                raise InvalidListNameError("列表名称不可为空")

            match action.op:
                case Op.SHOW | Op.ADD | Op.REMOVE | Op.TOGGLE:
                    handler = self.handle_list
                case Op.NONE:
                    handler = self.handle_list_items
                case _:
                    assert False, "unexpected list operation"
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
            await self.matcher.finish("未知错误")

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
                num, is_page = parse_page_or_item_number(action, symtab)
                if is_page:
                    pagination = lst.paginate(num, self.NUM_ITEMS_PER_PAGE)
                    obj = await ChoiceRender.render_list(
                        group_id=self.group_id,
                        userlist=lst,
                        pagination=pagination)
                elif not 0 <= num < len(lst):
                    raise InvalidIndexError(str(num + 1))
                else:
                    item = lst.items[num]
                    if isinstance(item, ReferenceItem):
                        obj = f"[引用] {item.name}"
                    else:
                        obj = item.content
                        obj = await MessageExtension.replace_with_local_image(
                            obj)
                if isinstance(obj, RenderObject):
                    result = ExtMessageSegment.image(obj.render().thumbnail(
                        max_height=2000,
                        interpolation=Interpolation.LANCZOS).to_pil())
                else:
                    result = obj
                await self.matcher.finish(result)
            case Op.REMOVE:
                if lst is None:
                    raise ListNotExistsError(list_name)
                await UserListService.remove_list(self.group_id, list_name,
                                                  operator_id, sudo)
                # display a grayscale image for the deleted list
                obj = await ChoiceRender.render_list(group_id=self.group_id,
                                                     userlist=lst)
                await self.matcher.finish(
                    Message([
                        ExtMessageSegment.text(f"列表 [{list_name}] 已删除"),
                        ExtMessageSegment.image(
                            obj.render().to_grayscale().to_pil())
                    ]))
            case Op.ADD:
                if lst is not None:
                    raise ListExistsError(list_name)
                await UserListService.create_list(self.group_id, list_name,
                                                  operator_id)
                await self.matcher.finish(f"列表 [{list_name}] 已创建")
            case Op.TOGGLE:
                async with ChoiceConfig.edit(user_id=operator_id,
                                             group_id=self.group_id) as cfg:
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
                assert False, "unreachable"

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

        # Case 2: add/remove items
        add_msg: list[Message] = []
        add_ref: list[str] = []
        remove_index: list[int] = []
        remove_fail: list[str] = []
        updated = False
        for item in action.items:
            content = MessageExtension.decode(item.content, symtab)
            if not content:
                continue
            plain_text = content.extract_plain_text()
            match item.op:
                case Op.ADD:
                    updated = True
                    if item.type == "reference":
                        if not all(seg.is_text() for seg in content):
                            raise NonPlainTextError("引用条目")
                        add_ref.append(plain_text)
                    else:
                        add_msg.append(content)
                case Op.REMOVE:
                    if plain_text.isdecimal():
                        index = int(plain_text) - 1
                        if not 0 <= index < len(lst.items):
                            raise InvalidIndexError(plain_text)
                        remove_index.append(index)
                        updated = True
                    else:
                        for i, lst_item in enumerate(lst.items):
                            if isinstance(lst_item, MessageItem):
                                content = lst_item.content
                                if all(seg.is_text() for seg in
                                       content) and content.extract_plain_text(
                                       ) == plain_text:
                                    remove_index.append(i)
                                    updated = True
                                    break  # only remove the first match
                        else:
                            remove_fail.append(plain_text)
                case _:
                    raise InvalidItemOpError
        if remove_index:
            # perform remove before add
            await UserListService.remove_by_index(self.group_id, list_name,
                                                  *set(remove_index))
        if add_msg:
            await UserListService.append_message(self.group_id, list_name,
                                                 operator_id, *add_msg)
        if add_ref:
            await UserListService.append_reference(self.group_id, list_name,
                                                   operator_id, *add_ref)

        lst = await UserListService.find_list(self.group_id, list_name)
        if lst is None:
            raise RuntimeError("List missing")

        # TODO: render diff instead of whole list
        # obj = await ChoiceRender.render_list(group_id=self.group_id,
        #                                      userlist=lst)
        # await self.matcher.finish(
        #     ExtMessageSegment.image(obj.render().to_pil()))

        if updated:
            if not remove_fail:
                await self.matcher.finish(f"列表 [{list_name}] 已更新")
            else:
                await self.matcher.finish(f"列表 [{list_name}] 已更新\n"
                                          f"未匹配的条目: {', '.join(remove_fail)}")
        else:
            await self.matcher.finish(f"列表 [{list_name}] 未更新")
