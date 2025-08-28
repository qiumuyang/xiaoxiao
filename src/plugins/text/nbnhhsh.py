"""https://lab.magiconch.com/nbnhhsh/"""

import random
import re
import shlex
from typing import ClassVar, TypedDict

import aiohttp
from async_lru import alru_cache
from nonebot import on_command, on_regex
from nonebot.adapters.onebot.v11 import GroupMessageEvent
from nonebot.matcher import Matcher
from typing_extensions import NotRequired

from src.ext import RateLimit, RateLimiter
from src.ext.config import Config
from src.utils.doc import CommandCategory, command_doc


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
    CFG_PATTERN = re.compile(r"([+-])([a-zA-Z\d]{2,10})(?:->|→)(.+)")
    CFG_USER_PATTERN = re.compile(r"([+-])([a-zA-Z\d]{2,10})")
    CUSTOM_MAX_LEN = 20

    @staticmethod
    @alru_cache(maxsize=32)
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
        if len(results) != 1 and (choices := includes.get(abbr, [])):
            # only enable when there are no/multiple parts
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
nbnhhsh_cmd = on_command("翻译缩写", block=True, force_whitespace=True)


@nbnhhsh_cmd.handle()
@nbnhhsh_msg.handle()
@command_doc("翻译缩写", category=CommandCategory.UTILITY)
async def _(
    matcher: Matcher,
    event: GroupMessageEvent,
    ratelimiter: RateLimiter = rate_depend,
):
    """
    将字母数字形式的缩写转换为原始含义

    Special:
        “能不能好好说话”

    Usage:
        {cmd} `<缩写>`               - 翻译缩写
        {cmd} `开|关`                - 开启或关闭快捷翻译缩写
        {cmd} +|-`<缩写>`->`<翻译>`  - 添加或删除自定义缩写翻译（群内共享）
        {cmd} +|-`<缩写>`             - 启用或禁用特定缩写 （个人）
        `<缩写>`                      - 快捷翻译缩写 （无需指令前缀）

    Examples:
        >>> {cmd} +dsa->大神啊
        【dsa】
          + 大神啊

    Notes:
        - 来源: [https://lab.magiconch.com/nbnhhsh/](https://lab.magiconch.com/nbnhhsh/)
    """
    cfg = await AbbrTranslateConfig.get(group_id=event.group_id)
    cfg_user = await AbbrTranslateConfig.get(group_id=event.group_id,
                                             user_id=event.user_id)
    abbr = event.get_message().extract_plain_text()
    is_cmd = abbr.startswith("翻译缩写")
    abbr = abbr.removeprefix("翻译缩写").strip()
    if is_cmd and abbr.startswith(("+", "-")):
        await config_abbr(matcher, event, abbr)
    if is_cmd and abbr in ("开", "关"):
        await toggle_abbr(matcher, event, abbr == "开")
    if not is_cmd and not cfg.enabled:
        # only disable implicit call by msg
        await matcher.finish()
    if not is_cmd and abbr in cfg_user.excludes:
        # use excludes in user config as user-level blacklist
        await matcher.finish()
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
    cfg = await AbbrTranslateConfig.get(group_id=event.group_id)
    cfg_user = await AbbrTranslateConfig.get(group_id=event.group_id,
                                             user_id=event.user_id)
    abbrs = set()
    abbrs_user = set()
    for part in shlex.split(message):
        if config_match := AbbreviationTranslate.CFG_PATTERN.fullmatch(part):
            # group-level configuration
            op, abbr, trans = config_match.groups()
            abbr = abbr.lower()
            trans = trans.strip()
            include_list = cfg.includes.setdefault(abbr, [])
            exclude_list = cfg.excludes.setdefault(abbr, [])
            # Note: here we use a 2-step config
            # if already configured, remove from the configuration
            # else add to the configuration
            if op == "+":
                if len(trans) > AbbreviationTranslate.CUSTOM_MAX_LEN:
                    continue
                if trans in exclude_list:
                    exclude_list.remove(trans)
                elif trans not in include_list:
                    include_list.append(trans)
            elif op == "-":
                if trans in include_list:
                    include_list.remove(trans)
                elif trans not in exclude_list:
                    exclude_list.append(trans)
            else:
                assert False, "unreachable"
            abbrs.add(abbr)
        elif config_user_match := AbbreviationTranslate.CFG_USER_PATTERN.fullmatch(
                part):
            # user-level configuration
            op, abbr = config_user_match.groups()
            abbr = abbr.lower()
            if op == "+":
                cfg_user.excludes.pop(abbr, None)
            elif op == "-":
                cfg_user.excludes[abbr] = []
            else:
                assert False, "unreachable"
            abbrs_user.add(abbr)
    await AbbrTranslateConfig.set(cfg, group_id=event.group_id)
    await AbbrTranslateConfig.set(cfg_user,
                                  group_id=event.group_id,
                                  user_id=event.user_id)

    lines = []
    for abbr in sorted(abbrs):
        include_list = cfg.includes.get(abbr, [])
        exclude_list = cfg.excludes.get(abbr, [])
        line = f"【{abbr}】"
        if include_list:
            line += f"\n  + {'|'.join(include_list)}"
        if exclude_list:
            line += f"\n  - {'|'.join(exclude_list)}"
        if not include_list and not exclude_list:
            line += " 无"
        lines.append(line)
    for abbr in sorted(abbrs_user):
        if abbr in cfg_user.excludes:
            lines.append(f"- {abbr}")
        else:
            lines.append(f"+ {abbr}")
    if lines:
        await matcher.finish("\n".join(lines))
    await matcher.finish()


async def toggle_abbr(
    matcher: Matcher,
    event: GroupMessageEvent,
    enabled: bool,
):
    cfg = await AbbrTranslateConfig.get(group_id=event.group_id)
    inform = cfg.enabled != enabled
    cfg.enabled = enabled
    await AbbrTranslateConfig.set(cfg, group_id=event.group_id)
    if inform:
        await matcher.finish(f"快捷翻译缩写已{'开启' if enabled else '关闭'}")
    await matcher.finish()
