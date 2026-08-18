from __future__ import annotations

"""Backwards-compatible facade for the agent run pipeline.

Implementation lives in `server/runner/`:
- `lifecycle.py`      — `run_agent_stream()` orchestration (retry wrapper, queue loop, cleanup)
- `translator.py`     — pydantic-ai event → application dict event translation (injectable)
- `events.py`         — pure event builders + tool-content normalization
- `finalize.py`       — result post-processing (deferred requests, new_messages, terminal events)
- `takeover_hook.py`  — browser human-takeover cross-cutting check (injectable)
- `errors.py`         — rate-limit detection + connection-retry exception classification
"""

from runtime.runner.lifecycle import run_agent_stream

__all__ = ["run_agent_stream"]
