"""https://lab.magiconch.com/nbnhhsh/"""

import json
import random
from functools import lru_cache
from typing import TypedDict

import requests
from nonebot import on_command, on_regex
from nonebot.adapters.onebot.v11 import MessageEvent
from nonebot.matcher import Matcher
from typing_extensions import NotRequired

from src.ext import ratelimit


class Response(TypedDict):
    name: str
    inputting: NotRequired[list[str]]
    trans: NotRequired[list[str]]


class AbbreviationTranslate:

    URL = "https://lab.magiconch.com/api/nbnhhsh/guess"
    TIMEOUT = 5

    PATTERN = r"^[a-zA-Z\d]{2,10}$"  # requires fullmatch

    @staticmethod
    @lru_cache(maxsize=256)
    def fetch(abbr: str) -> list[Response]:
        """Query abbreviation from nbnhhsh API.

        Returns:
            list[Response]: Each fragment of the abbreviation.
        """
        r = requests.post(AbbreviationTranslate.URL,
                          data={"text": abbr},
                          timeout=AbbreviationTranslate.TIMEOUT)
        r.raise_for_status()
        return json.loads(r.text)

    @staticmethod
    def query(abbr: str) -> str:
        try:
            results = AbbreviationTranslate.fetch(abbr)
        except:
            return ""

        text = []
        for part in results:
            trans = part.get("trans")
            inputting = part.get("inputting")
            text.append(random.choice(trans or inputting or [""]))
        return "".join(filter(None, text))


rate = ratelimit("abbr_trans", type="group", seconds=2)

# lower priority than commands
nbnhhsh_msg = on_regex(AbbreviationTranslate.PATTERN, priority=2, rule=rate)
nbnhhsh_cmd = on_command("翻译缩写",
                         aliases={"nbnhhsh"},
                         rule=rate,
                         block=True,
                         force_whitespace=True)


async def abbr(matcher: Matcher, event: MessageEvent):
    abbr = event.get_message().extract_plain_text()
    translation = AbbreviationTranslate.query(abbr)
    await matcher.finish(translation or None)  # empty string does send msg


nbnhhsh_cmd.handle()(abbr)
nbnhhsh_msg.handle()(abbr)
