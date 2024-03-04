import random
import re
from datetime import datetime, timedelta

from nonebot.adapters.onebot.v11 import Message

from src.ext import MessageSegment as MS
from src.utils.message.receive import ReceivedMessageTracker as RMT
from src.utils.message.send import SentMessageTracker as SMT

from .corpus import Corpus
from .keywords import Keyword


class Interact:

    IS_RECV = bool

    RECENT_MESSAGE_INTERVAL = timedelta(seconds=90)
    RECENT_MIN_RECV_MESSAGE = 3

    RP_PROB_MIN = 0.1
    RP_PROB_MAX = 0.6
    RP_MIN_CONSECUTIVE = 1
    RP_MAX_CONSECUTIVE = 5
    RP_BREAK_PROB_MIN = 0.1
    RP_BREAK_PROB_MAX = 0.5
    RP_BREAK_MIN_CONSECUTIVE = 6
    RP_BREAK_PROB_INC = 0.1
    RP_BREAK_TEXT = "打断！"
    RP_RE_BREAK_TEXT = "打断打断！"

    KW_PROB = 0.2
    KW_MIN_QUERY_LEN = 10
    KW_MIN_CORPUS_LEN = 6
    KW_MAX_CORPUS_LEN = 40
    KW_CORPUS_SAMPLE = 128
    KW_SIM_THRESHOLD = 0.6

    @classmethod
    async def response(cls, group_id: int, message: Message) -> Message | None:
        since = datetime.now() - cls.RECENT_MESSAGE_INTERVAL
        received_messages = await RMT.find(group_id=group_id,
                                           handled=False,
                                           since=since)
        # check if there are enough received messages
        if len(received_messages) < cls.RECENT_MIN_RECV_MESSAGE:
            return
        sent_messages = await SMT.find(group_id=group_id,
                                       recalled=False,
                                       since=since)
        is_recv = [True] * len(received_messages) + [False
                                                     ] * len(sent_messages)
        messages = sorted(zip(received_messages + sent_messages, is_recv),
                          key=lambda x: x[0].time)
        messages = [(m.content, r) for m, r in messages]
        responser = [
            cls.repeat_response,
            cls.keyword_response,
        ]
        for r in responser:
            if resp := await r(group_id, messages):
                return resp

    @classmethod
    async def repeat_response(
        cls,
        group_id: int,
        messages: list[tuple[Message, IS_RECV]],
    ) -> Message | None:
        consecutive = 0
        repeated_message, is_recv = messages[-1]
        contains_self = not is_recv
        for msg, is_recv in reversed(messages[:-1]):
            if not MS.message_equals(msg, repeated_message):
                break
            consecutive += 1
            repeated_message = msg
            contains_self = contains_self or not is_recv
        if consecutive < cls.RP_MIN_CONSECUTIVE:
            return
        prob = (cls.RP_PROB_MIN + (cls.RP_PROB_MAX - cls.RP_PROB_MIN) *
                (consecutive - cls.RP_MIN_CONSECUTIVE) /
                (cls.RP_MAX_CONSECUTIVE - cls.RP_MIN_CONSECUTIVE))
        if random.random() > prob:
            return
        # check if already repeated
        if not contains_self:
            # if not, repeat
            return repeated_message
        if consecutive >= cls.RP_BREAK_MIN_CONSECUTIVE:
            prob = (cls.RP_BREAK_PROB_MIN +
                    (consecutive - cls.RP_BREAK_MIN_CONSECUTIVE) *
                    cls.RP_BREAK_PROB_INC)
            prob = min(prob, cls.RP_BREAK_PROB_MAX)
            if random.random() < prob:
                return Message(cls.RP_RE_BREAK_TEXT if repeated_message.
                               extract_plain_text() ==
                               cls.RP_BREAK_TEXT else cls.RP_BREAK_TEXT)

    @classmethod
    async def keyword_response(
        cls,
        group_id: int,
        messages: list[tuple[Message, IS_RECV]],
    ) -> Message | None:
        recv_text = [
            t for m, r in messages if r and (t := m.extract_plain_text())
        ]
        query = " ".join(recv_text)
        if len(query) < cls.KW_MIN_QUERY_LEN:
            return
        if random.random() > cls.KW_PROB:
            return
        words = Keyword.extract(query)
        words = [re.escape(w) for w in words]
        regex = "|".join(set(words))
        entries = await Corpus.find(
            group_id,
            length=(cls.KW_MIN_CORPUS_LEN, cls.KW_MAX_CORPUS_LEN),
            filter={
                "text": {
                    "$regex": regex,
                    "$options": "i"
                }
            },
            sample=cls.KW_CORPUS_SAMPLE,
        ).to_list(length=cls.KW_CORPUS_SAMPLE)
        # filter again, I don't know why length is not working
        corpus = [
            e["text"] for e in entries
            if len(e["text"]) > cls.KW_MIN_CORPUS_LEN
        ]
        results = Keyword.search([query],
                                 corpus,
                                 threshold=cls.KW_SIM_THRESHOLD)
        if results:
            return Message(random.choice(results))
