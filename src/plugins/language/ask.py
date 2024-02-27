import random
import re
from datetime import datetime, timedelta
from typing import Callable, Iterable

import jieba
import jieba.posseg as pseg
from nonebot.adapters.onebot.v11 import Bot

from src.utils.message import ReceivedMessageTracker as RMT
from src.utils.message import ReceiveMessage
from src.utils.message import SentMessageTracker as SMT

jieba.add_word("问一下", tag="v")

punctuation_en = r"""!"#$%&'()*+,-./:;<=>?@[\]^_`{|}~"""
punctuation_cn = r"""！“”‘’（），。：；《》？【】……"""
punctuation = punctuation_en + punctuation_cn


class CorpusFilter:

    DEFAULT_MAX_LENGTH = 10
    DEFAULT_MIN_LENGTH = 2
    MIN_INTERVAL = timedelta(minutes=10)
    # FIXME: do not use a duplicated constant
    # defined in __init__.py
    SESSION_GROUP_PREFIX = "group_{group_id}_"

    def __init__(
        self,
        group_id: int,
        limit: int = 0,
        length: tuple[int, int] = (DEFAULT_MIN_LENGTH, DEFAULT_MAX_LENGTH),
        message_filter: Callable[[str], bool] = lambda x: True,
    ) -> None:
        self.now = datetime.now()
        self.group_id = group_id
        self.limit = limit
        self.length = length
        self.filtered = set()
        self.message_filter = message_filter

    def __call__(self, message: ReceiveMessage) -> bool:
        # do not use command related messages
        if message["handled"]:
            return False
        # do not use latest messages
        if self.now - message["time"] < self.MIN_INTERVAL:
            return False
        # do not use non-text messages
        text = message["content"].extract_plain_text()
        if not text.strip():
            return False
        # length
        min_l, max_l = self.length
        if not min_l <= len(text) <= max_l:
            return False
        # custom message filter
        if not self.message_filter(text):
            return False
        # do not use recently sent messages
        if SMT.contains(text,
                        prefix=self.SESSION_GROUP_PREFIX.format(
                            group_id=self.group_id),
                        recent=self.MIN_INTERVAL):
            return False
        self.filtered.add(text)
        # early stop
        if self.limit > 0 and len(self.filtered) > self.limit:
            raise StopIteration
        return True


class Ask:

    PERSON = {"你": "我", "我": "你", "你们": "我们", "我们": "你们"}
    PATTERN_YES_NO = re.compile(r"^(.+)([没不])\1")
    BAD_DE = "觉舍记认懂晓识值显贪懒博"

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
            result = "".join(self.process(question[1:], member_names))
        except ValueError:
            return
        if self.replacement:
            return result

    def random_reason(self) -> str:

        def startswith_because(s: str) -> bool:
            for word, _ in pseg.cut(s, use_paddle=True):
                return word == "因为"
            return False

        def yield_until_punctuation(s: str) -> Iterable[str]:
            for word, _ in pseg.cut(s, use_paddle=True):
                if word in punctuation:
                    return
                yield word

        because_filter = CorpusFilter(self.group_id,
                                      limit=1,
                                      length=(2, 20),
                                      message_filter=startswith_because)
        any_filter = CorpusFilter(self.group_id, limit=1)
        filters = [because_filter, any_filter]
        if random.random() < 0.5:
            filters.reverse()
        for f in filters:
            if list(RMT.filter(self.group_id, f)):
                result = f.filtered.pop().removeprefix("因为")
                return "".join(yield_until_punctuation(result))
        raise ValueError("Possible empty corpus")

    def random_what(self) -> str:
        filter = CorpusFilter(self.group_id, 1, length=(2, 10))
        result = list(RMT.filter(self.group_id, filter))
        if result:
            return filter.filtered.pop()
        raise ValueError("Possible empty corpus")

    def process(
        self,
        s: str,
        members: list[str],
    ) -> Iterable[str]:
        remain = s
        recent = ""

        def output(word: str):
            nonlocal recent
            recent = word
            return word

        def non_empty(fn) -> str:
            while True:
                result = fn()
                if result:
                    return result

        while remain:
            word, _ = next(pseg.cut(remain, use_paddle=True))
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
                        yield action + random.choice("得不") + obj
                        remain = next_remain[2:]
                        continue
                yield random.choice(["", neg]) + action
            elif word in self.PERSON:
                yield output(self.PERSON[word])
            elif word == "什么":
                self.replacement = True
                if recent == "因为":
                    yield non_empty(self.random_reason)
                    if next_remain:
                        yield "，所以"
                else:
                    yield non_empty(self.random_what)
            elif word == "为什么":
                self.replacement = True
                yield "因为" + non_empty(self.random_reason)
                if next_remain:
                    yield "，所以"
            elif word == "谁":
                self.replacement = True
                yield random.choice(members)
            elif word == "多少":
                self.replacement = True
                yield str(random.randint(0, 100))
            else:
                yield output(word)
            remain = next_remain
