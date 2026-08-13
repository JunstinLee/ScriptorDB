from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from browser import get_manager
from tests.conftest import _make_ctx
from tools.browser import browser_download
from tools.download import manifest as download_manifest

pytestmark = pytest.mark.usefixtures("cleanup_browser")

PDF_CONTENT = b"PDF fake content\n" * 50


class _FakeDownloadInfo:
    """Playwright expect_download 的下载信息容器（async context manager + awaitable value）。"""

    def __init__(self, download):
        self._download = download

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    @property
    def value(self):
        async def _get():
            return self._download

        return _get()


def _make_download(tmp_path: Path) -> tuple:
    """构造 fake download：save_as 落盘 PDF_CONTENT。返回 (page, download)。"""
    page = _FakePage()

    async def _save_as(path):
        Path(path).write_bytes(PDF_CONTENT)

    download = _SimpleNamespace(failure=lambda: None, suggested_filename="report.pdf", save_as=_save_as)
    page.expect_download.return_value = _FakeDownloadInfo(download)
    return page, download


def _workspace_ctx(tmp_path):
    ctx = _make_ctx()
    ctx.deps.workspace_path = tmp_path
    return ctx


async def test_missing_target_returns_usage():
    result = await browser_download(_make_ctx())
    assert "url 或 selector 之一" in result


async def test_browser_not_launched():
    result = await browser_download(_make_ctx(), url="https://example.com/file.pdf")
    assert "Browser not launched" in result


async def test_no_workspace(tmp_path):
    page, _ = _make_download(tmp_path)
    get_manager()._page = page
    result = await browser_download(_make_ctx(), url="https://example.com/file.pdf")
    assert "没有活动工作区" in result


async def test_download_success_by_url(tmp_path):
    page, _ = _make_download(tmp_path)
    get_manager()._page = page
    ctx = _workspace_ctx(tmp_path)

    result = await browser_download(ctx, url="https://example.com/report.pdf")

    assert "下载成功" in result
    saved = tmp_path / ".scriptordb" / "outputs" / "report.pdf"
    assert saved.read_bytes() == PDF_CONTENT
    page.goto.assert_awaited_once_with("https://example.com/report.pdf", wait_until="commit")
    page.click.assert_not_awaited()

    entries = download_manifest.load(download_manifest.manifest_path(tmp_path / ".scriptordb" / "outputs"))
    assert len(entries) == 1
    assert entries[0].source_url == "https://example.com/report.pdf"
    assert entries[0].filename == "report.pdf"
    assert entries[0].size == len(PDF_CONTENT)
    assert entries[0].sha256 == hashlib.sha256(PDF_CONTENT).hexdigest()


async def test_download_success_by_selector(tmp_path):
    page, _ = _make_download(tmp_path)
    page.url = "https://example.com/docs/page"
    get_manager()._page = page
    ctx = _workspace_ctx(tmp_path)

    result = await browser_download(ctx, selector="#download-btn")

    assert "下载成功" in result
    page.click.assert_awaited_once_with("#download-btn")
    page.goto.assert_not_awaited()
    entries = download_manifest.load(download_manifest.manifest_path(tmp_path / ".scriptordb" / "outputs"))
    assert entries[0].source_url == "https://example.com/docs/page"


async def test_download_succeeds_when_navigation_raises(tmp_path):
    """导航触发下载时 goto 可能抛错，但下载事件已发出——应继续保存而不是报失败。"""
    page, _ = _make_download(tmp_path)
    page.url = "https://example.com/docs/page"

    async def _boom(url, **kwargs):
        raise RuntimeError("navigation interrupted by download")

    page.goto = _boom
    get_manager()._page = page
    ctx = _workspace_ctx(tmp_path)

    result = await browser_download(ctx, url="https://example.com/report.pdf")

    assert "下载成功" in result
    assert (tmp_path / ".scriptordb" / "outputs" / "report.pdf").exists()


async def test_download_failure_reported(tmp_path):
    page = _FakePage()
    download = _SimpleNamespace(
        failure=lambda: "server aborted",
        suggested_filename="report.pdf",
        save_as=lambda path: None,
    )
    page.expect_download.return_value = _FakeDownloadInfo(download)
    get_manager()._page = page
    ctx = _workspace_ctx(tmp_path)

    result = await browser_download(ctx, url="https://example.com/report.pdf")

    assert "下载失败: server aborted" in result


async def test_download_exceeds_max_size_removed(tmp_path):
    page = _FakePage()

    async def _save_big(path):
        Path(path).write_bytes(b"x" * (1024 * 1024 + 10))  # > 1MB

    download = _SimpleNamespace(failure=lambda: None, suggested_filename="big.bin", save_as=_save_big)
    page.expect_download.return_value = _FakeDownloadInfo(download)
    get_manager()._page = page
    ctx = _workspace_ctx(tmp_path)

    result = await browser_download(ctx, url="https://example.com/big.bin", max_size_mb=1)

    assert "超过大小上限 1MB" in result
    assert not (tmp_path / ".scriptordb" / "outputs" / "big.bin").exists()


class _FakePage:
    """最小 fake page：goto/click 记录调用，expect_download 返回固定 download info。"""

    def __init__(self):
        self.url = "https://example.com/"
        self.goto = _AsyncFn()
        self.click = _AsyncFn()
        self.expect_download = _MagicWithReturn()


class _AsyncFn:
    """记录调用的可 await 函数。"""

    def __init__(self):
        self._calls = []
        self._not_awaited = True

    async def __call__(self, *args, **kwargs):
        self._calls.append((args, kwargs))
        self._not_awaited = False

    def assert_awaited_once_with(self, *args, **kwargs):
        assert not self._not_awaited, "expected to be awaited once, was never called"
        assert self._calls[-1] == (args, kwargs)

    def assert_not_awaited(self):
        assert self._not_awaited, "expected not to be called"


class _MagicWithReturn:
    """返回固定 return_value 的可调用对象（模拟 MagicMock 的调用语义）。"""

    def __init__(self):
        self.return_value = None

    def __call__(self, *args, **kwargs):
        return self.return_value


class _SimpleNamespace:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
