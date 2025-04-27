from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, Message
from nonebot.params import CommandArg

from src.ext import MessageExtension
from src.ext.permission import admin
from src.utils.doc import CommandCategory, command_doc

from .choice import ChoiceHandler
from .parse import parse_action

make_choice = on_command("选择困难",
                         aliases={"xzkn"},
                         block=True,
                         force_whitespace=True)


@make_choice.handle()
@command_doc("选择困难", aliases={"xzkn"}, category=CommandCategory.UTILITY)
async def _(bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()):
    """
    解决你的选择困难症

    Usage:
        {cmd} +|-`<列表名>`             -  添加/删除列表
        {cmd} `<列表名>` +`<内容>` ...  -  添加内容到指定列表
        {cmd} `<列表名>` -`<序号>` ...  -  删除列表中指定序号的项目
        {cmd} `<列表名>`                -  随机选择列表中的一个项目
        {cmd} ?`<列表名>` [页码]        -  显示指定列表内容
        其中:
        * `<内容>`允许**无嵌套引用**其他列表，用`[列表名]`表示
        * 添加带有**空格**的内容时，需要使用引号`"`将其包裹

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
    cmd, symtab = MessageExtension.encode(args)

    try:
        action = parse_action(cmd)
    except ValueError as e:
        if "No escaped character" in str(e):
            await make_choice.finish("缺少待转义的字符")
        if "No closing quotation" in str(e):
            await make_choice.finish("引号未闭合")
        await make_choice.finish("语法错误")

    handler = ChoiceHandler(bot, event, make_choice)

    if action is None:
        # TODO: show all lists
        await make_choice.finish("WIP")

    await handler.execute(event.user_id,
                          action,
                          symtab,
                          sudo=await admin(event))
