import random
import re
from typing import AsyncIterable

import jieba
import jieba.posseg as pseg
from nonebot.adapters.onebot.v11 import Bot, Message

from src.ext import MessageSegment, logger_wrapper

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
    BAD_ASK = [
        "问问", "问下", "问一下", "问题", "问询", "问候", "问鼎", "问起", "问世", "问路", "问及"
    ]

    LENGTH_CHECK_ATTEMP = 5
    MIN_WHAT, MAX_WHAT = 2, 10

    @classmethod
    def is_question(cls, s: str) -> bool:
        if not s.startswith("问"):
            return False
        for word, _ in pseg.cut(s, use_paddle=True):
            return not any(word.startswith(bad) for bad in cls.BAD_ASK)
        return False

    def __init__(self, bot: Bot, group_id: int, question: Message) -> None:
        self.bot = bot
        self.group_id = group_id
        self.question = question

    async def answer(self) -> Message | None:
        bot = self.bot
        group_id = self.group_id
        question = self.question
        if not question:
            return
        if not question[0].is_text() or not self.is_question(
                question[0].data["text"]):
            return

        members = await bot.get_group_member_list(group_id=group_id)
        member_names = [
            member["card"] or member["nickname"] for member in members
        ] + ["你", "我"]

        self.replacement = False
        processed_message = Message()
        for i, ob_seg in enumerate(question):
            seg = MessageSegment.from_onebot(ob_seg)
            if seg.is_at():
                # convert to plain text
                member = await bot.get_group_member_info(
                    group_id=group_id, user_id=seg.extract_at())
                member_name = (member["card"] or member["nickname"]
                               or str(seg.extract_at()))
                append_seg = MessageSegment.text(member_name)
            elif not seg.is_text():
                # as is
                append_seg = seg
            else:
                text = seg.extract_text()
                if i == 0:
                    text = text.removeprefix("问")
                try:
                    results = []
                    async for token in self.process(text, member_names):
                        results.append(token)
                    result = "".join(results)
                except ValueError:
                    logger.warning("Empty corpus")
                    return
                append_seg = MessageSegment.text(result)
            processed_message.append(append_seg)
        if self.replacement:
            return processed_message

    async def random_corpus_entry(
        self,
        length: int | tuple[int, int] | None = (MIN_WHAT, MAX_WHAT),
        startswith: str = "",
        sample: int = 10,
    ) -> list[Entry]:
        cursor = Corpus.find(group_id=self.group_id,
                             length=length,
                             sample=sample,
                             filter={"text": {
                                 "$regex": f"^{startswith}"
                             }} if startswith else None)
        result = await cursor.to_list(length=sample)
        entries = [deserialize(doc) for doc in result]
        if length is not None:
            # post length check
            # I don't know why filter sometimes doesn't work
            min_l, max_l = length if isinstance(length, tuple) else (length,
                                                                     length)
            entries = [e for e in entries if min_l <= len(e.text) <= max_l]
        if entries:
            return entries
        raise ValueError

    async def random_what_entry(self, **kwargs) -> Entry:
        return random.choice(await self.random_corpus_entry(**kwargs))

    async def random_what(self, **kwargs) -> str:
        try:
            entry = await self.random_what_entry(**kwargs)
            await Corpus.use(entry)
            return entry.text
        except ValueError as e:
            if kwargs.get("length") is None or kwargs["length"] > 2:
                raise e
            entries = await self.random_corpus_entry(sample=10)
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

    async def random_what_to_do(self, length: int | None = None):
        entries = await self.random_corpus_entry(length=(length
                                                         or self.MIN_WHAT,
                                                         100),
                                                 sample=64)
        candidates: list[tuple[str, Entry]] = []
        for entry in entries:
            for word_pos in entry.cut_pos(start="v", end=["x", "y"]):
                words, _ = zip(*word_pos)
                if length is None or len("".join(words)) == length:
                    candidates.append(("".join(words), entry))
        if candidates:
            if length is None:
                length_distribution = list(set(len(t) for t, _ in candidates))
                # the following line prefers frequent length
                # length = random.choice([len(t) for t, _ in candidates])
                # prefer longer text
                length = random.choices(length_distribution,
                                        k=1,
                                        weights=length_distribution)[0]
            text, entry = random.choice(
                [c for c in candidates if len(c[0]) == length])
            await Corpus.use(entry)
            return text
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
        """Process a question and yield answer tokens.

        Special tokens:
        - "\\\\": the next character after this token is yielded as is
        - "/": discarded immediately (for sentence segmentation)
        """

        remain = s
        prev_out = ""
        prev_in = ""
        prev_in_pos = ""

        def output(out: str):
            nonlocal prev_out
            prev_out = out
            return out

        while remain:
            word, pos = next(pseg.cut(remain, use_paddle=True))
            next_remain = remain[len(word):]
            if word == "\\":
                # special symbol "\" indicates the next character should be responded
                yield output(word if not next_remain else next_remain[0])
                remain = next_remain[1:]
                prev_in, prev_in_pos = word, pos
                continue
            if word == "/":
                remain = next_remain
                prev_in, prev_in_pos = word, pos
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
                        prev_in, prev_in_pos = "", ""
                        continue
                generated = random.choice(["", neg]) + action
                next_remain = generated + next_remain
            elif word in self.PERSON:
                yield output(self.PERSON[word])
            elif word in ["什么", "为什么", "干什么"]:
                self.replacement = True
                # check followed by one digit
                length_limit = None
                if self.PATTERN_ONE_DIGIT.match(next_remain):
                    if (length_limit := int(next_remain[0])) > 0:
                        next_remain = next_remain[1:]
                    else:
                        length_limit = None
                # check is reason
                if prev_out == "因为" and word == "什么":
                    fn = self.random_reason
                elif word == "为什么":
                    fn = self.random_reason
                elif word == "干什么":
                    fn = self.random_what_to_do
                else:
                    fn = self.random_what
                is_why = fn == self.random_reason
                attemp = self.LENGTH_CHECK_ATTEMP
                while attemp := attemp - 1:
                    generated = await fn(length=length_limit)
                    # check if previous token is nr or r (somebody)
                    # if so, remove the nr/r prefix of the generated text
                    if prev_in_pos in ["nr", "r"]:
                        start, start_pos = next(
                            pseg.cut(generated, use_paddle=True))
                        if start_pos in ["nr", "r"] and start != generated:
                            generated = generated[len(start):]
                    if not length_limit or len(generated) == length_limit:
                        break
                else:
                    raise ValueError(f"Failed: length={length_limit}")
                if is_why:
                    # decoration
                    reason = generated
                    tokens = [
                        "因为" if prev_out != "因为" else "",
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
                elif word == "几分" and re.fullmatch(r"\d+[点时]", prev_out):
                    num = str(random.randint(1, 59))
                elif word == "几秒" and re.fullmatch(r"\d+[点时分]", prev_out):
                    num = str(random.randint(1, 59))
                elif word == "几刻":
                    num = str(random.randint(1, 3))
                elif word == "几月":
                    num = str(random.randint(1, 12))
                elif word == "几号" and re.fullmatch(r"\d+月", prev_out):
                    month = int(prev_out[:-1])
                    days = {2: 29, 4: 30, 6: 30, 9: 30, 11: 30}.get(month, 31)
                    num = str(random.randint(1, days))
                else:
                    num = str(random.randint(0, 10))
                if word[1:].startswith("几"):
                    # only consume one character
                    # leave the rest to next iteration
                    yield output(num)
                    next_remain = word[1:] + next_remain
                else:
                    yield output(num + word[1:])
            else:
                yield output(word)
            remain = next_remain
            prev_in, prev_in_pos = word, pos
