from __future__ import annotations

"""PDF tool cluster: tool entry (`read_pdf`), crawl4ai-backed extraction service.

Implementation lives in `tools.pdf.tools` and `tools.pdf.service`. Importing
this package registers the `read_pdf` tool.
"""

from tools.pdf.service import MAX_TEXT_LENGTH, extract_pdf  # noqa: F401
from tools.pdf.tools import read_pdf  # noqa: F401

__all__ = ["MAX_TEXT_LENGTH", "extract_pdf", "read_pdf"]
