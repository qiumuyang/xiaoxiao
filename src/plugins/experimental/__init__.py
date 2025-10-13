import emoji
from nonebot import on_command, on_notice
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent
from nonebot.adapters.onebot.v11.event import Reply
from nonebot.permission import SUPERUSER
from nonebot.typing import T_State

from src.ext import api
from src.ext.event import GroupReactionAdd, GroupReactionAddEvent
from src.ext.message import (Button, ButtonAction, ButtonStyle,
                             MessageExtension, MessageSegment)
from src.ext.on import on_reply

reaction_reply = on_reply("贴", block=True)
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
        await api.set_emoji_reaction(group_id=event.group_id,
                                     message_id=event.message_id,
                                     emoji=event.code)


EXCLUDE_CODEPOINTS = {
    # zero-width joiner
    "\u200d",
    # variation selectors
    "\ufe0e",
    "\ufe0f",
    # male and female symbols
    "\u2640",
    "\u2642",
    # skin tones
    *(chr(c) for c in range(0x1F3FB, 0x1F400)),
    # regional indicators
    *(chr(c) for c in range(0x1F1E6, 0x1F200)),
}


@reaction_reply.handle()
async def _(bot: Bot, event: GroupMessageEvent, state: T_State):
    reply: Reply = state["reply"]
    content = reply.message
    max_count = 5
    for seg in content:
        seg = MessageSegment.from_onebot(seg)
        if seg.is_face():
            id = seg.extract_face()
            await api.set_emoji_reaction(group_id=event.group_id,
                                         message_id=event.message_id,
                                         emoji=str(id))
            max_count -= 1
            if max_count == 0:
                break
        elif seg.is_text():
            text = seg.extract_text().strip()
            for e in emoji.emoji_list(text):
                emj = e["emoji"]
                if emj in EXCLUDE_CODEPOINTS or len(emj) != 1:
                    continue
                await api.set_emoji_reaction(group_id=event.group_id,
                                             message_id=event.message_id,
                                             emoji=str(ord(emj)))
                max_count -= 1
                if max_count == 0:
                    break
    await reaction_reply.finish()
