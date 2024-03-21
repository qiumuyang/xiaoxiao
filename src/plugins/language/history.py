import asyncio
import re
from datetime import datetime, timedelta

from nonebot.adapters.onebot.v11 import Bot, Message

from src.ext.message import MessageSegment
from src.utils.message.receive import MessageData as ReceiveMessageData
from src.utils.message.receive import ReceivedMessageTracker as RMT
from src.utils.message.send import MessageData as SentMessageData
from src.utils.message.send import SentMessageTracker as SMT


class History:

    MAX_HISTORY_COUNT = 200
    MAX_HISTORY_INTERVAL = timedelta(days=1)

    FORWARD_MESSAGE_LIMIT = 30

    @classmethod
    async def find_single_message(
        cls,
        bot: Bot,
        group_id: int,
        *,
        index: int = 1,
    ) -> Message | None:
        since = datetime.now() - cls.MAX_HISTORY_INTERVAL
        recv = await RMT.find(group_id=group_id, since=since)
        sent = await SMT.find(group_id=group_id, since=since)
        messages = sorted(recv + sent, key=lambda x: x.time)
        # -1 for the current message
        messages = messages[-cls.MAX_HISTORY_COUNT - 1:]
        try:
            selected = messages[-index - 1]
        except IndexError:
            return

        user_id = (selected.user_id if isinstance(selected, ReceiveMessageData)
                   else int(bot.self_id))
        member = await bot.get_group_member_info(group_id=group_id,
                                                 user_id=user_id)
        nickname = (member["card"] or member["nickname"] or str(user_id))

        # forward and longmsg
        content = selected.content
        if content and content[0].type in ["forward", "longmsg"]:
            id_ = content[0].data["id"]
            if not id_:
                content = Message("[合并转发消息]")
            else:
                # cannot be wrapped again by node_lagrange
                return content

        forward_id = await bot.call_api("send_forward_msg",
                                        messages=[
                                            MessageSegment.node_lagrange(
                                                user_id=user_id,
                                                nickname=nickname,
                                                content=content)
                                        ])
        return Message(MessageSegment.forward(id_=forward_id))

    @classmethod
    async def find(
        cls,
        bot: Bot,
        group_id: int,
        *,
        senders: list[int] | None = None,
        keywords: list[str] | None = None,
    ) -> Message | None:
        """Find messages by senders and keywords.

        Bot messages are not included by default.

        Args:
            senders: match message if user_id in senders
            keywords: match message if all keywords in content
                use `:image:` to match image message
                use `:regex:<pattern>` to match content by regex pattern
                use `:bot:` to include bot messages

        Returns:
            A group forward message if found, otherwise None
        """
        # parse keywords
        accept_types = ["text"]
        accept_keywords: list[str | re.Pattern] = []

        for keyword in keywords or []:
            if keyword == ":image:":
                accept_types.append("image")
            elif keyword == ":bot:":
                accept_types.append("bot")
            elif keyword.startswith(":regex:"):
                regex = keyword.removeprefix(":regex:")
                try:
                    pattern = re.compile(regex)
                except re.error:
                    pattern = regex
                accept_keywords.append(pattern)
            else:
                accept_keywords.append(keyword)

        since = datetime.now() - cls.MAX_HISTORY_INTERVAL
        recv = await RMT.find(group_id=group_id, since=since)
        sent = await SMT.find(group_id=group_id, since=since)
        messages = sorted(recv + sent, key=lambda x: x.time)
        # -1 for the current message
        messages = messages[:-1]

        # filter messages
        filtered: list[SentMessageData | ReceiveMessageData] = []
        for message in messages:
            if isinstance(message, SentMessageData):
                if "bot" not in accept_types:
                    continue
            if isinstance(message, ReceiveMessageData):
                if senders and message.user_id not in senders:
                    continue
            content = message.content
            for seg in content:
                if seg.type == "image" and "image" in accept_types:
                    filtered.append(message)
                    break
                if seg.type == "text":
                    if "image" in accept_types and not accept_keywords:
                        # only display image messages
                        continue
                    text = seg.data.get("text", "")
                    if all(keyword in text if isinstance(keyword, str) else
                           keyword.search(text)
                           for keyword in accept_keywords):
                        filtered.append(message)
                        break

        filtered = filtered[-cls.FORWARD_MESSAGE_LIMIT:]
        if not filtered:
            return

        user_ids = set(m.user_id for m in filtered
                       if isinstance(m, ReceiveMessageData))
        if "bot" in accept_types:
            user_ids.add(int(bot.self_id))

        members = await asyncio.gather(
            *(bot.get_group_member_info(group_id=group_id, user_id=user_id)
              for user_id in user_ids))
        uin_to_nicknames = {
            int(member["user_id"]): member["card"] or member["nickname"]
            for member in members
        }

        # Reference:
        # https://lagrangedev.github.io/Lagrange.Doc/Lagrange.OneBot/API/Extend/#发送合并转发-群聊
        nodes = [
            MessageSegment.node_lagrange(
                user_id=user_id,
                nickname=uin_to_nicknames.get(user_id, str(user_id)),
                content=message.content,
            ) for message in filtered
            if (user_id := message.user_id if isinstance(
                message, ReceiveMessageData) else int(bot.self_id))
        ]
        forward_id = await bot.call_api("send_forward_msg", messages=nodes)
        return Message(MessageSegment.forward(id_=forward_id))
