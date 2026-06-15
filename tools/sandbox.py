from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SandboxResult:
    stdout: str
    stderr: str
    exit_code: int
    elapsed_ms: float


def sandbox_execute(
    code: str,
    db_url: str = "",
    timeout: int = 30,
    max_output_kb: int = 10,
    allowed_imports: list[str] | None = None,
) -> SandboxResult:
    if allowed_imports is None:
        allowed_imports = ["pandas", "matplotlib", "openpyxl", "csv", "json", "math", "statistics", "sqlite3"]

    work_dir = Path(tempfile.gettempdir()) / "scriptordb_sandbox" / uuid.uuid4().hex[:12]
    work_dir.mkdir(parents=True, exist_ok=True)

    script_path = work_dir / "_script.py"
    max_bytes = max_output_kb * 1024

    sandbox_code = f'''
import sys
import builtins

_original_import = builtins.__import__
_allowed = {allowed_imports!r}

def _sandbox_import(name, *args, **kwargs):
    top = name.split(".")[0]
    if top not in _allowed and top not in sys.stdlib_module_names:
        raise ImportError(f"Module '{{name}}' is not allowed in sandbox")
    return _original_import(name, *args, **kwargs)

builtins.__import__ = _sandbox_import

try:
{chr(10).join("    " + line for line in code.split(chr(10)))}
except Exception as e:
    print(f"__SANDBOX_ERROR__: {{type(e).__name__}}: {{e}}", file=sys.stderr)
'''

    script_path.write_text(sandbox_code, encoding="utf-8")

    env: dict[str, str] = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(work_dir),
        "TMPDIR": str(work_dir),
        "SCRIPTORDB_DB_URL": db_url,
        "PYTHONUNBUFFERED": "1",
    }
    for key in ("VIRTUAL_ENV", "PYTHONPATH", "PYTHONHOME"):
        if key in os.environ:
            env[key] = os.environ[key]

    start = time.perf_counter()
    try:
        proc = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(work_dir),
            env=env,
        )
    except subprocess.TimeoutExpired as e:
        elapsed_ms = (time.perf_counter() - start) * 1000
        return SandboxResult(
            stdout=e.stdout.decode("utf-8", errors="replace") if e.stdout else "",
            stderr=e.stderr.decode("utf-8", errors="replace") if e.stderr else "",
            exit_code=-1,
            elapsed_ms=elapsed_ms,
        )
    finally:
        try:
            import shutil
            shutil.rmtree(work_dir, ignore_errors=True)
        except Exception:
            pass

    elapsed_ms = (time.perf_counter() - start) * 1000

    stdout = proc.stdout or ""
    stderr = proc.stderr or ""

    if len(stdout) > max_bytes:
        stdout = stdout[:max_bytes] + "\n... [output truncated]"
    if len(stderr) > max_bytes:
        stderr = stderr[:max_bytes] + "\n... [output truncated]"

    return SandboxResult(
        stdout=stdout,
        stderr=stderr,
        exit_code=proc.returncode,
        elapsed_ms=elapsed_ms,
    )
