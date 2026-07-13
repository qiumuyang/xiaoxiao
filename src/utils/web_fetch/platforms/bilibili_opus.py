import re
from typing import ClassVar

from aiohttp import ClientSession

from ..base import ImageInfo, Scraper
from ..errors import ScrapeError

OPUS_PATTERN = re.compile(r"bilibili\.com/opus/(\d+)")
B23_PATTERN = re.compile(r"b23\.tv/")
IMG_PATTERN = re.compile(r'<img[^>]+src="(//i\d\.hdslb\.com/bfs/(?:new_dyn|article)/[^"@]+)')
FILENAME_PATTERN = re.compile(r"/([^/]+\.(?:jpg|png|webp|jpeg|gif))(?:\?|\s|$)")


class BilibiliOpusScraper(Scraper):
    PATTERNS: ClassVar = [OPUS_PATTERN, B23_PATTERN]
    URL_PATTERNS: ClassVar = [
        re.compile(r"https?://(?:www\.)?bilibili\.com/opus/\d+"),
        re.compile(r"https?://b23\.tv/\S+"),
    ]
    HEADERS: ClassVar = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "Referer": "https://www.bilibili.com",
    }

    async def scrape_images(self, url: str, session: ClientSession) -> list[ImageInfo]:
        if B23_PATTERN.search(url):
            url = await _resolve_b23(url, session)
            if not OPUS_PATTERN.search(url):
                raise ScrapeError("B站短链接非图文")

        async with session.get(url) as resp:
            if resp.status != 200:
                raise ScrapeError(f"B站请求失败 (HTTP {resp.status})")
            html = await resp.text()

        urls: list[str] = []
        for src in IMG_PATTERN.findall(html):
            urls.append(f"https:{src}")

        if not urls:
            return []

        return [ImageInfo(url=u, filename=self._extract_filename(u)) for u in urls]

    @staticmethod
    def _extract_filename(url: str) -> str:
        m = FILENAME_PATTERN.search(url)
        return m.group(1) if m else url.split("/")[-1].split("?")[0]


async def _resolve_b23(url: str, session: ClientSession) -> str:
    async with session.head(url, allow_redirects=True, max_redirects=5) as resp:
        if resp.status != 200:
            raise ScrapeError("B站短链接解析失败")
        return str(resp.url)
