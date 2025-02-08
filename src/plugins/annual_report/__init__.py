from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, Message
from nonebot.params import CommandArg

from src.ext import MessageSegment, get_group_member_name
from src.utils.doc import CommandCategory, command_doc

from .render import AnnualReportRenderer
from .statistics import AnnualStatistics

annual_report = on_command("年度报告", block=True, force_whitespace=True)
annual_report_group = on_command("群年度报告", block=True, force_whitespace=True)


@annual_report.handle()
@command_doc("年度报告", category=CommandCategory.STATISTICS)
async def _(bot: Bot, event: GroupMessageEvent, arg_: Message = CommandArg()):
    """
    生成个人本群年度活跃报告

    Special:
        正在激活年度数据汇总模块……数据采集中……请稍候。

        系统将全面解析您在本群的活动轨迹。

    Usage:
        {cmd}          - 查看自己的年度报告
        {cmd} `@用户`  - 查看群友的年度报告
    """
    user_id = event.user_id
    for ob_seg in arg_:
        seg = MessageSegment.from_onebot(ob_seg)
        if seg.is_at():
            user_id = seg.extract_at()
            break
    statistics = await AnnualStatistics.user(user_id=user_id,
                                             group_id=event.group_id)
    name = await get_group_member_name(group_id=event.group_id,
                                       user_id=user_id)
    result = await AnnualReportRenderer.render_user(statistics, user_id, name,
                                                    event.group_id)
    await annual_report.finish(MessageSegment.image(result.render().to_pil()))


@annual_report_group.handle()
@command_doc("群年度报告", category=CommandCategory.STATISTICS)
async def _(bot: Bot, event: GroupMessageEvent):
    """
    生成本群年度活跃报告

    Special:
        正在激活年度数据汇总模块……数据采集中……

        请稍候。系统将全面解析本群的活动轨迹。

    Usage:
        {cmd} - 查看本群的年度报告
    """
    statistics = await AnnualStatistics.group(group_id=event.group_id)
    info = await bot.get_group_info(group_id=event.group_id)
    result = await AnnualReportRenderer.render_group(statistics,
                                                     event.group_id,
                                                     info["group_name"])
    await annual_report.finish(MessageSegment.image(result.render().to_pil()))
