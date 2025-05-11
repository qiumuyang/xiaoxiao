from nonebot import on_command, on_message
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, Message
from nonebot.adapters.onebot.v11.event import Reply
from nonebot.matcher import Matcher
from nonebot.params import CommandArg
from nonebot.typing import T_State

from src.ext import MessageExtension, MessageType
from src.ext.on import on_reply
from src.ext.permission import ADMIN, SUPERUSER
from src.ext.rule import not_reply
from src.utils.doc import CommandCategory, command_doc

from .choice import ChoiceConfig, ChoiceHandler
from .parse import Action, Op, parse_action

make_choice_reply = on_reply(("选择困难", "xzkn"), block=True)
make_choice = on_command("选择困难",
                         rule=not_reply(),
                         aliases={"xzkn"},
                         block=True,
                         force_whitespace=True)
choice_shortcut = on_message(priority=2, block=False)


async def _parse(cmd: str, matcher: type[Matcher]) -> Action | None:
    try:
        return parse_action(cmd)
    except ValueError as e:
        if "No escaped character" in str(e):
            await matcher.finish("缺少待转义的字符")
        if "No closing quotation" in str(e):
            await matcher.finish("引号未闭合")
        await matcher.finish("语法错误")


@make_choice.handle()
@command_doc("选择困难", aliases={"xzkn"}, category=CommandCategory.UTILITY)
async def _(bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()):
    """
    解决你的选择困难症

    Usage:
        {cmd}                            -  显示列表总览
        {cmd} +|-`<列表名>`             -  添加/删除列表
        {cmd} `<列表名>` +`<内容>` ...  -  添加内容到指定列表
        {cmd} `<列表名>` -`<序号>` ...  -  删除列表中指定序号的项目
        {cmd} `<列表名>`                -  随机选择列表中的一个项目
        {cmd} ?`<列表名>` [页码]        -  显示指定列表内容
        {cmd} *`<列表名>`                -  设置/取消指定列表快捷访问
        `引用` {cmd} `<列表名>` +       -  将引用消息添加到指定列表
        其中:
        * `<内容>`允许**无嵌套引用**其他列表，用`[列表名]`表示
        * 添加带有**空格**的内容时，需要使用引号`"`将其包裹
        * 包含指令字符(`+` `-` `?` `*`)且会引起歧义时，需要在其之前添加转义符`\\`

    Examples:
        >>> {cmd} +炸鸡汉堡
        >>> {cmd} 炸鸡汉堡 +肯德基 +麦当劳 +"Burger King"
        >>> {cmd} 炸鸡汉堡 -2

        >>> {cmd} +中式快餐
        >>> {cmd} 中式快餐 +老乡鸡 +真功夫

        >>> {cmd} +吃什么
        >>> {cmd} 吃什么 +[炸鸡汉堡] +[中式快餐]
        >>> {cmd} 吃什么  # 会从炸鸡汉堡和中式快餐的非引用内容中随机选择

    Note:
        - 慎用删除功能，仅创建者/管理员可用，删除后列表所有内容将被清空，**不可恢复**
    """
    args = MessageExtension.discard(args, "reply")
    cmd, symtab = MessageExtension.encode(args)

    action = await _parse(cmd, make_choice)

    handler = ChoiceHandler(bot, event, make_choice)

    if action is None:
        await handler.overview()
    else:
        rule = SUPERUSER | ADMIN
        await handler.execute(event.user_id,
                              action,
                              symtab,
                              sudo=await rule(bot, event))


@make_choice_reply.handle()
async def _(bot: Bot,
            event: GroupMessageEvent,
            state: T_State,
            args: Message = CommandArg()):
    args = MessageExtension.discard(args, "reply")
    cmd, symtab = MessageExtension.encode(args)

    action = await _parse(cmd, make_choice_reply)
    if not action:
        return
    if (not action.items or len(action.items) != 1 or action.items[0].content):
        await make_choice_reply.finish(f"选择困难快捷添加语法: <列表名> {Op.ADD}")

    # rewrite action with reply content
    reply: Reply = state["reply"]
    content = MessageExtension.filter(reply.message, MessageType.TEXT,
                                      MessageType.AT, MessageType.FACE,
                                      MessageType.MFACE, MessageType.IMAGE)
    content = MessageExtension.fix_mface(content)
    s, symtab_content = MessageExtension.encode(content, start=len(symtab))
    action.items[0] = action.items[0].with_content(s)

    handler = ChoiceHandler(bot, event, make_choice_reply)
    await handler.execute(event.user_id,
                          action,
                          symtab | symtab_content,
                          sudo=await (SUPERUSER | ADMIN)(bot, event))


@choice_shortcut.handle()
async def _(bot: Bot, event: GroupMessageEvent):
    if not all(seg.is_text() for seg in event.message):
        return
    name = event.message.extract_plain_text()
    cfg = await ChoiceConfig.get(user_id=event.user_id,
                                 group_id=event.group_id)
    if name in cfg.shortcuts:
        handler = ChoiceHandler(bot, event, make_choice_reply)
        if msg := await handler.random_list_items(name):
            await choice_shortcut.finish(msg)
