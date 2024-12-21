from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, Message
from nonebot.params import CommandArg

from src.ext import MessageSegment

from .render import AnnualReportRenderer
from .statistics import AnnualStatistics

annual_report = on_command("年度报告", block=True, force_whitespace=True)
annual_report_group = on_command("群年度报告", block=True, force_whitespace=True)


@annual_report.handle()
async def _(bot: Bot, event: GroupMessageEvent, arg_: Message = CommandArg()):
    # if no args, show current user report
    # if at someone, show target user report
    user_id = event.user_id
    for ob_seg in arg_:
        seg = MessageSegment.from_onebot(ob_seg)
        if seg.is_at():
            user_id = seg.extract_at()
            break
    statistics = await AnnualStatistics.user(user_id, event.group_id)
    try:
        mem = await bot.get_group_member_info(group_id=event.group_id,
                                              user_id=user_id)
        name = mem["card"] or mem["nickname"]
    except:
        name = f"用户{user_id}"
    result = await AnnualReportRenderer.render_user(statistics, user_id, name,
                                                    event.group_id)
    await annual_report.finish(MessageSegment.image(result.render().to_pil()))


@annual_report_group.handle()
async def _(bot: Bot, event: GroupMessageEvent):
    statistics = await AnnualStatistics.group(event.group_id)
    info = await bot.get_group_info(group_id=event.group_id)
    result = await AnnualReportRenderer.render_group(statistics,
                                                     event.group_id,
                                                     info["group_name"])
    await annual_report.finish(MessageSegment.image(result.render().to_pil()))
