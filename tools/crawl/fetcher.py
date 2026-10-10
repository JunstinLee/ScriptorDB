from __future__ import annotations

import hashlib
import json
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from core.logging_setup import get_logger
from tools.crawl.rate_limit import RateLimiter
from tools.policy.crawl_policy import is_binary_content_type

logger = get_logger("crawl.fetcher")

RAW_PREFIX = "raw://"

CACHE_TTL_SECONDS = 3600
MAX_CACHEABLE_HTML_CHARS = 5_000_000
DEFAULT_TIMEOUT_MS = 30_000
NETWORK_IDLE_TIMEOUT_MS = 15_000

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
LAUNCH_ARGS = ["--disable-blink-features=AutomationControlled"]

_rate_limiter = RateLimiter()


@dataclass
class FetchResult:
    url: str
    final_url: str = ""
    status_code: int | None = None
    content_type: str | None = None
    title: str | None = None
    html: str = ""
    headers: dict = field(default_factory=dict)
    from_cache: bool = False
    error: str | None = None


def _normalize_content_type(value: str | None) -> str | None:
    if not value:
        return None
    return str(value).split(";", 1)[0].strip().lower()


def _header_content_type(headers: dict | None) -> str | None:
    if not headers:
        return None
    for key, value in headers.items():
        if str(key).lower() == "content-type":
            return _normalize_content_type(value)
    return None


def title_from_html(html: str) -> str | None:
    from bs4 import BeautifulSoup

    if not html:
        return None
    soup = BeautifulSoup(html, "html.parser")
    node = soup.find("title")
    if node is None:
        return None
    text = node.get_text(strip=True)
    return text or None


def _cache_root() -> Path:
    from config.workspace_paths import GLOBAL_CONFIG_DIR

    try:
        from config.settings import settings

        workspace_path = getattr(settings, "workspace_path", None)
    except Exception:  # pragma: no cover - import-time bootstrap issues
        workspace_path = None

    if workspace_path:
        return Path(workspace_path) / ".scriptordb" / "cache" / "crawl"
    return GLOBAL_CONFIG_DIR / "cache" / "crawl"


def _cache_file(url: str, wait_for_selector: str | None) -> Path:
    key = hashlib.sha256(f"{url}\x00{wait_for_selector or ''}".encode()).hexdigest()
    return _cache_root() / f"{key}.json"


def _read_cache(url: str, wait_for_selector: str | None) -> FetchResult | None:
    path = _cache_file(url, wait_for_selector)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    fetched_at = payload.get("fetched_at")
    if not isinstance(fetched_at, (int, float)) or time.time() - fetched_at > CACHE_TTL_SECONDS:
        return None
    html = payload.get("html")
    if not isinstance(html, str):
        return None
    logger.info("crawl cache hit url=%s", url)
    return FetchResult(
        url=payload.get("url") or url,
        final_url=payload.get("final_url") or url,
        status_code=payload.get("status_code"),
        content_type=payload.get("content_type"),
        title=payload.get("title"),
        html=html,
        headers=payload.get("headers") or {},
        from_cache=True,
    )


def _write_cache(url: str, wait_for_selector: str | None, result: FetchResult) -> None:
    if result.error or not result.html or len(result.html) > MAX_CACHEABLE_HTML_CHARS:
        return
    if is_binary_content_type(result.content_type):
        return
    path = _cache_file(url, wait_for_selector)
    payload = {
        "url": result.url,
        "final_url": result.final_url,
        "status_code": result.status_code,
        "content_type": result.content_type,
        "title": result.title,
        "html": result.html,
        "headers": result.headers,
        "fetched_at": time.time(),
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    except OSError as e:
        logger.warning("crawl cache write failed url=%s: %s", url, e)


async def _navigate(page, url: str, wait_for_selector: str | None, timeout_ms: int):
    response = await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
    if wait_for_selector:
        await page.wait_for_selector(wait_for_selector, timeout=timeout_ms)
    else:
        try:
            await page.wait_for_load_state(
                "networkidle", timeout=min(timeout_ms, NETWORK_IDLE_TIMEOUT_MS)
            )
        except Exception:
            logger.info("crawl networkidle wait timed out url=%s — continuing", url)
    return response


async def _click_next(page, selector: str, settle_ms: int) -> bool:
    from playwright.async_api import Error as PlaywrightError

    if not selector:
        return False
    locator = page.locator(selector).first
    try:
        if await locator.count() == 0 or not await locator.is_enabled():
            return False
        await locator.click(timeout=5_000)
    except PlaywrightError as e:
        logger.info("crawl pagination click failed selector=%s: %s", selector, e)
        return False
    await page.wait_for_timeout(settle_ms)
    return True


async def _snapshot(page, url: str, response) -> FetchResult:
    status_code = response.status if response is not None else None
    headers = {}
    if response is not None:
        try:
            headers = await response.all_headers()
        except Exception:  # pragma: no cover - response already consumed
            headers = {}
    content_type = _header_content_type(headers)
    if content_type is None and response is None:
        content_type = "text/html"
    html = await page.content()
    title = await page.title() or title_from_html(html)
    return FetchResult(
        url=url,
        final_url=page.url or url,
        status_code=status_code,
        content_type=content_type,
        title=title,
        html=html,
        headers=headers,
    )


async def _probe_headers(url: str, context) -> FetchResult:
    """Header-only fallback for navigations Chromium refuses (e.g. downloads)."""
    try:
        response = await context.request.get(url, timeout=DEFAULT_TIMEOUT_MS)
    except Exception as e:
        return FetchResult(url=url, final_url=url, error=str(e))
    return FetchResult(
        url=url,
        final_url=url,
        status_code=response.status,
        content_type=_header_content_type(response.headers),
        headers=dict(response.headers),
    )


@asynccontextmanager
async def _browser_context(timeout_ms: int):
    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True, channel="chromium", args=LAUNCH_ARGS
        )
        try:
            context = await browser.new_context(
                user_agent=USER_AGENT,
                viewport={"width": 1280, "height": 900},
            )
            yield context
        finally:
            await browser.close()


async def fetch_pages(
    url: str,
    wait_for_selector: str | None = None,
    pagination_next_selector: str | None = None,
    max_pages: int = 1,
    page_settle_ms: int = 800,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
    use_cache: bool = True,
) -> list[FetchResult]:
    """Fetch one page, or several by repeatedly clicking a "next page" control."""
    if url.startswith(RAW_PREFIX):
        html = url[len(RAW_PREFIX):]
        return [FetchResult(
            url=url,
            final_url=url,
            status_code=200,
            content_type="text/html",
            title=title_from_html(html),
            html=html,
        )]

    paginated = bool(pagination_next_selector) and max_pages > 1
    cacheable = use_cache and not paginated
    if cacheable:
        cached = _read_cache(url, wait_for_selector)
        if cached is not None:
            return [cached]

    domain = urlparse(url).hostname or ""
    results: list[FetchResult] = []
    await _rate_limiter.acquire(domain)
    try:
        async with _browser_context(timeout_ms) as context:
            page = await context.new_page()
            try:
                response = await _navigate(page, url, wait_for_selector, timeout_ms)
            except Exception as e:
                logger.warning("crawl navigation failed url=%s: %s", url, e)
                probe = await _probe_headers(url, context)
                if probe.error:
                    return [FetchResult(url=url, final_url=url, error=str(e))]
                return [probe]

            first = await _snapshot(page, url, response)
            results.append(first)

            for _ in range(max(max_pages, 1) - 1):
                if not await _click_next(page, pagination_next_selector or "", page_settle_ms):
                    break
                nxt = await _snapshot(page, page.url or url, None)
                before = len(nxt.html)
                if before == 0:
                    break
                results.append(nxt)
    finally:
        _rate_limiter.release(domain)

    if cacheable and results:
        _write_cache(url, wait_for_selector, results[0])
    return results


__all__ = ["RAW_PREFIX", "FetchResult", "fetch_pages", "title_from_html"]
