import re

import aiohttp

from .base import ImageInfo, Scraper
from .errors import ScrapeError
from .platforms.bilibili_opus import BilibiliOpusScraper

SCRAPERS: list[type[Scraper]] = [BilibiliOpusScraper]

URL_PATTERN = re.compile("|".join(p.pattern for s in SCRAPERS for p in s.URL_PATTERNS))


async def scrape_images(url: str) -> list[ImageInfo]:
    for scraper_cls in SCRAPERS:
        if scraper_cls.match(url):
            async with aiohttp.ClientSession(headers=scraper_cls.HEADERS) as session:
                return await scraper_cls().scrape_images(url, session)
    raise ScrapeError("暂不支持该链接类型")


async def scrape_from_text(text: str) -> list[ImageInfo] | None:
    m = URL_PATTERN.search(text)
    if not m:
        return None
    return await scrape_images(m.group(0))
