from __future__ import annotations

"""PDF cluster: pypdf-backed extraction service and the internal read branch.

Implementation lives in `tools.pdf.tools` (`_read_pdf`, called by the unified
`read_file`) and `tools.pdf.service` (`extract_pdf`).
"""

from tools.pdf.service import MAX_TEXT_LENGTH, extract_pdf  # noqa: F401

__all__ = ["MAX_TEXT_LENGTH", "extract_pdf"]
