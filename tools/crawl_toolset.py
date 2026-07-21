from __future__ import annotations

from pydantic_ai import Tool
from pydantic_ai.toolsets.function import FunctionToolset

from tools.crawl_tools import crawl_webpage
from tools.registry import register_toolset

_crawl_tools = [
    Tool(
        crawl_webpage,
        takes_ctx=True,
        name="crawl_webpage",
        timeout=45,
        max_retries=1,
        requires_approval=False,
        include_return_schema=True,
    ),
]


@register_toolset("crawl")
def _create_crawl_toolset():
    return [
        FunctionToolset(
            instructions=(
                "Web crawling tools. Use crawl_webpage to fetch and extract "
                "content from web pages as Markdown text. "
                "Useful for reading documentation, articles, or any web content "
                "relevant to the user's request."
            ),
            tools=_crawl_tools,
        )
    ]
