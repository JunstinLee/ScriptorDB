from __future__ import annotations

from schemas.crawl_models import CrawlResult


async def crawl_webpage(ctx, url: str) -> str:
    from services.crawl_service import crawl_url

    result: CrawlResult = await crawl_url(url)
    if result.success:
        return f"# {result.title}\n\n{result.markdown}"
    return f"抓取失败: {result.error}"
