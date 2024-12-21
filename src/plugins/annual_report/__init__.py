from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent

from src.ext import MessageSegment

from .render import AnnualReportRenderer
from .statistics import AnnualStatistics

annual_report = on_command("年度报告", block=True, force_whitespace=True)
annual_report_group = on_command("群年度报告", block=True, force_whitespace=True)


@annual_report.handle()
async def _(bot: Bot, event: GroupMessageEvent):
    statistics = await AnnualStatistics.user(event.user_id, event.group_id)
    try:
        mem = await bot.get_group_member_info(group_id=event.group_id,
                                              user_id=event.user_id)
        name = mem["card"] or mem["nickname"]
    except:
        name = f"用户{event.user_id}"
    result = await AnnualReportRenderer.render_user(statistics, event.user_id,
                                                    name, event.group_id)
    await annual_report.finish(MessageSegment.image(result.render().to_pil()))


@annual_report_group.handle()
async def _(bot: Bot, event: GroupMessageEvent):
    await annual_report.finish("敬请期待")
