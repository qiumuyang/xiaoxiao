"""https://lab.magiconch.com/nbnhhsh/"""

import random
import re
from typing import ClassVar, TypedDict

import aiohttp
from async_lru import alru_cache
from nonebot import on_command, on_regex
from nonebot.adapters.onebot.v11 import GroupMessageEvent
from nonebot.matcher import Matcher
from typing_extensions import NotRequired

from src.ext import RateLimit, RateLimiter
from src.ext.config import Config, ConfigManager


class Response(TypedDict):
    name: str
    inputting: NotRequired[list[str]]
    trans: NotRequired[list[str]]


class AbbrTranslateConfig(Config):
    user_friendly: ClassVar[str] = "翻译缩写"

    includes: dict[str, list[str]] = {}
    excludes: dict[str, list[str]] = {}


class AbbreviationTranslate:

    URL = "https://lab.magiconch.com/api/nbnhhsh/guess"
    client: aiohttp.ClientSession | None = None

    PATTERN = r"^[a-zA-Z\d]{2,10}$"  # requires fullmatch
    CFG_PATTERN = re.compile(r"([+-])([a-zA-Z\d]{2,10})(?:->|→)([^\s]+)")
    CUSTOM_MAX_LEN = 20

    @staticmethod
    @alru_cache(maxsize=256)
    async def fetch(abbr: str) -> list[Response]:
        """Query abbreviation from nbnhhsh API.

        Returns:
            list[Response]: Each fragment of the abbreviation.
        """
        if AbbreviationTranslate.client is None:
            AbbreviationTranslate.client = aiohttp.ClientSession()
        client = AbbreviationTranslate.client
        data = {"text": abbr}
        async with client.post(AbbreviationTranslate.URL, data=data) as resp:
            resp.raise_for_status()
            return await resp.json()

    @staticmethod
    async def query(
        abbr: str,
        includes: dict[str, list[str]] | None = None,
        excludes: dict[str, list[str]] | None = None,
    ) -> str:
        abbr = abbr.lower()
        try:
            results = await AbbreviationTranslate.fetch(abbr)
        except:
            return ""

        includes = includes or {}
        excludes = excludes or {}
        if len(results) > 1 and (choices := includes.get(abbr, [])):
            # only enable when there are multiple parts
            return random.choice(choices)

        text = []
        for part in results:
            trans = part.get("trans")
            inputting = part.get("inputting")
            include = set(includes.get(part["name"], []))
            exclude = set(excludes.get(part["name"], []))
            choices = set(trans or inputting or [""]) - exclude
            choices |= include
            if not choices:
                if text:
                    break
                else:
                    continue
            text.append(random.choice(list(choices)))
        return "".join(filter(None, text))


rate_depend = RateLimit("abbr_trans", type="group", seconds=2)

# lower priority than commands
nbnhhsh_msg = on_regex(AbbreviationTranslate.PATTERN, priority=2, block=True)
nbnhhsh_cmd = on_command("翻译缩写",
                         aliases={"nbnhhsh"},
                         block=True,
                         force_whitespace=True)


@nbnhhsh_cmd.handle()
@nbnhhsh_msg.handle()
async def _(
    matcher: Matcher,
    event: GroupMessageEvent,
    ratelimiter: RateLimiter = rate_depend,
):
    cfg = await ConfigManager.get_group(event.group_id, AbbrTranslateConfig)
    abbr = event.get_message().extract_plain_text()
    is_cmd = abbr.startswith("翻译缩写")
    abbr = abbr.removeprefix("翻译缩写").strip()
    if is_cmd and abbr.startswith(("+", "-")):
        await config_abbr(matcher, event, abbr)
        return
    translation = await AbbreviationTranslate.query(abbr, cfg.includes,
                                                    cfg.excludes)
    if not translation or not ratelimiter.try_acquire():
        await matcher.finish()
    await matcher.finish(translation)


async def config_abbr(
    matcher: Matcher,
    event: GroupMessageEvent,
    message: str,
):
    cfg = await ConfigManager.get_group(event.group_id, AbbrTranslateConfig)
    abbrs = set()
    for config_match in AbbreviationTranslate.CFG_PATTERN.finditer(message):
        op, abbr, t = config_match.groups()
        abbr = abbr.lower()
        ilst = cfg.includes.setdefault(abbr, [])
        elst = cfg.excludes.setdefault(abbr, [])
        # Note: here we use a 2-step config
        # if already configured, remove from the configuration
        # else add to the configuration
        if op == "+":
            if len(t) > AbbreviationTranslate.CUSTOM_MAX_LEN:
                continue
            if t in elst:
                elst.remove(t)
            elif t not in ilst:
                ilst.append(t)
        elif op == "-":
            if t in ilst:
                ilst.remove(t)
            elif t not in elst:
                elst.append(t)
        else:
            raise ValueError(f"Unknown operation: {op}")
        abbrs.add(abbr)
    await ConfigManager.set_group(event.group_id, cfg)

    lines = []
    for abbr in sorted(abbrs):
        ilst = cfg.includes.get(abbr, [])
        elst = cfg.excludes.get(abbr, [])
        line = f"【{abbr}】"
        if ilst:
            line += f"\n  + {'|'.join(ilst)}"
        if elst:
            line += f"\n  - {'|'.join(elst)}"
        if not ilst and not elst:
            line += " 无"
        lines.append(line)
    if lines:
        await matcher.finish("\n".join(lines))
