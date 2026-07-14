from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class SandboxResult:
    stdout: str
    stderr: str
    exit_code: int
    elapsed_ms: float
    result_files: list[str] = field(default_factory=list)
    memory_killed: bool = False


_DEFAULT_LIMITS = {
    "cpu_seconds": 30,
    "max_file_size_bytes": 100 * 1024 * 1024,
    "max_open_files": 64,
    "max_processes": 16,
}

_DEFAULT_MAX_MEMORY_RSS_BYTES = 4 * 1024 * 1024 * 1024
_DEFAULT_MEMORY_POLL_INTERVAL = 0.8
_MEMORY_LIMIT_MARKER = "__SANDBOX_MEMORY_LIMIT__"
_VMS_DIAG_MARKER = "__SANDBOX_VMS_DIAG__"


def _set_resource_limits() -> None:
    if sys.platform == "win32":
        return

    import resource

    def _try(name: int, target: int) -> None:
        try:
            resource.setrlimit(name, (target, target))
        except (ValueError, OSError) as e:
            print(
                f"__SANDBOX_RLIMIT_SKIP__: {name}={target} -> {type(e).__name__}: {e}",
                file=sys.stderr,
            )

    _try(resource.RLIMIT_CPU, _DEFAULT_LIMITS["cpu_seconds"])
    _try(resource.RLIMIT_FSIZE, _DEFAULT_LIMITS["max_file_size_bytes"])
    _try(resource.RLIMIT_NOFILE, _DEFAULT_LIMITS["max_open_files"])
    _try(resource.RLIMIT_NPROC, _DEFAULT_LIMITS["max_processes"])


def _memory_monitor(
    proc: subprocess.Popen,
    max_rss_bytes: int,
    interval: float,
    state: dict,
) -> None:
    import psutil

    try:
        ps_proc = psutil.Process(proc.pid)
    except psutil.NoSuchProcess:
        return

    while proc.poll() is None:
        try:
            info = ps_proc.memory_info()
        except psutil.NoSuchProcess:
            return

        if info.rss > max_rss_bytes:
            state["memory_killed"] = True
            state["rss_at_kill"] = info.rss
            state["vms_at_kill"] = info.vms
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            return

        if info.vms > max_rss_bytes * 2:
            print(
                f"{_VMS_DIAG_MARKER} vms={info.vms} rss={info.rss}",
                file=sys.stderr,
            )

        time.sleep(interval)


def _prepare_result_dir(workspace_path: Path | None) -> Path:
    base = Path(workspace_path) if workspace_path else Path.cwd()
    date_dir = base / "result" / datetime.now().strftime("%y-%m-%d")
    date_dir.mkdir(parents=True, exist_ok=True)
    return date_dir


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem, suffix, parent = path.stem, path.suffix, path.parent
    counter = 1
    while True:
        candidate = parent / f"{stem}_{counter:03d}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def _copy_results(temp_dir: Path, result_dir: Path) -> list[str]:
    saved: list[str] = []
    for path in temp_dir.rglob("*"):
        if not path.is_file() or path.name == "_script.py":
            continue
        rel = path.relative_to(temp_dir)
        dest = _unique_path(result_dir / rel)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
        saved.append(str(dest))
    return saved


def sandbox_execute(
    code: str,
    db_url: str = "",
    timeout: int = 30,
    max_output_kb: int = 10,
    allowed_imports: list[str] | None = None,
    workspace_path: Path | str | None = None,
) -> SandboxResult:
    if allowed_imports is None:
        allowed_imports = ["pandas", "matplotlib", "openpyxl", "csv", "json", "math", "statistics", "sqlite3"]

    work_dir = Path(tempfile.mkdtemp(prefix="scriptordb_sandbox_"))
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
        "PATH": os.environ.get("PATH", r"C:\Windows\System32;C:\Windows" if sys.platform == "win32" else "/usr/bin:/bin"),
        "HOME": str(work_dir),
        "TMPDIR": str(work_dir),
        "SCRIPTORDB_DB_URL": db_url,
        "PYTHONUNBUFFERED": "1",
    }
    for key in ("VIRTUAL_ENV", "PYTHONPATH", "PYTHONHOME"):
        if key in os.environ:
            env[key] = os.environ[key]

    use_preexec = sys.platform != "win32"
    preexec_fn = _set_resource_limits if use_preexec else None

    monitor_state: dict = {"memory_killed": False, "rss_at_kill": 0, "vms_at_kill": 0}
    monitor_thread: threading.Thread | None = None

    start = time.perf_counter()
    try:
        proc = subprocess.Popen(
            [sys.executable, str(script_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(work_dir),
            env=env,
            preexec_fn=preexec_fn,
        )

        try:
            import psutil  # noqa: F401

            monitor_thread = threading.Thread(
                target=_memory_monitor,
                args=(proc, _DEFAULT_MAX_MEMORY_RSS_BYTES, _DEFAULT_MEMORY_POLL_INTERVAL, monitor_state),
                daemon=True,
            )
            monitor_thread.start()
        except ImportError:
            monitor_thread = None

        try:
            stdout, stderr = proc.communicate(timeout=timeout)
            timed_out = False
        except subprocess.TimeoutExpired as e:
            timed_out = True
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            stdout = e.stdout.decode("utf-8", errors="replace") if e.stdout else ""
            stderr = e.stderr.decode("utf-8", errors="replace") if e.stderr else ""

        if monitor_thread is not None:
            monitor_thread.join(timeout=1.0)

        elapsed_ms = (time.perf_counter() - start) * 1000

        if not timed_out:
            if len(stdout) > max_bytes:
                stdout = stdout[:max_bytes] + "\n... [output truncated]"
            if len(stderr) > max_bytes:
                stderr = stderr[:max_bytes] + "\n... [output truncated]"

        if timed_out:
            exit_code = -1
        else:
            exit_code = proc.returncode

        if monitor_state["memory_killed"]:
            stderr = (
                f"{_MEMORY_LIMIT_MARKER} RSS={monitor_state['rss_at_kill']} "
                f"exceeds limit {_DEFAULT_MAX_MEMORY_RSS_BYTES}\n"
            ) + stderr

        result_files: list[str] = []
        if not timed_out:
            try:
                result_dir = _prepare_result_dir(
                    Path(workspace_path) if workspace_path else None
                )
                result_files = _copy_results(work_dir, result_dir)
            except Exception as copy_err:
                stderr += f"\n__SANDBOX_RESULT_COPY_ERROR__: {type(copy_err).__name__}: {copy_err}"

        return SandboxResult(
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            elapsed_ms=elapsed_ms,
            result_files=result_files,
            memory_killed=monitor_state["memory_killed"],
        )
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
