from nonebot import on_command, on_notice
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent
from nonebot.permission import SUPERUSER

from src.ext.event import GroupReactionAdd, GroupReactionAddEvent
from src.ext.message import (Button, ButtonAction, ButtonStyle,
                             MessageExtension, MessageSegment)

send_keyboard = on_command("keyboard", permission=SUPERUSER, block=True)
send_reply = on_command("reply_me", permission=SUPERUSER, block=True)
# cannot use default permission since notice event does not have user_id
follow_reaction = on_notice()


@send_keyboard.handle()
async def _(bot: Bot, event: GroupMessageEvent):
    button1 = Button("Click me", "ping", enter=True, visited_text="Clicked")
    button2 = Button("问什么", "问什么", enter=False)
    button3 = Button("Tencent",
                     "https://www.tencent.com",
                     enter=True,
                     action=ButtonAction.JUMP,
                     style=ButtonStyle.GRAY_LINE)
    keyboard = button3 + (button1 | button2)
    message = await MessageExtension.markdown("# Test for keyboard\n\n",
                                              int(bot.self_id),
                                              "鸮鸮",
                                              keyboard=keyboard,
                                              bot=bot)
    await bot.send_group_forward_msg(messages=message, group_id=event.group_id)
    await send_keyboard.finish()


@send_reply.handle()
async def _(event: GroupMessageEvent):
    await send_reply.finish(
        MessageSegment.reply(event.message_id) + MessageSegment.text("reply"))


@follow_reaction.handle()
async def _(bot: Bot, event: GroupReactionAddEvent = GroupReactionAdd()):
    if event.count == 3:
        await bot.set_group_reaction(group_id=event.group_id,
                                     message_id=event.message_id,
                                     code=event.code,
                                     is_add=True)
