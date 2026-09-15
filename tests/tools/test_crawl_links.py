from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from schemas.crawl_links import CrawlLink
from tools.crawl.links import extract_links, filter_document_links
from tools.policy.crawl_policy import is_allowed_domain, is_binary_content_type
from tools.crawl.structured import extract_with_schema


class _Handler(BaseHTTPRequestHandler):
    request_count = 0

    def do_GET(self):  # noqa: N802
        _Handler.request_count += 1
        if self.path.endswith(".pdf"):
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Length", "12")
            self.end_headers()
            self.wfile.write(b"%PDF-1.4 fake")
        else:
            body = (
                b"<html><body>"
                b"<a href='/report.pdf'>Report</a>"
                b"<a href='https://other.example.com/data.xlsx'>Data</a>"
                b"</body></html>"
            )
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass


@pytest.fixture
def http_server():
    _Handler.request_count = 0
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()
    thread.join()


class TestCrawlLinksModule:
    def test_extract_links_maps_internal_external(self):
        html = (
            "<html><body>"
            "<a href='https://example.com/a' title='TA'>A</a>"
            "<a href='https://example.com/b'>B</a>"
            "<a href='https://other.com/x'>X</a>"
            "</body></html>"
        )

        links = extract_links(html, "https://example.com/")
        assert len(links) == 3
        assert links[0].is_internal is True
        assert links[0].url == "https://example.com/a"
        assert links[0].text == "A"
        assert links[0].title == "TA"
        assert links[2].is_internal is False

    def test_extract_links_resolves_relative_urls(self):
        html = "<html><body><a href='/docs/guide'>Guide</a></body></html>"

        links = extract_links(html, "https://example.com/page")
        assert [link.url for link in links] == ["https://example.com/docs/guide"]
        assert links[0].is_internal is True

    def test_extract_links_no_links(self):
        assert extract_links("<html><body><p>no anchors</p></body></html>") == []
        assert extract_links("") == []

    def test_filter_document_links_by_extension(self):
        links = [
            CrawlLink(url="https://example.com/report.pdf"),
            CrawlLink(url="https://example.com/page"),
            CrawlLink(url="https://other.com/data.xlsx"),
            CrawlLink(url="https://example.com/a.zip?download=1"),
            CrawlLink(url="https://example.com/b.csv#frag"),
        ]
        docs = filter_document_links(links)
        assert [d.url for d in docs] == [
            "https://example.com/report.pdf",
            "https://other.com/data.xlsx",
            "https://example.com/a.zip?download=1",
            "https://example.com/b.csv#frag",
        ]

    def test_filter_document_links_by_domain_keeps_content_docs(self):
        links = [
            CrawlLink(url="https://example.com/report.pdf"),
            CrawlLink(url="https://other.com/data.xlsx"),
            CrawlLink(url="https://www.example.com/r2.pdf"),
        ]
        docs = filter_document_links(links, ["example.com"])
        assert [d.url for d in docs] == [
            "https://example.com/report.pdf",
            "https://other.com/data.xlsx",
            "https://www.example.com/r2.pdf",
        ]

    def test_filter_document_links_restricts_when_page_out_of_scope(self):
        links = [
            CrawlLink(url="https://example.com/report.pdf"),
            CrawlLink(url="https://other.com/data.xlsx"),
        ]
        docs = filter_document_links(links, ["example.com"], page_url="https://elsewhere.com/")
        assert [d.url for d in docs] == ["https://example.com/report.pdf"]


class TestCrawlPolicy:
    def test_is_binary_content_type(self):
        assert is_binary_content_type("application/pdf")
        assert is_binary_content_type("application/pdf; charset=binary")
        assert is_binary_content_type("application/zip")
        assert is_binary_content_type("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        assert not is_binary_content_type("text/html; charset=utf-8")
        assert not is_binary_content_type(None)

    def test_is_allowed_domain(self):
        assert is_allowed_domain("https://example.com/x", ["example.com"])
        assert is_allowed_domain("https://www.example.com/x", ["example.com"])
        assert not is_allowed_domain("https://other.com/x", ["example.com"])
        assert is_allowed_domain("https://other.com/x", None)


class TestCrawlStructured:
    def test_extract_with_schema(self):
        html = (
            "<div class='item'><h2>Item 1</h2><p>2026-01-01</p></div>"
            "<div class='item'><h2>Item 2</h2><p>2026-01-02</p></div>"
        )
        schema = {
            "name": "Items",
            "baseSelector": "div.item",
            "fields": [
                {"name": "title", "selector": "h2", "type": "text"},
                {"name": "date", "selector": "p", "type": "text"},
            ],
        }
        data = extract_with_schema(html, schema)
        assert data is not None
        assert '"title"' in data
        assert "Item 1" in data

    def test_extract_with_schema_invalid(self):
        assert extract_with_schema("", {"name": "x", "baseSelector": "div"}) is None
        assert extract_with_schema("<div></div>", None) is None
        assert extract_with_schema("<div></div>", {}) is None


class TestCrawlUrlRaw:
    @pytest.mark.asyncio
    async def test_crawl_raw_links_and_documents(self):
        from tools.crawl.service import crawl_url

        html = (
            "<html><head><title>Test</title></head><body>"
            "<a href='https://example.com/report.pdf'>Report</a>"
            "<a href='https://example.com/home'>Home</a>"
            "<a href='https://other.com/data.xlsx'>Data</a>"
            "</body></html>"
        )
        result = await crawl_url("raw://" + html)
        assert result.success
        assert result.title == "Test"
        assert result.is_document is False
        assert len(result.links) == 3
        assert [d.url for d in result.document_links] == [
            "https://example.com/report.pdf",
            "https://other.com/data.xlsx",
        ]

    @pytest.mark.asyncio
    async def test_crawl_raw_allowed_domains_filters_documents(self):
        from tools.crawl.service import crawl_url

        html = (
            "<html><body>"
            "<a href='https://example.com/report.pdf'>Report</a>"
            "<a href='https://other.com/data.xlsx'>Data</a>"
            "</body></html>"
        )
        result = await crawl_url("raw://" + html, allowed_domains=["example.com"])
        assert result.success
        assert [d.url for d in result.document_links] == ["https://example.com/report.pdf"]

    @pytest.mark.asyncio
    async def test_crawl_raw_extraction_schema(self):
        from tools.crawl.service import crawl_url

        html = (
            "<html><body>"
            "<div class='item'><h2>Title A</h2><p>2026-01-01</p></div>"
            "</body></html>"
        )
        schema = {
            "name": "Items",
            "baseSelector": "div.item",
            "fields": [
                {"name": "title", "selector": "h2", "type": "text"},
            ],
        }
        result = await crawl_url("raw://" + html, extraction_schema=schema)
        assert result.success
        assert result.extracted_data is not None
        assert "Title A" in result.extracted_data


class TestCrawlUrlHttp:
    @pytest.mark.asyncio
    async def test_content_type_gate_routes_binary_to_downloader(self, http_server):
        from tools.crawl.service import crawl_url

        result = await crawl_url(http_server + "/doc.pdf")
        assert result.success
        assert result.is_document is True
        assert result.content_type == "application/pdf"
        assert "download_file" in result.markdown

    @pytest.mark.asyncio
    async def test_crawl_html_http(self, http_server):
        from tools.crawl.service import crawl_url

        result = await crawl_url(http_server + "/")
        assert result.success
        assert result.is_document is False
        assert "Report" in result.markdown or "report.pdf" in result.markdown

    @pytest.mark.asyncio
    async def test_cache_hit_avoids_refetch(self, http_server):
        from tools.crawl.service import crawl_url

        url = http_server + "/"
        first = await crawl_url(url)
        assert first.success
        count_after_first = _Handler.request_count

        second = await crawl_url(url)
        assert second.success
        assert second.markdown == first.markdown
        assert _Handler.request_count == count_after_first
