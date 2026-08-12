from __future__ import annotations

"""Download tool cluster: tool entry (`download_file`), HTTP fetch service, manifest persistence.

Entry point for the download toolset; implementation lives in
`tools.download.tools`, `tools.download.service`, `tools.download.manifest`.
Importing this package registers the `download_file` tool.
"""

from tools.download import manifest  # noqa: F401
from tools.download.service import DownloadServiceError  # noqa: F401
from tools.download.tools import download_file  # noqa: F401

__all__ = ["download_file"]
