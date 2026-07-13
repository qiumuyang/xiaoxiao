from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import ClientSession

from src.utils.web_fetch import scrape_from_text, scrape_images
from src.utils.web_fetch.base import ImageInfo
from src.utils.web_fetch.errors import ScrapeError
from src.utils.web_fetch.platforms.bilibili_opus import (
    BilibiliOpusScraper,
    _resolve_b23,
)

OPUS_HTML_SINGLE = """<html><body>
<div class="content">
<img src="//i0.hdslb.com/bfs/new_dyn/abc123.jpg@1044w" data-index="0">
</div>
</body></html>"""

OPUS_HTML_MULTIPLE = """<html><body>
<div class="content">
<img src="//i0.hdslb.com/bfs/new_dyn/img1.png@1044w">
<img src="//i1.hdslb.com/bfs/new_dyn/img2.webp@1044w">
<img src="//i0.hdslb.com/bfs/article/img3.jpg@800w" class="not-dyn">
</div>
</body></html>"""

OPUS_HTML_NO_IMAGES = """<html><body>
<div class="content">纯文字内容，没有图片</div>
</body></html>"""


def make_mock_response(status: int, text: str, url: str = "https://www.bilibili.com/opus/123456"):
    mock = MagicMock()
    mock.status = status
    mock.text = AsyncMock(return_value=text)
    mock.url = url

    async def mock_aenter(_self):
        return mock

    async def mock_aexit(_self, *_):
        pass

    MockCtx = MagicMock()
    MockCtx.__aenter__ = mock_aenter
    MockCtx.__aexit__ = mock_aexit
    return MockCtx


class TestBilibiliOpusScraperMatch:
    def test_match_opus_url(self):
        assert BilibiliOpusScraper.match("https://www.bilibili.com/opus/123456")
        assert BilibiliOpusScraper.match("https://bilibili.com/opus/123456")
        assert BilibiliOpusScraper.match("http://www.bilibili.com/opus/123456?share_from=article")

    def test_match_b23_url(self):
        assert BilibiliOpusScraper.match("https://b23.tv/QuohVOX")
        assert BilibiliOpusScraper.match("http://b23.tv/abc123")

    def test_no_match_video(self):
        assert not BilibiliOpusScraper.match("https://www.bilibili.com/video/BV1xx411c7mD")
        assert not BilibiliOpusScraper.match("https://bilibili.com/bangumi/play/ep123")

    def test_no_match_article(self):
        assert not BilibiliOpusScraper.match("https://www.bilibili.com/read/cv123456")

    def test_no_match_other(self):
        assert not BilibiliOpusScraper.match("https://www.example.com/page")
        assert not BilibiliOpusScraper.match("")


class TestBilibiliOpusScraperScrape:
    @pytest.mark.anyio
    async def test_extract_single_image(self):
        scraper = BilibiliOpusScraper()
        session = MagicMock(spec=ClientSession)
        session.get.return_value = make_mock_response(200, OPUS_HTML_SINGLE)

        result = await scraper.scrape_images("https://www.bilibili.com/opus/123456", session)

        assert len(result) == 1
        assert isinstance(result[0], ImageInfo)
        assert result[0].url == "https://i0.hdslb.com/bfs/new_dyn/abc123.jpg"
        assert result[0].filename == "abc123.jpg"

    @pytest.mark.anyio
    async def test_extract_multiple_images(self):
        scraper = BilibiliOpusScraper()
        session = MagicMock(spec=ClientSession)
        session.get.return_value = make_mock_response(200, OPUS_HTML_MULTIPLE)

        result = await scraper.scrape_images("https://www.bilibili.com/opus/123456", session)

        assert len(result) == 3
        assert result[0].url == "https://i0.hdslb.com/bfs/new_dyn/img1.png"
        assert result[1].url == "https://i1.hdslb.com/bfs/new_dyn/img2.webp"
        assert result[2].url == "https://i0.hdslb.com/bfs/article/img3.jpg"
        assert result[0].filename == "img1.png"
        assert result[1].filename == "img2.webp"
        assert result[2].filename == "img3.jpg"

    @pytest.mark.anyio
    async def test_no_images_returns_empty(self):
        scraper = BilibiliOpusScraper()
        session = MagicMock(spec=ClientSession)
        session.get.return_value = make_mock_response(200, OPUS_HTML_NO_IMAGES)

        result = await scraper.scrape_images("https://www.bilibili.com/opus/123456", session)

        assert result == []

    @pytest.mark.anyio
    async def test_http_error_raises(self):
        scraper = BilibiliOpusScraper()
        session = MagicMock(spec=ClientSession)
        session.get.return_value = make_mock_response(404, "")

        with pytest.raises(ScrapeError, match="B站请求失败"):
            await scraper.scrape_images("https://www.bilibili.com/opus/123456", session)

    @pytest.mark.anyio
    async def test_http_503_raises(self):
        scraper = BilibiliOpusScraper()
        session = MagicMock(spec=ClientSession)
        session.get.return_value = make_mock_response(503, "")

        with pytest.raises(ScrapeError, match="B站请求失败"):
            await scraper.scrape_images("https://www.bilibili.com/opus/123456", session)

    @pytest.mark.anyio
    async def test_b23_resolves_then_scrapes(self):
        scraper = BilibiliOpusScraper()
        session = MagicMock(spec=ClientSession)

        mock_head_resp = make_mock_response(200, "", url="https://www.bilibili.com/opus/123456")
        mock_get_resp = make_mock_response(200, OPUS_HTML_SINGLE)
        session.head.return_value = mock_head_resp
        session.get.return_value = mock_get_resp

        result = await scraper.scrape_images("https://b23.tv/QuohVOX", session)

        assert len(result) == 1
        assert result[0].url == "https://i0.hdslb.com/bfs/new_dyn/abc123.jpg"

    @pytest.mark.anyio
    async def test_b23_resolve_failure_raises(self):
        scraper = BilibiliOpusScraper()
        session = MagicMock(spec=ClientSession)
        session.head.return_value = make_mock_response(404, "")

        with pytest.raises(ScrapeError, match="B站短链接解析失败"):
            await scraper.scrape_images("https://b23.tv/deadlink", session)

    @pytest.mark.anyio
    async def test_b23_resolves_to_non_opus_raises(self):
        scraper = BilibiliOpusScraper()
        session = MagicMock(spec=ClientSession)
        session.head.return_value = make_mock_response(
            200, "", url="https://www.bilibili.com/video/BV1xx411c7mD"
        )

        with pytest.raises(ScrapeError, match="B站短链接非图文"):
            await scraper.scrape_images("https://b23.tv/somevideo", session)


class TestScrapeImagesDispatch:
    @pytest.mark.anyio
    async def test_opus_url_dispatches_to_opus_scraper(self):
        with (
            patch("src.utils.web_fetch.aiohttp.ClientSession") as mock_cls,
            patch(
                "src.utils.web_fetch.platforms.bilibili_opus.BilibiliOpusScraper.scrape_images",
                new_callable=AsyncMock,
            ) as mock_scrape,
        ):
            mock_scrape.return_value = [ImageInfo(url="https://img.test/1.jpg", filename="1.jpg")]
            mock_session = MagicMock()
            mock_cls.return_value.__aenter__.return_value = mock_session

            result = await scrape_images("https://www.bilibili.com/opus/123456")

            assert len(result) == 1
            assert result[0].url == "https://img.test/1.jpg"
            mock_scrape.assert_awaited_once()

    @pytest.mark.anyio
    async def test_unsupported_url_raises(self):
        with patch("src.utils.web_fetch.aiohttp.ClientSession") as mock_cls:
            mock_session = MagicMock()
            mock_cls.return_value.__aenter__.return_value = mock_session

            with pytest.raises(ScrapeError, match="暂不支持该链接类型"):
                await scrape_images("https://www.bilibili.com/video/BV1xx411c7mD")


class TestScrapeFromText:
    @pytest.mark.anyio
    async def test_no_url_returns_none(self):
        with patch("src.utils.web_fetch.aiohttp.ClientSession"):
            result = await scrape_from_text("这是一条普通消息")
            assert result is None

    @pytest.mark.anyio
    async def test_opus_url_extracts_images(self):
        with (
            patch("src.utils.web_fetch.aiohttp.ClientSession") as mock_cls,
            patch(
                "src.utils.web_fetch.platforms.bilibili_opus.BilibiliOpusScraper.scrape_images",
                new_callable=AsyncMock,
            ) as mock_scrape,
        ):
            mock_scrape.return_value = [ImageInfo(url="https://img.test/1.jpg", filename="1.jpg")]
            mock_session = MagicMock()
            mock_cls.return_value.__aenter__.return_value = mock_session

            result = await scrape_from_text("看看这个 https://www.bilibili.com/opus/123456")

            assert result is not None
            assert len(result) == 1
            assert result[0].url == "https://img.test/1.jpg"
            mock_scrape.assert_awaited_once()

    @pytest.mark.anyio
    async def test_unsupported_url_returns_none(self):
        with patch("src.utils.web_fetch.aiohttp.ClientSession") as mock_cls:
            mock_session = MagicMock()
            mock_cls.return_value.__aenter__.return_value = mock_session

            result = await scrape_from_text("看看 https://www.bilibili.com/video/BV1xx411c7mD")
            assert result is None


class TestResolveB23:
    @pytest.mark.anyio
    async def test_resolve_success(self):
        session = MagicMock(spec=ClientSession)
        mock_resp = make_mock_response(200, "")
        mock_resp.url = "https://www.bilibili.com/opus/123456"
        session.head.return_value = mock_resp

        result = await _resolve_b23("https://b23.tv/abc", session)
        assert result == "https://www.bilibili.com/opus/123456"

    @pytest.mark.anyio
    async def test_resolve_failure(self):
        session = MagicMock(spec=ClientSession)
        session.head.return_value = make_mock_response(404, "")

        with pytest.raises(ScrapeError, match="B站短链接解析失败"):
            await _resolve_b23("https://b23.tv/dead", session)
