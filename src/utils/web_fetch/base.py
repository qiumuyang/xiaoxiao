import re
from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from typing import ClassVar

from aiohttp import ClientSession


@dataclass
class ImageInfo:
    url: str
    filename: str


class Scraper(ABC):
    PATTERNS: ClassVar[Sequence[re.Pattern]] = []
    URL_PATTERNS: ClassVar[Sequence[re.Pattern]] = []
    HEADERS: ClassVar[dict[str, str]] = {}

    @classmethod
    def match(cls, url: str) -> bool:
        return any(p.search(url) for p in cls.PATTERNS)

    @abstractmethod
    async def scrape_images(self, url: str, session: ClientSession) -> list[ImageInfo]:
        raise NotImplementedError
