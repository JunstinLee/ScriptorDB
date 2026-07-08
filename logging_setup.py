from __future__ import annotations

import logging
import os
import sys


_LOGGER_NAME = "scriptordb"
_CONFIGURED = False


def configure_logging() -> None:
    """初始化全局日志配置。多次调用安全。

    默认输出到 stderr，级别由环境变量 ``SCRIPTORDB_LOG_LEVEL`` 控制（默认 ``INFO``）。
    调用方在测试中可以通过 ``unconfigure`` 或直接修改 handler 级别来调整。
    """
    global _CONFIGURED
    if _CONFIGURED:
        return
    level_name = os.environ.get("SCRIPTORDB_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    handler = logging.StreamHandler(stream=sys.stderr)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
    )
    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(level)
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.propagate = False
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """获取以 ``scriptordb`` 为根的子 logger。首次调用会自动初始化。"""
    configure_logging()
    return logging.getLogger(f"{_LOGGER_NAME}.{name}")


def unconfigure() -> None:
    """移除已注册的 handler（仅用于测试隔离）。"""
    global _CONFIGURED
    logger = logging.getLogger(_LOGGER_NAME)
    logger.handlers.clear()
    _CONFIGURED = False
