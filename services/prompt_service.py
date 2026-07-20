from __future__ import annotations

import traceback

from logging_setup import get_logger

logger = get_logger("services.prompt")


class CrawlError(Exception):
    pass


async def augment_prompt(
    prompt: str,
    attachments: list[str] | None = None,
    crawl_url: str | None = None,
) -> str:
    augmented = prompt
    if attachments:
        files_block = "\n".join(f"- {path}" for path in attachments)
        augmented = (
            f"The user has attached the following files:\n{files_block}\n\n"
            f"User request: {prompt}"
        )

    if crawl_url:
        from services.crawl_service import crawl_url as do_crawl

        try:
            result = await do_crawl(crawl_url)
            if result.success:
                crawl_block = (
                    f"\n\n[网页内容 - 来源: {result.url}]\n"
                    f"标题: {result.title or '(无标题)'}\n\n"
                    f"{result.markdown}\n"
                    f"[网页内容结束]"
                )
                augmented = f"{augmented}{crawl_block}"
            else:
                raise CrawlError(result.error or "网页抓取失败")
        except CrawlError:
            raise
        except Exception as e:
            logger.error(
                "Chat crawl failed for url %s: %s\n%s",
                crawl_url,
                e,
                traceback.format_exc(),
            )
            raise CrawlError(str(e))

    return augmented
