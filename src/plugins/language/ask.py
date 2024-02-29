import random
import re
from typing import AsyncIterable

import jieba
import jieba.posseg as pseg
from nonebot.adapters.onebot.v11 import Bot

from src.ext import logger_wrapper

from .corpus import Corpus, Entry, deserialize

logger = logger_wrapper(__name__)

jieba.add_word("问一下", tag="v")
jieba.add_word("号号", tag="n")

punctuation_en = r"""!"#$%&'()*+,-./:;<=>?@[\]^_`{|}~"""
punctuation_cn = r"""！“”‘’（），。：；《》？【】……"""
punctuation = punctuation_en + punctuation_cn


def cut_before_first_punctuation(s: str) -> str:
    for i, c in enumerate(s):
        if c in punctuation:
            return s[:i]
    return s


class Ask:

    PERSON = {"你": "我", "我": "你", "你们": "我们", "我们": "你们"}

    PATTERN_YES_NO = re.compile(r"^(.+)([没不])\1")
    PATTERN_ONE_DIGIT = re.compile(r"^\d")

    BAD_DE = "觉舍记认懂晓识值显贪懒博"

    MIN_WHAT, MAX_WHAT = 2, 10

    @classmethod
    def is_question(cls, s: str) -> bool:
        if not s.startswith("问"):
            return False
        for word, _ in pseg.cut(s, use_paddle=True):
            return word == "问"
        return False

    def __init__(self, bot: Bot, group_id: int, question: str) -> None:
        self.bot = bot
        self.group_id = group_id
        self.question = question

    async def answer(self) -> str | None:
        bot = self.bot
        group_id = self.group_id
        question = self.question
        if not self.is_question(question):
            return

        members = await bot.get_group_member_list(group_id=group_id)
        member_names = [
            member["card"] or member["nickname"] for member in members
        ] + ["你", "我"]

        self.replacement = False
        try:
            results = []
            async for token in self.process(question[1:], member_names):
                results.append(token)
            result = "".join(results)
        except ValueError:
            logger.warning("Empty corpus")
            return
        if self.replacement:
            return result

    async def random_what_entry(
        self,
        length: int | None = None,
        startswith: str = "",
        all: bool = False,
        sample: int = 5,
    ) -> Entry | list[Entry]:
        cursor = Corpus.find(group_id=self.group_id,
                             length=length or (self.MIN_WHAT, self.MAX_WHAT),
                             sample=sample,
                             filter={"text": {
                                 "$regex": f"^{startswith}"
                             }} if startswith else None)
        result = await cursor.to_list(length=sample)
        entries = [deserialize(doc) for doc in result]
        if entries:
            return random.choice(entries) if not all else entries
        raise ValueError

    async def random_what(self, **kwargs) -> str:
        try:
            entry = await self.random_what_entry(**kwargs)
            assert isinstance(entry, Entry)
            await Corpus.use(entry)
            return entry.text
        except ValueError as e:
            if kwargs.get("length") is None or kwargs["length"] > 2:
                raise e
            entries = await self.random_what_entry(all=True)
            assert isinstance(entries, list)
            if kwargs["length"] == 1:
                return random.choice(entries[0].text)
            if kwargs["length"] == 2:
                words = [
                    word for ent in entries for word, _ in ent.posseg
                    if len(word) == kwargs["length"]
                ]
                if not words:
                    raise e
                return random.choice(words)
        raise ValueError

    async def random_reason_entry(self, length: int | None = None) -> Entry:
        coroutines = [
            self.random_what_entry(startswith="因为",
                                   length=length + 2 if length else None),
            self.random_what_entry(length=length),
        ]
        if random.random() < 0.5:
            coroutines.reverse()
        try:
            return await coroutines[0]  # type: ignore
        except ValueError:
            return await coroutines[1]  # type: ignore

    async def random_reason(self, **kwargs) -> str:
        entry = await self.random_reason_entry(**kwargs)
        reason = entry.remove_prefix("因为")
        reason = cut_before_first_punctuation(reason)
        await Corpus.use(entry)
        return reason

    async def process(
        self,
        s: str,
        members: list[str],
    ) -> AsyncIterable[str]:
        remain = s
        recent = ""

        def output(word: str):
            nonlocal recent
            recent = word
            return word

        while remain:
            word, pos = next(pseg.cut(remain, use_paddle=True))
            next_remain = remain[len(word):]
            if word == "\\":
                # escape character
                yield output(word if not next_remain else next_remain[0])
                remain = next_remain[1:]
                continue
            if match := self.PATTERN_YES_NO.match(remain):
                self.replacement = True
                next_remain = remain[len(match.group(0)):]
                action, neg = match.group(1), match.group(2)
                if (neg == "不" and next_remain.startswith("得")
                        and action not in self.BAD_DE):
                    obj = next_remain[1:2]
                    if obj:
                        generated = action + random.choice("得不") + obj
                        remain = generated + next_remain[2:]
                        continue
                generated = random.choice(["", neg]) + action
                next_remain = generated + next_remain
            elif word in self.PERSON:
                yield output(self.PERSON[word])
            elif word in ["什么", "为什么"]:
                self.replacement = True
                # check followed by one digit
                length_limit = None
                if self.PATTERN_ONE_DIGIT.match(next_remain):
                    if length_limit := int(next_remain[0]):
                        next_remain = next_remain[1:]
                # check is reason
                if recent == "因为" and word == "什么":
                    fn = self.random_reason
                elif word == "为什么":
                    fn = self.random_reason
                else:
                    fn = self.random_what
                is_why = fn == self.random_reason
                generated = await fn(length=length_limit)
                if is_why:
                    # decoration
                    reason = generated
                    tokens = [
                        "因为" if recent != "因为" else "",
                        reason,
                        "，所以" if next_remain else "",
                    ]
                    generated = "".join(tokens)
                yield generated
            elif word == "谁":
                self.replacement = True
                yield random.choice(members)
            elif word.startswith("多少"):
                self.replacement = True
                num = str(random.randint(0, 100))
                yield word.replace("多少", num)
            elif word.startswith("几") and pos == "m":
                self.replacement = True
                if word == "几点钟":
                    num = str(random.randint(1, 12))
                elif word in ["几点", "几时"] and next_remain.startswith(
                    ("几分", "几刻", "几秒")):
                    num = str(random.randint(1, 12))
                elif word == "几分" and re.fullmatch(r"\d+[点时]", recent):
                    num = str(random.randint(1, 59))
                elif word == "几秒" and re.fullmatch(r"\d+[点时分]", recent):
                    num = str(random.randint(1, 59))
                elif word == "几刻":
                    num = str(random.randint(1, 3))
                elif word == "几月":
                    num = str(random.randint(1, 12))
                elif word == "几号" and re.fullmatch(r"\d+月", recent):
                    month = int(recent[:-1])
                    days = {2: 29, 4: 30, 6: 30, 9: 30, 11: 30}.get(month, 31)
                    num = str(random.randint(1, days))
                else:
                    num = str(random.randint(0, 10))
                yield output(num + word[1:])
            else:
                yield output(word)
            remain = next_remain
