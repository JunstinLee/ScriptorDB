from __future__ import annotations

from pydantic_ai.exceptions import FallbackExceptionGroup, ModelHTTPError

# 连接类异常：模型 API 的 SSE 流可能被对端中断（如 incomplete chunked read），
# 这类瞬时错误可通过重试恢复。aiohttp 是传递依赖，导入失败时退化为不重试。
try:
    from aiohttp import ClientError as _AiohttpClientError

    CONNECTION_RETRY_EXCEPTIONS: tuple[type[BaseException], ...] = (_AiohttpClientError,)
except ImportError:  # pragma: no cover
    CONNECTION_RETRY_EXCEPTIONS = ()

MAX_CONNECTION_RETRIES = 2


def find_rate_limit(exc: BaseException) -> tuple[int, str] | None:
    """Walk the exception chain (and exception groups) looking for HTTP 429.

    Returns (status_code, model_name) when the failure is a model rate limit,
    None otherwise. pydantic-ai may surface ModelHTTPError directly, wrapped in
    UnexpectedModelBehavior, or inside a FallbackExceptionGroup, so the chain is
    traversed defensively.
    """
    seen: set[int] = set()
    pending: list[BaseException] = [exc]
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        if isinstance(current, ModelHTTPError) and current.status_code == 429:
            return (current.status_code, current.model_name)
        if isinstance(current, FallbackExceptionGroup):
            pending.extend(current.exceptions)
        if current.__cause__ is not None:
            pending.append(current.__cause__)
        if current.__context__ is not None:
            pending.append(current.__context__)
    return None
