from __future__ import annotations

from urllib.parse import urljoin

from bs4 import BeautifulSoup
from markdownify import MarkdownConverter

_STRIP_TAGS = ("script", "style", "noscript", "template", "head", "title")
_SKIP_HREF_PREFIXES = ("javascript:", "mailto:", "tel:", "data:", "about:")


class _Converter(MarkdownConverter):
    """Markdownify variant tuned to stay close to the previous crawl output."""

    def convert_a(self, el, text, parent_tags):  # noqa: N802 - markdownify API
        href = el.get("href") or ""
        if href.strip().lower().startswith(_SKIP_HREF_PREFIXES):
            return text
        return super().convert_a(el, text, parent_tags)


def _resolve_urls(soup: BeautifulSoup, base_url: str) -> None:
    base_tag = soup.find("base", href=True)
    resolved_base = urljoin(base_url, base_tag["href"]) if base_tag else base_url
    if not resolved_base:
        return
    for anchor in soup.find_all("a", href=True):
        anchor["href"] = urljoin(resolved_base, anchor["href"].strip())
    for image in soup.find_all("img", src=True):
        image["src"] = urljoin(resolved_base, image["src"].strip())


def clean_soup(html: str, base_url: str = "") -> BeautifulSoup:
    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup(_STRIP_TAGS):
        tag.decompose()
    _resolve_urls(soup, base_url)
    return soup


def html_to_markdown(html: str, base_url: str = "") -> str:
    """Convert an HTML document into markdown (links resolved against base_url)."""
    if not html:
        return ""
    converter = _Converter(heading_style="ATX", bullets="-")
    return converter.convert_soup(clean_soup(html, base_url)).strip()


__all__ = ["clean_soup", "html_to_markdown"]
