import random
import re
from datetime import datetime, timedelta

from src.utils.message.receive import ReceivedMessageTracker as RMT

from .corpus import Corpus
from .keywords import Keyword


class Interact:

    INTERVAL = timedelta(seconds=90)
    MIN_LEN_QUERY = 10
    NUM_MSG = 3

    PROB = 0.2

    MIN_LEN_CORPUS = 6
    MAX_LEN_CORPUS = 40
    SAMPLE = 128
    SIM_THRESHOLD = 0.75

    @classmethod
    async def response(cls, group_id: int, message: str) -> str | None:
        messages = await RMT.find(group_id=group_id,
                                  handled=False,
                                  since=datetime.now() - cls.INTERVAL)
        messages.sort(key=lambda m: m.time)
        messages = [
            m for m in messages if m.content.extract_plain_text().strip()
        ]
        if len(messages) < cls.NUM_MSG - 1:
            return
        text = [m.content.extract_plain_text() for m in messages]
        text.append(message)
        query = " ".join(text)
        if len(query) < cls.MIN_LEN_QUERY:
            return
        if random.random() > cls.PROB:
            return
        words = Keyword.extract(query)
        words = [re.escape(w) for w in words]
        regex = "|".join(set(words))
        entries = await Corpus.find(
            group_id,
            length=(cls.MIN_LEN_CORPUS, cls.MAX_LEN_CORPUS),
            filter={
                "text": {
                    "$regex": regex,
                    "$options": "i"
                }
            },
            sample=cls.SAMPLE,
        ).to_list(length=cls.SAMPLE)
        # filter again, I don't know why length is not working
        corpus = [
            e["text"] for e in entries if len(e["text"]) > cls.MIN_LEN_CORPUS
        ]
        results = Keyword.search([message],
                                 corpus,
                                 threshold=cls.SIM_THRESHOLD)
        if results:
            return random.choice(results)
