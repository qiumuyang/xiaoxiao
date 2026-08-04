import itertools
import random
import re
from collections.abc import AsyncIterable
from dataclasses import dataclass
from functools import partial

import jieba
import jieba.posseg as pseg
from nonebot.adapters.onebot.v11 import Bot, Message

from src.ext import (
    MessageExtension,
    MessageSegment,
    get_group_member_name,
    list_group_member_names,
)
from src.utils.log import logger_wrapper

from .capture_group import expand_capture_group_references
from .corpus import Corpus, Entry
from .corpus_pool import CorpusPool

logger = logger_wrapper(__name__)

jieba.add_word("问一下", tag="v")
jieba.add_word("号号", tag="n")
jieba.add_word("几块钱", tag="m")

punctuation_en = r"""!"#$%&'()*+,-./:;<=>?@[\]^_`{|}~"""
punctuation_cn = r"""！“”‘’（），。：；《》？【】……"""
punctuation = punctuation_en + punctuation_cn
punctuation_choice_stop = r"""，。：；？！,:;?!/()"""


def cut_before_first_punctuation(s: str) -> str:
    for i, c in enumerate(s):
        if c in punctuation:
            return s[:i]
    return s


def number_to_chinese(n: int) -> str:
    assert 0 <= n <= 10
    return "零一二三四五六七八九十"[n]


def endswith_num_and_char(s: str, chars: str, range_: tuple[int, int]):
    if not any(s.endswith(c) for c in chars):
        return False
    i = 2
    while i <= len(s) and s[-i].isdecimal():
        i += 1
    num = s[-i + 1 : -1]
    return num and range_[0] <= int(num) <= range_[1]


@dataclass
class ReplacementPoint:
    """一个 LLM 类替换点（什么/为什么/干什么）。"""

    kw: str  # 什么 / 为什么 / 干什么
    start: int  # 在原字符串中的起始偏移
    length: int | None  # 跟随数字的长度约束，如 什么3 → 3
    prev_out: str = ""  # 替换点前的已输出文本（供 prompt 上下文）


def _scan_template(s: str) -> list[ReplacementPoint]:
    """识别 LLM 类替换点（什么/为什么/干什么）及跟随数字长度约束。

    \\ 转义语义保留：\\什么 不触发（与 process() 一致）。
    """

    points: list[ReplacementPoint] = []
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c == "\\":
            i += 2
            continue
        if c == "/":
            i += 1
            continue
        for kw in ("为什么", "干什么", "什么"):
            if s.startswith(kw, i):
                j = i + len(kw)
                length = None
                if j < n and s[j].isdecimal() and int(s[j]) > 0:
                    length = int(s[j])
                    j += 1
                points.append(ReplacementPoint(kw=kw, start=i, length=length))
                i = j
                break
        else:
            i += 1
    return points


def _encode_template(s: str, points: list[ReplacementPoint]) -> str:
    """把 LLM 点替换为定长 slot 标记，为什么 点加「因为…，所以」句式。"""

    result = s
    for p, i in sorted(
        ((p, i) for i, p in enumerate(points)),
        key=lambda x: x[0].start,
        reverse=True,
    ):
        end = p.start + len(p.kw)
        if p.length is not None:
            end += 1
        slot = f"\x00{i}\x00"
        # 为什么 加「因为」前缀（前置已是「因为」时不重复加，对齐 process prev_out 语义）；
        # 替换点后仍有文本时补「，所以」（对齐 process next_remain 语义，用原始 s 判尾）
        prefix_before = result[max(0, p.start - len("因为")) : p.start]
        if p.kw == "为什么":
            marker = f"因为{slot}" if prefix_before != "因为" else slot
            if end < len(s):
                marker += "，所以"
        else:
            marker = slot
        result = result[: p.start] + marker + result[end:]
    return result


class Ask:
    PERSON = {"你": "我", "我": "你", "你们": "我们", "我们": "你们"}

    PATTERN_YES_NO = re.compile(r"^(.+)([没不])\1")
    PATTERN_ONE_DIGIT = re.compile(r"^\d")

    BAD_DE = "觉舍记认懂晓识值显贪懒博"
    BAD_ASK = [
        "问问",
        "问下",
        "问一下",
        "问题",
        "问询",
        "问候",
        "问鼎",
        "问起",
        "问世",
        "问路",
        "问及",
    ]

    LENGTH_CHECK_ATTEMP = 5
    MIN_WHAT, MAX_WHAT = 2, 10

    ESCAPE_TABLE = {"&": "&amp;", **{str(i): f"&#{i};" for i in range(10)}}

    @classmethod
    def escape(cls, s: str) -> str:
        return "".join(cls.ESCAPE_TABLE.get(c, c) for c in s)

    @classmethod
    def unescape(cls, s: str) -> str:
        for k, v in cls.ESCAPE_TABLE.items():
            s = s.replace(v, k)
        return s

    @classmethod
    def is_question(cls, s: str) -> bool:
        if not s.startswith("问"):
            return False
        for word, _ in pseg.cut(s, use_paddle=True):
            return not any(word.startswith(bad) for bad in cls.BAD_ASK)
        return False

    def preprocess_choice(self, text: str) -> str:
        # split the text by "还是"
        parts = re.split(
            # if punctuation is escaped, it is not a split point
            f"(?<!\\\\)([{re.escape(punctuation_choice_stop)}\n])",
            text,
            flags=re.M,
        )
        sentences, punctuation = parts[::2], parts[1::2]
        for i, sentence in enumerate(sentences):
            choices = list(filter(None, sentence.split("还是")))
            if choices:
                sentences[i] = random.choice(choices)
                self.replacement = self.replacement or len(choices) > 1
            # else as is
        text = "".join(
            s + p
            for s, p in itertools.zip_longest(sentences, punctuation, fillvalue="")
        )
        return text

    def __init__(self, bot: Bot, group_id: int, question: Message) -> None:
        self.bot = bot
        self.group_id = group_id
        self.question = question
        self.replacement = False

    async def _finalize(
        self, result: str, symtab: dict, group_id: int
    ) -> Message | None:
        """expand_capture_groups / unescape / decode 公共收尾，LLM 与普通路径共用。"""
        try:
            expanded = expand_capture_group_references(result)
            result = self.unescape(expanded)
        except ValueError:
            return Message("[由于循环引用，展开终止]")
        processed_message = Message()
        for seg in MessageExtension.decode(result, symtab):
            seg = MessageSegment.from_onebot(seg)
            if seg.is_at():
                # convert to plain text
                member_name = await get_group_member_name(
                    group_id=group_id, user_id=seg.extract_at()
                )
                processed_message.append(MessageSegment.at(member_name))
            else:
                processed_message.append(seg)
        return processed_message

    async def answer(self) -> Message | None:
        group_id = self.group_id
        question, symtab = MessageExtension.encode(self.question)
        if not question:
            return
        if not self.is_question(question):
            return

        member_names = await list_group_member_names(group_id=group_id)
        member_names.extend(["你", "我"])

        question = question.removeprefix("问")
        question = self.preprocess_choice(question)
        if not self.replacement:
            from .ask_llm import AskLlmPreprocessor
            from .config import _ask_llm_enabled

            if await _ask_llm_enabled(self.group_id):
                pre = AskLlmPreprocessor()
                llm_result = await pre.try_preprocess(
                    question, symtab, member_names, group_id=self.group_id
                )
                if llm_result is not None:
                    self.replacement = True
                    processed = await self._finalize(llm_result, symtab, self.group_id)
                    if processed:
                        return processed
        try:
            results = []
            async for token in self.process(question, member_names):
                results.append(token)
            result = "".join(results)
        except ValueError:
            logger.warning("Empty corpus")
            return
        if not self.replacement:
            return
        return await self._finalize(result, symtab, group_id)

    async def random_corpus_entry(
        self,
        length: int | tuple[int, int] | None = (MIN_WHAT, MAX_WHAT),
        startswith: str = "",
        sample: int = 2,
    ) -> list[Entry]:
        result = await CorpusPool.fetch(
            group_id=self.group_id, length=length, startswith=startswith, count=sample
        )
        if not result:
            raise ValueError("No corpus found")
        return result

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
            entries = await self.random_corpus_entry()
            if kwargs["length"] == 1:
                return random.choice(entries[0].text)
            if kwargs["length"] == 2:
                words = [
                    word
                    for ent in entries
                    for word, _ in ent.posseg
                    if len(word) == kwargs["length"]
                ]
                if not words:
                    raise e
                return random.choice(words)
        raise ValueError

    async def random_what_startswith(
        self,
        startswith: str,
        enable_prob: float = 0.25,
        **kwargs,
    ) -> str:
        length = kwargs.pop("length", None)
        if random.random() < enable_prob:
            try:
                if length is not None:
                    # fix by adding length of startswith
                    # which will be removed later
                    return await self.random_what(
                        startswith=startswith, length=length + len(startswith), **kwargs
                    )
                return await self.random_what(startswith=startswith, **kwargs)
            except ValueError:
                pass
        return await self.random_what(length=length, **kwargs)

    async def random_what_to_do(self, length: int | None = None):
        entries = await self.random_corpus_entry(
            length=(length or self.MIN_WHAT, 100), sample=32
        )
        candidates: list[tuple[str, Entry]] = []
        for entry in entries:
            for word_pos in entry.cut_pos(start="v", end=["x", "y"]):
                words, _ = zip(*word_pos, strict=False)
                if length is None or len("".join(words)) == length:
                    candidates.append(("".join(words), entry))
        if candidates:
            if length is None:
                length_distribution = list(set(len(t) for t, _ in candidates))
                # the following line prefers frequent length
                # length = random.choice([len(t) for t, _ in candidates])
                # prefer longer text
                length = random.choices(
                    length_distribution, k=1, weights=length_distribution
                )[0]
            text, entry = random.choice([c for c in candidates if len(c[0]) == length])
            await Corpus.use(entry)
            return text
        raise ValueError

    async def random_reason_entry(self, length: int | None = None) -> Entry:
        kwargs = [
            dict(startswith="因为", length=length + 2 if length else None),
            dict(length=length),
        ]
        if random.random() < 0.5:
            kwargs.reverse()
        for kw in kwargs:
            try:
                return await self.random_what_entry(**kw)
            except ValueError:
                pass
        # not expected to reach here
        return await self.random_what_entry()

    async def random_reason(self, **kwargs) -> str:
        entry = await self.random_reason_entry(**kwargs)
        reason = entry.remove_prefix("因为")
        reason = cut_before_first_punctuation(reason)
        await Corpus.use(entry)
        return reason

    @classmethod
    def pseg_cut(cls, s: str) -> list[str]:
        return [word for word, _ in pseg.cut(s, use_paddle=True)]

    async def _collect_or_text(
        self,
        collect_values: dict[str, tuple[str, str]] | None,
        pua_start: int,
        type_: str,
        text: str,
    ) -> str:
        """collect 模式下把真实值编码为 PUA 字符；否则原样返回。"""
        if collect_values is None:
            return text
        ch = chr(0xE000 + pua_start + len(collect_values))
        collect_values[ch] = (type_, text)
        return ch

    async def process(
        self,
        s: str,
        members: list[str],
        collect_values: dict[str, tuple[str, str]] | None = None,
        pua_start: int = 0,
    ) -> AsyncIterable[str]:
        """Process a question and yield answer tokens.

        Special tokens:
        - "\\\\": the next character after this token is yielded as is
        - "/": discarded immediately (for sentence segmentation)
        """

        remain = s
        total_out = ""
        prev_out = ""
        prev_in_pos = ""

        def output(out: str, escape: bool = True):
            nonlocal total_out
            nonlocal prev_out
            total_out += out
            prev_out = out
            return out if not escape else self.escape(out)

        while remain:
            word, pos = next(pseg.cut(remain, use_paddle=True))
            next_remain = remain[len(word) :]
            if word == "\\":
                # special symbol "\" indicates the next char is yielded as is
                # except:
                #   - \d, which is a reference to capture group
                #   - (), which indicates a capture group, capture handles this
                if next_remain[:1].isdecimal() or next_remain[:1] in "()":
                    yield output(word + next_remain[0], escape=False)
                else:
                    yield output(word if not next_remain else next_remain[0])
                remain = next_remain[1:]
                _prev_in, prev_in_pos = word, pos
                continue
            if word == "/":
                remain = next_remain
                _prev_in, prev_in_pos = word, pos
                continue
            if match := self.PATTERN_YES_NO.match(remain):
                self.replacement = True
                next_remain = remain[len(match.group(0)) :]
                action, neg = match.group(1), match.group(2)
                if (
                    neg == "不"
                    and next_remain.startswith("得")
                    and action not in self.BAD_DE
                ):
                    obj = next_remain[1:2]
                    if obj:
                        generated = action + random.choice("得不") + obj
                        remain = generated + next_remain[2:]
                        _prev_in, prev_in_pos = "", ""
                        continue
                generated = random.choice(["", neg]) + action
                next_remain = generated + next_remain
            elif word in self.PERSON:
                yield output(self.PERSON[word])
            elif word in ["什么", "为什么", "干什么"]:
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
                elif not self.replacement and 1 <= len(prev_out) <= 3:
                    fn = partial(self.random_what_startswith, startswith=prev_out)
                else:
                    fn = self.random_what
                is_why = fn == self.random_reason
                attemp = self.LENGTH_CHECK_ATTEMP
                while attemp := attemp - 1:
                    generated = await fn(length=length_limit)
                    # check if previous token is nr or r (somebody)
                    # if so, remove the nr/r prefix of the generated text
                    if prev_in_pos in ["nr", "r"]:
                        start, start_pos = next(pseg.cut(generated, use_paddle=True))
                        if start_pos in ["nr", "r"] and start != generated:
                            generated = generated[len(start) :]
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
                generated = generated.removeprefix(prev_out)
                yield output(generated)
                self.replacement = True
            elif word == "谁":
                picked = random.choice(members)
                yield await self._collect_or_text(
                    collect_values, pua_start, "nickname", picked
                )
                self.replacement = True
            elif word.startswith("多少"):
                num = str(random.randint(0, 100))
                generated = word.replace("多少", num)
                yield await self._collect_or_text(
                    collect_values, pua_start, "number", generated
                )
                self.replacement = True
            elif "几" in word and pos == "m":
                if word == "几点钟":
                    num = str(random.randint(1, 12))
                elif word in ["几点", "几时"] and next_remain.startswith(
                    ("几分", "几刻", "几秒")
                ):
                    num = str(random.randint(1, 12))
                elif word == "几分" and endswith_num_and_char(
                    total_out, "点时", (0, 24)
                ):
                    num = str(random.randint(1, 59))
                # yapf: disable
                elif word == "几秒" and (
                    endswith_num_and_char(total_out, "点时", (0, 24))
                    or endswith_num_and_char(total_out, "分", (0, 60))
                ):
                    num = str(random.randint(1, 59))
                # yapf: enable
                elif word == "几刻":
                    num = str(random.randint(1, 3))
                elif word == "几月":
                    num = str(random.randint(1, 12))
                elif word in {"几号", "几日"} and endswith_num_and_char(
                    total_out, "月", (1, 12)
                ):
                    m = re.search(r"(\d+)月$", total_out)
                    assert m is not None
                    month = int(m.group(1))
                    days = {2: 29, 4: 30, 6: 30, 9: 30, 11: 30}.get(month, 31)
                    num = str(random.randint(1, days))
                elif match := re.search(r"几[十百千万]|[十第]几", word):
                    num = number_to_chinese(random.randint(1, 9))
                elif word == "几" and prev_out == "星期":
                    num = number_to_chinese(random.randint(1, 7))
                    num = "天" if num == "七" else num
                else:
                    num = str(random.randint(0, 10))
                first, rest = word.split("几", 1)
                yield output(
                    await self._collect_or_text(
                        collect_values, pua_start, "number", first + num
                    )
                )
                self.replacement = True
                next_remain = rest + next_remain
            else:
                yield output(word, escape=False)
            remain = next_remain
            _prev_in, prev_in_pos = word, pos
