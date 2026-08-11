from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import quote

import pytest

from browser import get_manager
from browser.links import LinkExtraction, StructuredLink, extract_links
from browser.tabs import TabManager
from browser.trace import ClickTracer
from tools.browser import browser_click, browser_extract_links, browser_get_tabs, browser_switch_tab


@pytest.fixture(autouse=True)
def _cleanup_browser():
    get_manager().reset()
    yield
    get_manager().reset()


class TestBrowserExtractLinks:
    @pytest.mark.asyncio
    async def test_without_launch(self):
        with patch.object(get_manager(), "_page", None):
            result = await browser_extract_links(None)
            assert "not launched" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_extract_links_success(self):
        mock_page = AsyncMock()
        mock_page.evaluate = AsyncMock(return_value={
            "total": 2,
            "links": [
                {
                    "text": "Docs",
                    "url": "https://example.com/docs",
                    "title": "Docs page",
                    "base_domain": "example.com",
                    "target": "_blank",
                    "new_tab": True,
                    "is_internal": True,
                },
                {
                    "text": "",
                    "url": "https://other.com/x",
                    "title": "",
                    "base_domain": "other.com",
                    "target": "",
                    "new_tab": False,
                    "is_internal": False,
                },
            ],
        })
        with patch.object(get_manager(), "_page", mock_page):
            result = await browser_extract_links(None, max_links=10)
        assert result["total"] == 2
        assert any(l["url"] == "https://example.com/docs" for l in result["links"])
        assert all("new_tab" in l for l in result["links"])
        assert all("is_internal" in l for l in result["links"])
        assert all("title" not in l for l in result["links"])
        assert all("base_domain" not in l for l in result["links"])
        assert all("target" not in l for l in result["links"])
        _, args = mock_page.evaluate.await_args.args
        assert args == ["", 0, 10, True, True]

    @pytest.mark.asyncio
    async def test_extract_links_include_metadata(self):
        mock_page = AsyncMock()
        mock_page.evaluate = AsyncMock(return_value={
            "total": 1,
            "links": [
                {
                    "text": "Docs",
                    "url": "https://example.com/docs",
                    "title": "Docs page",
                    "base_domain": "example.com",
                    "target": "_blank",
                    "new_tab": True,
                    "is_internal": True,
                }
            ],
        })
        with patch.object(get_manager(), "_page", mock_page):
            result = await browser_extract_links(None, include_metadata=True)
        assert result["links"][0]["title"] == "Docs page"
        assert result["links"][0]["base_domain"] == "example.com"
        assert result["links"][0]["target"] == "_blank"

    @pytest.mark.asyncio
    async def test_pagination_truncated_flag(self):
        mock_page = AsyncMock()
        mock_page.evaluate = AsyncMock(return_value={
            "total": 5,
            "links": [
                {
                    "text": f"L{i}",
                    "url": f"https://example.com/{i}",
                    "title": "",
                    "base_domain": "example.com",
                    "target": "",
                    "new_tab": False,
                    "is_internal": True,
                }
                for i in range(3)
            ],
        })
        with patch.object(get_manager(), "_page", mock_page):
            result = await browser_extract_links(None, max_links=3, page=1)
        assert result["total"] == 5
        assert result["truncated"] is True
        assert any(l["url"] == "https://example.com/0" for l in result["links"])

    @pytest.mark.asyncio
    async def test_page_out_of_range(self):
        mock_page = AsyncMock()
        mock_page.evaluate = AsyncMock(return_value={"total": 5, "links": []})
        with patch.object(get_manager(), "_page", mock_page):
            result = await browser_extract_links(None, max_links=3, page=9)
        assert result["links"] == []
        assert result["total"] == 5

    @pytest.mark.asyncio
    async def test_filter_args_passed_to_extractor(self):
        mock_page = AsyncMock()
        mock_page.evaluate = AsyncMock(return_value={"total": 0, "links": []})
        with patch.object(get_manager(), "_page", mock_page):
            await browser_extract_links(
                None, max_links=7, page=2, include_external=False, unique_only=False
            )
        _, args = mock_page.evaluate.await_args.args
        assert args == ["", 7, 7, False, False]

    @pytest.mark.asyncio
    async def test_extract_links_empty(self):
        mock_page = AsyncMock()
        mock_page.evaluate = AsyncMock(return_value={"total": 0, "links": []})
        with patch.object(get_manager(), "_page", mock_page):
            result = await browser_extract_links(None)
            assert result["total"] == 0
            assert result["links"] == []

    @pytest.mark.asyncio
    async def test_extract_links_error(self):
        mock_page = AsyncMock()
        mock_page.evaluate = AsyncMock(side_effect=Exception("boom"))
        with patch.object(get_manager(), "_page", mock_page):
            result = await browser_extract_links(None)
            assert "failed" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_document_only_keeps_external_cdn_docs(self):
        mock_page = AsyncMock()
        mock_page.url = "https://investor.oracle.com/sec-filings/"
        mock_page.evaluate = AsyncMock(return_value={
            "total": 2,
            "links": [
                {
                    "text": "8-K", "url": "https://d1io.cloudfront.net/8-k.pdf",
                    "title": "", "base_domain": "d1io.cloudfront.net",
                    "target": "", "new_tab": False, "is_internal": False,
                },
                {
                    "text": "Home", "url": "https://investor.oracle.com/",
                    "title": "", "base_domain": "investor.oracle.com",
                    "target": "", "new_tab": False, "is_internal": True,
                },
            ],
        })
        mock_page.request = AsyncMock()
        mock_page.request.head = AsyncMock(return_value=AsyncMock())
        mock_page.request.get = AsyncMock(return_value=AsyncMock())
        with patch.object(get_manager(), "_page", mock_page):
            result = await browser_extract_links(
                None, document_only=True, allowed_domains="investor.oracle.com",
                resolve_redirects=False,
            )
        assert any("cloudfront.net/8-k.pdf" in l["url"] for l in result["links"])
        assert all("investor.oracle.com/" not in l["url"] for l in result["links"])

    @pytest.mark.asyncio
    async def test_resolve_redirects_follows_to_final_url(self):
        mock_page = AsyncMock()
        mock_page.url = "https://investor.oracle.com/sec-filings/"
        mock_page.evaluate = AsyncMock(return_value={
            "total": 1,
            "links": [
                {
                    "text": "Report", "url": "https://investor.oracle.com/node/123",
                    "title": "", "base_domain": "investor.oracle.com",
                    "target": "", "new_tab": False, "is_internal": True,
                },
            ],
        })
        resp = AsyncMock()
        resp.url = "https://d1io.cloudfront.net/report.xlsx"
        mock_page.request = AsyncMock()
        mock_page.request.head = AsyncMock(return_value=resp)
        mock_page.request.get = AsyncMock(return_value=AsyncMock())
        with patch.object(get_manager(), "_page", mock_page):
            result = await browser_extract_links(None, document_only=True, resolve_redirects=True)
        assert any("cloudfront.net/report.xlsx" in l["url"] for l in result["links"])

    @pytest.mark.asyncio
    async def test_subdomain_is_internal(self):
        from tools.policy.link_policy import is_internal_link

        assert is_internal_link("https://docs.oracle.com/x", "https://investor.oracle.com/")
        assert is_internal_link("https://www.python.org/x", "https://python.org/")
        assert not is_internal_link("https://cloudfront.net/x", "https://investor.oracle.com/")


class TestBrowserGetTabs:
    @pytest.mark.asyncio
    async def test_without_launch(self):
        with patch.object(get_manager(), "_page", None):
            result = await browser_get_tabs(None)
            assert "not launched" in result.lower()

    @pytest.mark.asyncio
    async def test_get_tabs_lists_active(self):
        mgr = get_manager()
        page0 = MagicMock()
        page0.url = "https://example.com/a"
        page0.title = AsyncMock(return_value="Title A")
        page1 = MagicMock()
        page1.url = "https://example.com/b"
        page1.title = AsyncMock(return_value="Title B")

        ctx = MagicMock()
        mgr.tabs.attach(ctx, page0)
        handler = ctx.on.call_args[0][1]
        handler(page1)

        mock_page = MagicMock()
        mock_page.url = "https://example.com/a"
        with patch.object(mgr, "_page", mock_page):
            result = await browser_get_tabs(None)
        assert "[0] ACTIVE https://example.com/a Title A" in result
        assert "[1] https://example.com/b Title B" in result


class TestBrowserSwitchTab:
    @pytest.mark.asyncio
    async def test_without_launch(self):
        result = await browser_switch_tab(None, 0)
        assert "not launched" in result.lower()

    @pytest.mark.asyncio
    async def test_switch_tab_success(self):
        mgr = get_manager()
        page0 = MagicMock()
        page0.url = "https://example.com/a"
        page0.title = AsyncMock(return_value="Title A")
        page1 = MagicMock()
        page1.url = "https://example.com/b"
        page1.title = AsyncMock(return_value="Title B")

        ctx = MagicMock()
        mgr.tabs.attach(ctx, page0)
        handler = ctx.on.call_args[0][1]
        handler(page1)

        mock_page = MagicMock()
        mock_page.url = "https://example.com/a"
        with patch.object(mgr, "_page", mock_page):
            result = await browser_switch_tab(None, 1)
        assert "Switched to tab 1" in result
        assert "example.com/b" in result
        assert mgr.tabs.active_page() is page1

    @pytest.mark.asyncio
    async def test_switch_tab_out_of_range(self):
        mgr = get_manager()
        page0 = MagicMock()
        page0.url = "https://example.com/a"
        page0.title = AsyncMock(return_value="Title A")
        mgr.tabs.attach(MagicMock(), page0)
        mock_page = MagicMock()
        mock_page.url = "https://example.com/a"
        with patch.object(mgr, "_page", mock_page):
            result = await browser_switch_tab(None, 5)
        assert "out of range" in result


class TestTabManager:
    def test_attach_tracks_initial_page(self):
        mgr = TabManager()
        page = MagicMock()
        ctx = MagicMock()
        mgr.attach(ctx, page)
        assert mgr.pages() == [page]
        assert mgr.active_page() is page
        ctx.on.assert_called_once()
        page.on.assert_called_once()

    def test_new_page_appended_and_active_unchanged(self):
        mgr = TabManager()
        page0 = MagicMock()
        page1 = MagicMock()
        ctx = MagicMock()
        mgr.attach(ctx, page0)
        handler = ctx.on.call_args[0][1]
        handler(page1)
        assert mgr.pages() == [page0, page1]
        assert mgr.active_page() is page0

    def test_switch_tab(self):
        mgr = TabManager()
        page0 = MagicMock()
        page1 = MagicMock()
        ctx = MagicMock()
        mgr.attach(ctx, page0)
        handler = ctx.on.call_args[0][1]
        handler(page1)
        assert mgr.switch_tab(1) is page1
        assert mgr.active_page() is page1

    def test_switch_tab_out_of_range_raises(self):
        mgr = TabManager()
        mgr.attach(MagicMock(), MagicMock())
        with pytest.raises(IndexError):
            mgr.switch_tab(3)

    @pytest.mark.asyncio
    async def test_close_tab_pops_and_readjusts_active(self):
        mgr = TabManager()
        page0 = MagicMock()
        page0.close = AsyncMock()
        page1 = MagicMock()
        page1.close = AsyncMock()
        ctx = MagicMock()
        mgr.attach(ctx, page0)
        handler = ctx.on.call_args[0][1]
        handler(page1)
        mgr.switch_tab(1)
        result = await mgr.close_tab(1)
        assert "Closed tab 1" in result
        assert mgr.pages() == [page0]
        assert mgr.active_page() is page0

    def test_page_closed_removed(self):
        mgr = TabManager()
        page0 = MagicMock()
        page1 = MagicMock()
        ctx = MagicMock()
        mgr.attach(ctx, page0)
        handler = ctx.on.call_args[0][1]
        handler(page1)
        close_handler = page1.on.call_args[0][1]
        close_handler(page1)
        assert mgr.pages() == [page0]
        assert mgr.active_page() is page0


class TestClickTracer:
    @pytest.mark.asyncio
    async def test_record_pre_click_stores_info(self):
        tracer = ClickTracer()
        page = AsyncMock()
        page.evaluate = AsyncMock(return_value={"url": "https://example.com/x", "new_tab": False})
        info = await tracer.record_pre_click(page, "a.link")
        assert info == {"url": "https://example.com/x", "new_tab": False}
        assert tracer._pre_click == info

    @pytest.mark.asyncio
    async def test_record_pre_click_ignores_non_dict(self):
        tracer = ClickTracer()
        page = AsyncMock()
        page.evaluate = AsyncMock(return_value="not-a-dict")
        info = await tracer.record_pre_click(page, "a")
        assert info is None
        assert tracer._pre_click is None

    @pytest.mark.asyncio
    async def test_record_post_nav_builds_trace(self):
        tracer = ClickTracer()
        page = AsyncMock()
        page.evaluate = AsyncMock(return_value={"url": "https://example.com/start", "new_tab": False})
        await tracer.record_pre_click(page, "a")
        page.url = "https://example.com/end"
        page.title = AsyncMock(return_value="End Page")
        trace = await tracer.record_post_nav(page)
        assert trace["final_url"] == "https://example.com/end"
        assert trace["title"] == "End Page"
        assert trace["pre_click"]["url"] == "https://example.com/start"
        assert tracer._pre_click is None


class TestBrowserClickTrace:
    @pytest.mark.asyncio
    async def test_click_records_navigation_detail(self):
        mgr = get_manager()
        mock_page = AsyncMock()
        mock_page.click = AsyncMock(return_value="Clicked element: .button")
        mock_page.evaluate = AsyncMock(return_value={
            "selector": ".button",
            "href": "/start",
            "url": "https://example.com/start",
            "text": "",
            "target": "",
            "new_tab": False,
        })
        mock_page.url = "https://example.com/end"
        mock_page.title = AsyncMock(return_value="End Page")

        with patch.object(mgr, "_page", mock_page):
            result = await browser_click(None, ".button")
        assert "Clicked" in result
        assert mgr._actions[-1]["detail"] == ".button -> https://example.com/end"
        mock_page.click.assert_awaited_once_with(".button")


class TestLinksModule:
    @pytest.mark.asyncio
    async def test_extract_links_returns_structured(self):
        page = AsyncMock()
        page.evaluate = AsyncMock(return_value={
            "total": 1,
            "links": [
                {"text": "A", "url": "https://example.com/a", "title": "", "base_domain": "example.com",
                 "target": "", "new_tab": False, "is_internal": True},
            ],
        })
        extraction = await extract_links(page, limit=5)
        assert isinstance(extraction, LinkExtraction)
        assert extraction.total == 1
        assert isinstance(extraction.links[0], StructuredLink)
        assert extraction.links[0].url == "https://example.com/a"

    @pytest.mark.asyncio
    async def test_extract_links_computes_truncated(self):
        page = AsyncMock()
        page.evaluate = AsyncMock(return_value={
            "total": 5,
            "links": [
                {"text": f"A{i}", "url": f"https://example.com/{i}", "title": "", "base_domain": "example.com",
                 "target": "", "new_tab": False, "is_internal": True}
                for i in range(3)
            ],
        })
        extraction = await extract_links(page, limit=3, offset=0)
        assert extraction.truncated is True
        assert len(extraction.links) == 3


@pytest.mark.slow
class TestBrowserLinksReal:
    @pytest.mark.asyncio
    async def test_extract_links_and_tabs(self):
        from tools.browser import browser_launch, browser_navigate

        result = await browser_launch(None)
        assert "launched successfully" in result.lower()

        html = (
            "<html><body>"
            "<a href='https://example.com/a'>A</a>"
            "<a href='https://example.com/b' target='_blank'>B</a>"
            "</body></html>"
        )
        result = await browser_navigate(None, "data:text/html," + quote(html))
        assert "navigated to" in result.lower()

        result = await browser_extract_links(None)
        assert result["total"] == 2

        result = await browser_get_tabs(None)
        assert "ACTIVE" in result

        result = await browser_switch_tab(None, 0)
        assert "Switched to tab 0" in result
