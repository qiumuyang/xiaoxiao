import asyncio
from collections import defaultdict
from datetime import datetime
from typing import Any

from nonebot import CommandGroup, on_command, on_message, on_notice
from nonebot.adapters import Bot, Message
from nonebot.adapters.onebot.v11 import Bot as OnebotBot
from nonebot.adapters.onebot.v11 import GroupMessageEvent
from nonebot.adapters.onebot.v11 import Message as Message_
from nonebot.adapters.onebot.v11 import MessageEvent
from nonebot.adapters.onebot.v11.event import PokeNotifyEvent, Reply
from nonebot.params import CommandArg
from nonebot.typing import T_State
from pymongo.errors import DocumentTooLarge

from src.ext import MessageSegment, api, get_group_member_name
from src.ext.permission import ADMIN, SUPERUSER
from src.ext.rule import RateLimit, RateLimiter, enabled, ratelimit, reply
from src.utils.doc import CommandCategory, command_doc
from src.utils.message import ReceivedMessageTracker, SentMessageTracker

from .ask import Ask
from .config import (RandomResponseConfig, toggle_group_response_request,
                     toggle_user_response)
from .history import History
from .interact import RandomResponse

record_message = on_message(priority=0, block=False)
random_response = on_message(priority=10,
                             block=False,
                             rule=enabled(RandomResponseConfig))
record_unhandled_message = on_message(priority=255, block=True)

recall_message = on_command("撤回", aliases={"快撤回"}, block=True)
answer_ask = on_command("问",
                        force_whitespace=False,
                        priority=2,
                        block=True,
                        rule=ratelimit("问", type="user", seconds=2))
debug_ask = on_command("cut", force_whitespace=True, block=True)
message_rank = on_command("发言排行",
                          force_whitespace=True,
                          block=True,
                          rule=ratelimit("发言排行", type="group", seconds=15))
disable_response = on_command("闭嘴",
                              aliases={"闭菊"},
                              force_whitespace=True,
                              block=True)
enable_response = on_command("张嘴",
                             aliases={"张菊", "开菊", "开嘴"},
                             force_whitespace=True,
                             block=True)
poke_source = on_notice()

message_trace = CommandGroup("trace", block=True)
trace_single = message_trace.command(
    tuple(),
    force_whitespace=True,
    rule=ratelimit("trace_single", type="group", seconds=5),
)
trace_search = message_trace.command(
    "search",
    force_whitespace=True,
    rule=ratelimit("trace_search", type="group", seconds=5),
)

check_reply = reply()


@Bot.on_called_api
async def handle_api_result(bot: Bot, exception: Exception | None, api: str,
                            data: dict[str, Any], result: Any):
    if exception:
        return

    match api:
        case "send_msg":
            session_id = SentMessageTracker.get_session_id(data)
            try:
                await SentMessageTracker.add(session_id, result["message_id"],
                                             data["message"])
            except DocumentTooLarge:
                await SentMessageTracker.add(session_id, result["message_id"],
                                             Message_("[过大消息]"))


@recall_message.handle()
@command_doc("撤回", aliases={"快撤回"}, category=CommandCategory.CHAT)
async def _(bot: Bot, event: MessageEvent, state: T_State):
    """
    撤回{bot}消息 / 由{bot}撤回你的消息

    Special:
        激活时空锚点修正协议…正在执行数据擦除——执行莱█生█████密通讯协议v3.███4

    Usage:
        **@{bot}** {cmd}         - 撤回最近一条**由你引起**的消息
        [引用{bot}] {cmd}        - 撤回被引用且**由你引起**的消息
        [引用{bot}] {cmd}        - 撤回被引用的消息 ***(仅限发送者为管理员)***
        [引用发送者] {cmd}      - 撤回被引用的消息 ***(仅限{bot}比发送者权限更高)***
    """
    session_id, group_prefix = SentMessageTracker.get_session_id_or_prefix(
        event)

    # directly called without reply specified (+ to_me)
    if not await check_reply(bot, event, state) and event.is_tome():
        message_id = await SentMessageTracker.remove(session_id)
        if message_id is not None:
            await bot.delete_msg(message_id=message_id)
        await recall_message.finish()

    # try to recall the replied message
    # cases:
    # - replied message sent by BOT:
    #   - check if the message is triggered by the same user
    #   - check if the user has higher permission
    # - replied message sent by CURRENT USER:
    #   - check bot permission
    reply: Reply = state["reply"]
    if str(reply.sender.user_id) == bot.self_id:  # bot.self_id is a string
        session_id, group_prefix = SentMessageTracker.get_session_id_or_prefix(
            event)

        # user exact match
        message_id = await SentMessageTracker.remove(session_id,
                                                     reply.message_id)
        if message_id is not None:
            await bot.delete_msg(message_id=message_id)
            await recall_message.finish()
        # superuser or admin match
        perm = SUPERUSER | ADMIN
        if await perm(bot, event):
            message_id = await SentMessageTracker.remove_prefix(
                group_prefix, reply.message_id)
            if message_id is not None:
                await bot.delete_msg(message_id=message_id)
                await recall_message.finish()
    elif reply.sender.user_id == event.user_id and isinstance(
            event, GroupMessageEvent):
        mem = await bot.get_group_member_info(group_id=event.group_id,
                                              user_id=int(bot.self_id))
        if mem["role"] in ("owner", "admin"):
            await bot.delete_msg(message_id=reply.message_id)


@record_message.handle()
async def _(event: GroupMessageEvent):
    """Called before all other handlers with priority 0.

    Suppose the message will be handled by other handlers.
    """
    await ReceivedMessageTracker.add(event.user_id,
                                     event.group_id,
                                     event.message_id,
                                     event.message,
                                     handled=True)
    # should not finish here


@record_unhandled_message.handle()
async def _(event: GroupMessageEvent):
    """Called after all other handlers with priority 255.

    If the message goes through all handlers here, it is unhandled.
    """
    await ReceivedMessageTracker.add(event.user_id,
                                     event.group_id,
                                     event.message_id,
                                     event.message,
                                     handled=False)
    await record_unhandled_message.finish()


@answer_ask.handle()
@command_doc("问", category=CommandCategory.CHAT)
async def _(bot: OnebotBot, event: GroupMessageEvent):
    """
    根据提问模板，随机填充内容作为回答

    Special:
        加载**PRTS**问答协议//启动伪随机数生成器…正在注入语义重构算法

        （注：输出结果包含63%标准话术与28%冗余数据）

    Usage:
        {cmd}`<模板>`    - 使用模板进行回答

        :syntax 什么:      随机选取一条语料
        :syntax 什么<k>:   随机选取一条长度为`k`的语料
        :syntax 干什么:    随机选取一条以动词开头的语料
        :syntax 为什么:    随机选取一条语料 => 因为...，所以
        :syntax 谁:        随机选取群友昵称
        :syntax 几:        随机数 `[0, 10]` （在词语中可能有特殊处理）
        :syntax 多少:      随机数 `[0, 100]`
        :syntax x不x:      随机选择 `x` 或 `不x`
        :syntax a还是b:    随机选择 `a` 或 `b` <br>（对整句生效，如有需要请用括号包裹选项）
        :syntax /:          强制断句，不会出现在结果中
        :syntax \\:         强制输出下一符号，不会出现在结果中
        :syntax (<捕获>)...\\k: 引用第`k`组括号捕获的内容
        :syntax 人称替换:  默认对第一第二人称进行替换

    Examples:
        >>> 问谁什么，谁干不干什么，谁为什么什么

        >>> 问今天是星期几

        # 使用\\直接输出“你”，避免人称替换
        >>> 问\\你群有多少什么2

        # 使用\\1和\\2重复前文括号捕获的内容
        >>> 问(什么1)我所欲也，(什么2)亦我所欲也。二者不可得兼，舍\\1而取\\2者也。

    Notes:
        - 捕获组序号从1开始，以左括号出现顺序为准
    """
    result = await Ask(bot, event.group_id, event.message).answer()
    if result:
        await answer_ask.finish(result)


@debug_ask.handle()
@command_doc("cut", category=CommandCategory.UTILITY)
async def _(bot: OnebotBot,
            event: GroupMessageEvent,
            arg: Message = CommandArg()):
    """
    显示输入的分词结果

    Special:
        “苯环的碳碳键键能能否否定定论一或定论二”

    Usage:
        {cmd} `<文本>`  - 显示文本的分词结果
        可以用于检查`问什么`没有回复的原因

    Examples:
        >>> {cmd} 问起不起床
        问起/不/起床
    """
    if (input := arg.extract_plain_text()):
        await debug_ask.finish("/".join(Ask.pseg_cut(input)))


@message_rank.handle()
@command_doc("发言排行", category=CommandCategory.STATISTICS)
async def _(bot: OnebotBot, event: GroupMessageEvent):
    """
    显示今日群内发言排行

    Special:
        \\- “为什么{bot}不在排行里”
        \\- “好问题，我也想知道”
    """
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    messages = await ReceivedMessageTracker.find(group_id=event.group_id,
                                                 since=today)
    user_messages = defaultdict(int)
    for message in messages:
        user_messages[message.user_id] += 1
    user_messages = sorted(user_messages.items(), key=lambda x: -x[1])

    group_info = await bot.get_group_info(group_id=event.group_id,
                                          no_cache=True)
    group_name = group_info["group_name"]
    date = today.strftime("%m-%d")
    if not user_messages:
        await message_rank.finish("今天还没有人发言哦")
    # top = min(10, group_info["member_count"] // 2)
    # member_count seems problematic for now
    result = f"{group_name} {date} 发言排行\n"
    top = 10
    top_uid, top_messages = zip(*user_messages[:top])
    names = await asyncio.gather(*[
        get_group_member_name(group_id=event.group_id, user_id=user_id)
        for user_id in top_uid
    ])
    ranking = "\n".join(
        f"{i}. {member} {count}"
        for i, (member, count) in enumerate(zip(names, top_messages), 1))
    await message_rank.finish(result + ranking)


@random_response.handle()
@command_doc("随机回复", category=CommandCategory.CHAT, is_placeholder=True)
async def _(event: GroupMessageEvent,
            ratelimit: RateLimiter = RateLimit("随机回复",
                                               type="group",
                                               seconds=10)):
    """
    根据预设规则，随机回复消息

    Special:
        激活非确定性应答矩阵......载入模糊逻辑引擎//正在执行响应概率分布计算。

    Usage:
        ~~没有任何用法，~~你只需要说话就可能随机触发

        触发规则：
        1. 随机复读
        2. 提取最近消息中的关键词，随机匹配群内历史语料重放

    Note:
        - 本功能是{bot}*胡言乱语*的主要来源
    """
    resp = await RandomResponse.response(event.group_id, event.message)
    if resp:
        resp = MessageSegment.normalize(resp)
        if resp and ratelimit.try_acquire():
            await random_response.send(resp)


@trace_single.handle()
@command_doc("trace", category=CommandCategory.UTILITY)
async def _(bot: OnebotBot,
            event: GroupMessageEvent,
            arg: Message = CommandArg()):
    """
    查看过往消息

    Special:
        启动历史数据回溯协议……正在扫描加密通讯日志（警告：需要凯尔希权限认证）
        ——已定位至目标时间轴。

    Usage:
        {cmd} `<k>` - 显示最近第k条消息 (从1开始，包括*{bot}*和*被撤回*的消息)
        {cmd}.search `<条件>`...  - 搜索最近{History.MAX_HISTORY_INTERVAL_DAYS}天内的消息 (至多{History.FORWARD_MESSAGE_LIMIT}条)

        可用条件：
        - `@<用户>` 指定发送者
        - `:bot:` *{bot}*发送消息 (默认不包含)
        - `:image:` 图片消息
        - `:regex:<正则>` 正则表达式可匹配文本内容
        - `<关键词>` 文本内容包含关键词

        同时指定多个正则/关键词时，需满足所有条件 (ALL)

    Examples:
        >>> {cmd} 10

        >>> {cmd}.search 羡慕

        >>> {cmd}.search @someone :regex:[a-zA-Z]+
    """
    if (input := arg.extract_plain_text()) and input.isdecimal():
        index = int(input)
    else:
        index = 1

    result = await History.find_single_message(bot,
                                               event.group_id,
                                               index=index)
    if isinstance(result, Message) or result is None:
        await trace_single.finish(result)
    else:
        await api.send_group_forward_msg(event.group_id, [result])


@trace_search.handle()
async def _(bot: OnebotBot,
            event: GroupMessageEvent,
            arg: Message = CommandArg()):
    senders = []
    keywords = []
    for seg in arg:
        segment = MessageSegment.from_onebot(seg)
        if segment.is_at():
            senders.append(segment.extract_at())
        elif segment.is_text():
            keywords.extend(segment.extract_text_args())

    results = await History.find(bot,
                                 event.group_id,
                                 senders=senders,
                                 keywords=keywords)
    if results:
        await api.send_group_forward_msg(event.group_id, results)


@disable_response.handle()
@command_doc("闭嘴", aliases={"闭菊"}, category=CommandCategory.CHAT)
async def _(event: GroupMessageEvent,
            notice_lim: RateLimiter = RateLimit("随机回复关闭提示",
                                                type="group",
                                                seconds=600)):
    """
    关闭{bot}的随机回复

    Special:
        切换应答协议状态：███模式已终止……警告，即将回滚至初始配置文件。

    Usage:
        {cmd}        - 投票关闭群内随机回复 (需{RandomResponseConfig.num_reqs_to_toggle}人同意)
        @{bot} {cmd} - 对个人关闭随机回复

    Note:
        - 可使用`{cmdhelp} 随机回复`查看功能信息
    """
    if event.is_tome():
        if await toggle_user_response(user_id=event.user_id, enabled=False):
            await disable_response.finish("鸮鸮对你的随机回复已关闭")
        return
    result = await toggle_group_response_request(user_id=event.user_id,
                                                 group_id=event.group_id,
                                                 enabled=False)
    if type(result) is int:
        requests = RandomResponseConfig.num_reqs_to_toggle
        prompt = f"正在关闭鸮鸮的随机回复，进度 {result}/{requests}"
        if notice_lim.try_acquire():
            prompt += "\n（@鸮鸮 可以对个人关闭）"
        await disable_response.finish(prompt)
    if result:
        await disable_response.finish("鸮鸮的随机回复已关闭")


@enable_response.handle()
@command_doc("张嘴", aliases={"张菊", "开菊", "开嘴"}, category=CommandCategory.CHAT)
async def _(event: GroupMessageEvent):
    """
    开启{bot}的随机回复

    Special:
        切换应答协议状态：███模式已激活……警告，即将回滚至初始配置文件。

    Usage:
        {cmd}        - 投票开启群内随机回复 (需{RandomResponseConfig.num_reqs_to_toggle}人同意)
        @{bot} {cmd} - 对个人开启随机回复

    Note:
        - 可使用`{cmdhelp} 随机回复`查看功能信息
    """
    user_toggled = await toggle_user_response(user_id=event.user_id,
                                              enabled=True)
    result = await toggle_group_response_request(user_id=event.user_id,
                                                 group_id=event.group_id,
                                                 enabled=True)
    requests = RandomResponseConfig.num_reqs_to_toggle
    if user_toggled:
        prompt = "鸮鸮对你的随机回复已开启"
        if type(result) is int:  # group disabled
            prompt += f"\n群内未开启，进度 {result}/{requests}"
        await enable_response.finish(prompt)
    if type(result) is int:
        prompt = f"正在开启鸮鸮的随机回复，进度 {result}/{requests}"
        await enable_response.finish(prompt)
    if result is True:
        await enable_response.finish("鸮鸮的随机回复已开启")


@poke_source.handle()
@command_doc("跟戳", category=CommandCategory.CHAT, is_placeholder=True)
async def _(bot: Bot,
            event: PokeNotifyEvent,
            ratelimiter: RateLimiter = RateLimit("poke",
                                                 type="group",
                                                 seconds=10)):
    """
    跟随其他群友戳一戳

    Special:
        检测到生物特征接触事件……正在克隆操作者行为模式
        （递归指令已排除，博士无需担心便携式战术终端轰鸣的可能）
    """
    if int(bot.self_id) in (event.user_id, event.target_id):
        return
    if not event.group_id:
        return
    if ratelimiter.try_acquire():
        await bot.call_api("group_poke",
                           group_id=event.group_id,
                           user_id=event.target_id)
