from __future__ import annotations

import hashlib
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from schemas.download_models import DownloadManifestEntry
from tools.download import manifest as download_manifest
from tools.download.service import download_file
from tools.download.tools import _parse_domains
from tools.policy.download_policy import DownloadPolicyError, is_allowed_type, validate_domain

PDF_BODY = b"PDF-1.4 fake content\n" * 4
CSV_BODY = b"name,value\na,1\nb,2\n"
WEIRD_BODY = b"weird,data\n"


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        path = self.path.split("?")[0]
        if path == "/report.pdf":
            self._ok(PDF_BODY, "application/pdf", 'attachment; filename="annual report.pdf"')
        elif path == "/plain.txt":
            self._ok(b"plain text", "text/plain", None)
        elif path == "/files/data.csv":
            self._ok(CSV_BODY, "text/csv", None)
        elif path == "/files/weird.csv":
            self._ok(WEIRD_BODY, "text/csv", 'attachment; filename="my file?.csv"')
        elif path == "/redirect-in":
            self.send_response(302)
            self.send_header("Location", "/report.pdf")
            self.end_headers()
        elif path == "/redirect-out":
            self.send_response(302)
            self.send_header("Location", "https://evil.example.com/report.pdf")
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def _ok(self, body: bytes, content_type: str, content_disposition: str | None) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        if content_disposition:
            self.send_header("Content-Disposition", content_disposition)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass


@pytest.fixture
def http_server():
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()
    thread.join()


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    return tmp_path


class TestDownloadPolicy:
    def test_validate_domain_allows_whitelist(self):
        validate_domain("https://example.com/report.pdf", ["example.com"])
        validate_domain("https://www.example.com/report.pdf", ["example.com"])

    def test_validate_domain_rejects(self):
        with pytest.raises(DownloadPolicyError):
            validate_domain("https://other.com/x", ["example.com"])
        with pytest.raises(DownloadPolicyError):
            validate_domain("https://example.com/x", [])
        with pytest.raises(DownloadPolicyError):
            validate_domain("https://example.com/x", None)

    def test_is_allowed_type(self):
        assert is_allowed_type("application/pdf", "pdf")
        assert is_allowed_type(None, "pdf")
        assert is_allowed_type("text/csv", "csv")
        assert is_allowed_type("application/octet-stream", "zip")
        assert not is_allowed_type("text/html", "html")
        assert is_allowed_type("text/plain", "pdf")
        assert not is_allowed_type(None, "txt")


class TestDownloadManifest:
    def test_append_load_roundtrip(self, tmp_path: Path):
        path = download_manifest.manifest_path(tmp_path)
        download_manifest.append(
            DownloadManifestEntry(
                source_url="https://example.com/r.pdf",
                filename="r.pdf",
                size=5,
                sha256="abc",
            ),
            path,
        )
        entries = download_manifest.load(path)
        assert len(entries) == 1
        entry = entries[0]
        assert entry.source_url == "https://example.com/r.pdf"
        assert entry.filename == "r.pdf"
        assert entry.size == 5
        assert entry.sha256 == "abc"
        assert entry.downloaded_at

    def test_load_missing_and_corrupt(self, tmp_path: Path):
        path = download_manifest.manifest_path(tmp_path)
        assert download_manifest.load(path) == []
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("not json")
        assert download_manifest.load(path) == []

    def test_append_accumulates(self, tmp_path: Path):
        path = download_manifest.manifest_path(tmp_path)
        for i in range(3):
            download_manifest.append(
                DownloadManifestEntry(
                    source_url=f"u{i}",
                    filename=f"f{i}.pdf",
                    size=i,
                    sha256="s",
                ),
                path,
            )
        assert len(download_manifest.load(path)) == 3


class TestDownloadService:
    @pytest.mark.asyncio
    async def test_whitelist_rejects_other_domain(self, http_server, workspace: Path):
        result = await download_file(http_server + "/report.pdf", ["example.com"], workspace)
        assert result.success is False
        assert "not in the allowed domains" in (result.error or "")

    @pytest.mark.asyncio
    async def test_content_type_rejected(self, http_server, workspace: Path):
        result = await download_file(http_server + "/plain.txt", ["127.0.0.1"], workspace)
        assert result.success is False
        assert "content type" in (result.error or "")

    @pytest.mark.asyncio
    async def test_download_success_size_and_sha(self, http_server, workspace: Path):
        result = await download_file(http_server + "/report.pdf", ["127.0.0.1"], workspace)
        assert result.success
        assert result.filename == "annual report.pdf"
        assert result.size == len(PDF_BODY)
        assert result.sha256 == hashlib.sha256(PDF_BODY).hexdigest()
        out = workspace / ".scriptordb" / "outputs" / "annual report.pdf"
        assert out.exists()
        assert out.read_bytes() == PDF_BODY

    @pytest.mark.asyncio
    async def test_filename_from_url_path(self, http_server, workspace: Path):
        result = await download_file(http_server + "/files/data.csv", ["127.0.0.1"], workspace)
        assert result.success
        assert result.filename == "data.csv"

    @pytest.mark.asyncio
    async def test_filename_sanitized(self, http_server, workspace: Path):
        result = await download_file(http_server + "/files/weird.csv", ["127.0.0.1"], workspace)
        assert result.success
        assert result.filename == "my file_.csv"

    @pytest.mark.asyncio
    async def test_dedupe_unique_name(self, http_server, workspace: Path):
        first = await download_file(http_server + "/report.pdf", ["127.0.0.1"], workspace)
        second = await download_file(http_server + "/report.pdf", ["127.0.0.1"], workspace)
        assert first.filename == "annual report.pdf"
        assert second.filename == "annual report_1.pdf"
        assert first.sha256 == second.sha256

    @pytest.mark.asyncio
    async def test_redirect_inside_whitelist(self, http_server, workspace: Path):
        result = await download_file(http_server + "/redirect-in", ["127.0.0.1"], workspace)
        assert result.success
        assert result.filename == "annual report.pdf"

    @pytest.mark.asyncio
    async def test_redirect_out_of_whitelist_rejected(self, http_server, workspace: Path):
        result = await download_file(http_server + "/redirect-out", ["127.0.0.1"], workspace)
        assert result.success is False
        assert "not in the allowed domains" in (result.error or "")

    @pytest.mark.asyncio
    async def test_max_size_rejected(self, http_server, workspace: Path):
        result = await download_file(
            http_server + "/report.pdf",
            ["127.0.0.1"],
            workspace,
            max_size_mb=0,
        )
        assert result.success is False
        assert "size" in (result.error or "")

    def test_parse_domains(self):
        assert _parse_domains("a.com, b.com") == ["a.com", "b.com"]
        assert _parse_domains("") is None
        assert _parse_domains("  ") is None
