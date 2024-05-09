import asyncio
import random

from nonebot import get_bot

from src.ext import MessageSegment

from ..data import Poetry
from .data import KEYWORDS, FeiHuaData


class FeiHua:

    GAME_IN_PROGRESS = "当前进行的飞花令题目是：【{keywords}】"
    GAME_RAND_START = "飞花令开始！鸮鸮帮你出题：【{keywords}】"
    GAME_NORM_START = "飞花令开始！题目是：【{keywords}】"
    GAME_STOP = "飞花令结束啦~来看看得分吧\n{ranking}"

    E_NO_GAME = "没有正在进行的飞花令游戏"
    E_NO_KW = "这句诗词根本就没提到【{keywords}】吧"
    E_LENGTH = "太短啦再多说几个字吧"
    E_EXIST = "之前有人说过这句啦"
    E_NOT_POETRY = "鸮鸮不认识这句诗词"
    ACCEPT = "答对啦！当前得分：{score}\n这句诗词来自【{dynasty}·{author} 《{title}》】"

    MIN_LENGTH = 5

    def __init__(self, group_id: int):
        self.group_id = group_id

    async def start(self, keywords: list[str]) -> MessageSegment | None:
        group = await FeiHuaData.get(self.group_id)
        if group.in_progress:
            return MessageSegment.text(
                self.GAME_IN_PROGRESS.format(keywords=group.display_keywords))

        if not keywords:
            group.keywords = [random.choice(KEYWORDS)]
            template = self.GAME_RAND_START
        else:
            group.keywords = keywords
            template = self.GAME_NORM_START

        await FeiHuaData.set(self.group_id, group)
        return MessageSegment.text(
            template.format(keywords=group.display_keywords))

    async def stop(self) -> MessageSegment | None:
        group = await FeiHuaData.get(self.group_id)
        if not group.in_progress or not group.score:
            return
        bot = get_bot()
        score = dict(
            sorted(group.score.items(), key=lambda x: x[1], reverse=True))
        members = await asyncio.gather(*[
            bot.get_group_member_info(group_id=self.group_id, user_id=user_id)
            for user_id in score
        ])
        # temporary fix for the member name problem
        prefix = "\x08%ĀĀ\x07Ñ\n\x08\x12\x06"
        suffix = "\x10\x00"

        def make_name(member: dict):
            name = member["card"] or member["nickname"]
            return name.strip().removeprefix(prefix).removesuffix(suffix)

        ranking = "\n".join(
            f"第{i}名 {make_name(member)} {sc}分"
            for i, (member, sc) in enumerate(zip(members, score.values()), 1))

        group.stop()
        await FeiHuaData.set(self.group_id, group)
        return MessageSegment.text(self.GAME_STOP.format(ranking=ranking))

    async def answer(
        self,
        user_id: int,
        input_: str,
        *,
        explicit: bool,
    ) -> MessageSegment | None:
        """Answer the FeiHua game.

        The answer is accepted if:
        - contains the expected keywords
        - comes from a poetry
        - not mentioned by others yet

        If explicit is True, the bot will always reply with a message.
        If not, only reply when the answer comes from a poetry.
        """
        group = await FeiHuaData.get(self.group_id)
        if not group.in_progress:
            return None if not explicit else MessageSegment.text(
                "没有正在进行的飞花令游戏")
        parts = Poetry.separate(input_)
        if sum(len(_) for _ in parts) < self.MIN_LENGTH:
            return None if not explicit else MessageSegment.text(self.E_LENGTH)
        if all(kw not in input_ for kw in group.keywords):
            return None if not explicit else MessageSegment.text(
                self.E_NO_KW.format(keywords=group.display_keywords))
        match_poetry = Poetry.search_origin(input_)
        if not match_poetry:
            return None if not explicit else MessageSegment.text(
                self.E_NOT_POETRY)
        hit_part = [p for p in parts if any(kw in p for kw in group.keywords)]
        if all(p in group.parts for p in hit_part):
            return MessageSegment.text(self.E_EXIST)
        # accept the answer
        # choose the origin by title length (shorter is better)
        origin = min(match_poetry, key=lambda x: len(x["title"]))
        group.score.setdefault(user_id, 0)
        group.score[user_id] += 1
        group.history.append((user_id, input_))
        group.parts.extend(hit_part)
        await FeiHuaData.set(self.group_id, group)
        return MessageSegment.text(
            self.ACCEPT.format(score=group.score[user_id], **origin))
