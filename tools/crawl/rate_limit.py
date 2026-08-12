from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass


@dataclass
class _DomainSlot:
    last_request_at: float = 0.0
    inflight: int = 0


class RateLimiter:
    """Per-domain concurrency/interval limiter to keep crawls polite."""

    def __init__(self, min_interval: float = 1.0, max_concurrency: int = 2) -> None:
        self._min_interval = min_interval
        self._max_concurrency = max_concurrency
        self._slots: dict[str, _DomainSlot] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    async def acquire(self, domain: str) -> None:
        lock = self._locks.setdefault(domain, asyncio.Lock())
        async with lock:
            slot = self._slots.setdefault(domain, _DomainSlot())
            while slot.inflight >= self._max_concurrency:
                await asyncio.sleep(0.05)
            wait = slot.last_request_at + self._min_interval - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            slot.inflight += 1
            slot.last_request_at = time.monotonic()

    def release(self, domain: str) -> None:
        slot = self._slots.get(domain)
        if slot:
            slot.inflight = max(0, slot.inflight - 1)


__all__ = ["RateLimiter"]
