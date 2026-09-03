from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from pathlib import Path


_LOGGER_NAME = "scriptordb"
_CONFIGURED = False


class _SuppressUnhandledRunEvent(logging.Filter):
    """PartDeltaEvent 等未知事件逐 chunk 刷屏——仅拦控制台,文件日志保留。"""

    def filter(self, record: logging.LogRecord) -> bool:
        if record.name == "scriptordb.agent_runner.translator":
            return not record.getMessage().startswith("unhandled run event type")
        return True


def configure_logging() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    level_name = os.environ.get("SCRIPTORDB_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )

    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(level)
    logger.handlers.clear()
    logger.propagate = False

    stderr_handler = logging.StreamHandler(stream=sys.stderr)
    stderr_handler.setFormatter(formatter)
    stderr_handler.addFilter(_SuppressUnhandledRunEvent())
    logger.addHandler(stderr_handler)

    logs_dir = Path(os.environ.get("SCRIPTORDB_LOG_DIR", "logs"))
    logs_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = logs_dir / f"run_{timestamp}.log"
    file_handler = logging.FileHandler(str(log_path))
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(f"{_LOGGER_NAME}.{name}")


def unconfigure() -> None:
    global _CONFIGURED
    logger = logging.getLogger(_LOGGER_NAME)
    logger.handlers.clear()
    _CONFIGURED = False
