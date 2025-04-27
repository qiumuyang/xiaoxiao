import random

from nonebot.adapters.onebot.v11 import (Bot, GroupMessageEvent, Message,
                                         MessageSegment)
from nonebot.exception import FinishedException
from nonebot.matcher import Matcher

from src.ext import MessageExtension
from src.ext import MessageSegment as ExtMessageSegment
from src.utils.log import logger_wrapper
from src.utils.render import Interpolation
from src.utils.userlist import (ListPermissionError, TooManyItemsError,
                                TooManyListsError, UserListError,
                                UserListService)

from .parse import Action, Op
from .render import ChoiceRender

logger = logger_wrapper(__name__)


class ChoiceError(Exception):

    def __str__(self) -> str:
        return self.args[0]


class ListNotExistsError(ChoiceError):

    def __init__(self, name: str):
        super().__init__(f"列表 [{name}] 不存在")


class ListExistsError(ChoiceError):

    def __init__(self, name: str):
        super().__init__(f"列表 [{name}] 已存在")


class NonPlainTextError(ChoiceError):

    def __init__(self, where: str):
        super().__init__(f"{where}仅允许包含文本")


class InvalidIndexError(ChoiceError):

    def __init__(self, index: str, name: str = "索引"):
        super().__init__(f"无效的{name}: {index}")


class InvalidListNameError(ChoiceError):

    def __init__(self, reason: str):
        super().__init__(reason)


class InvalidItemOpError(ChoiceError):

    def __init__(self):
        super().__init__("列表项目仅可使用+/-操作")


def extract_plain_text(content: str,
                       symtab: dict[str, MessageSegment],
                       exception: Exception | None = None):
    message = MessageExtension.decode(content, symtab)
    if any(not seg.is_text() for seg in message) and exception is not None:
        raise exception
    return message.extract_plain_text()


def parse_page_number(
    action: Action,
    symtab: dict[str, MessageSegment],
) -> int:
    if not action.items:
        return 0
    page_str = extract_plain_text(action.items[0].content, symtab,
                                  NonPlainTextError("页码"))
    if not page_str.isdecimal():
        raise InvalidIndexError(page_str, "页码")
    return int(page_str) - 1


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
                case Op.SHOW | Op.ADD | Op.REMOVE:
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
                page = parse_page_number(action, symtab)
                pagination = lst.paginate(page, self.NUM_ITEMS_PER_PAGE)
                obj = await ChoiceRender.render_list(group_id=self.group_id,
                                                     userlist=lst,
                                                     pagination=pagination)
                await self.matcher.finish(
                    ExtMessageSegment.image(obj.render().thumbnail(
                        max_height=2000,
                        interpolation=Interpolation.LANCZOS).to_pil()))
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
            case _:
                assert False, "unreachable"

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
        for item in action.items:
            content = MessageExtension.decode(item.content, symtab)
            if not content:
                continue
            plain_text = content.extract_plain_text()
            match item.op:
                case Op.ADD:
                    if item.type == "reference":
                        if not all(seg.is_text() for seg in content):
                            raise NonPlainTextError("引用条目")
                        add_ref.append(plain_text)
                    else:
                        add_msg.append(content)
                case Op.REMOVE:
                    # TODO: support remove by text
                    if not plain_text.isdecimal():
                        raise InvalidIndexError(plain_text)
                    index = int(plain_text) - 1
                    if not 0 <= index < len(lst.items):
                        raise InvalidIndexError(plain_text)
                    remove_index.append(index)
                case _:
                    raise InvalidItemOpError

        if remove_index:
            # perform remove before add
            await UserListService.remove_by_index(self.group_id, list_name,
                                                  *remove_index)
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
        await self.matcher.finish(f"列表 [{list_name}] 已更新")
