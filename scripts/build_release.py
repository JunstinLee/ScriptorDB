from __future__ import annotations

"""Assemble the ScriptorDB release bundle and compress it.

Run from the repo root: `uv run python scripts/build_release.py`.

The bundle is a self-contained tree — no venv activation, no system Python:

    <name>/
      ScriptorDB.command        macOS/Linux launcher (double-clickable on macOS)
      ScriptorDB.cmd            Windows launcher
      desktop.py                pywebview entry point
      python/                   CPython interpreter + the pruned dependency set
      frontend/dist/            built React SPA (api/app.py mounts it at "/")
      browsers/                 Chromium for Playwright (core/playwright_browsers.py)
      api/ agents/ browser/ ... the application packages

Output: `dist/<name>.tar.gz`, where `<name>` is `scriptordb-<version>-<os>-<arch>`.
`.gitignore` already ignores `dist/`.

Platform layout differences are handled here: POSIX keeps the interpreter prefix as
`python/bin/python3.12` + `python/lib/python3.12/site-packages`, Windows uses
`python/python.exe` + `python/Lib/site-packages` (and `python/Scripts` for console
scripts). The interpreter dir is called `python`, not `runtime`, because the bundle also
ships the application package `runtime/` at its root.

Pruned from the environment: dev-only packages (reportlab, pytest and friends), the
interpreter's own pip, `tests/` directories shipped inside third-party packages, type
stubs (`*.pyi`), and a few build-time-only trees (`numpy/f2py`, `numpy/_pyinstaller`,
`matplotlib` sample data). Third-party `__pycache__` is kept on purpose: the dependency
tree is large and recompiling it at every launch is a worse trade than the bytes.
"""

import os
import platform
import shutil
import sys
import tarfile
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DIST = REPO / "dist"
IS_WINDOWS = os.name == "nt"

# Interpreter + dependencies. Named "python" rather than "runtime" because the bundle
# also ships the application package `runtime/` at its root.
RUNTIME_DIR = "python"

APP_PACKAGES = (
    "agents",
    "api",
    "browser",
    "cli",
    "config",
    "core",
    "database",
    "runtime",
    "schemas",
    "services",
    "tools",
)
APP_FILES = ("desktop.py", "main.py")

SP_DROP_PREFIXES = ("_pytest", "pytest", "reportlab", "pluggy", "iniconfig", "pip")
SP_DROP_PATHS = frozenset(
    {
        "sqlalchemy/testing",
        "matplotlib/testing",
        "matplotlib/mpl-data/sample_data",
        "numpy/f2py",
        "numpy/_pyinstaller",
    }
)

LAUNCHER_POSIX = """#!/bin/bash
# Launch ScriptorDB: FastAPI backend + bundled React SPA inside a native window.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$DIR/python/bin/__PYTHON__" "$DIR/desktop.py" "$@"
"""

# pythonw.exe, not python.exe: the desktop app must not keep a console window around.
LAUNCHER_WINDOWS = """@echo off
rem Launch ScriptorDB: FastAPI backend + bundled React SPA inside a native window.
setlocal
set "DIR=%~dp0"
start "" "%DIR%python\\pythonw.exe" "%DIR%desktop.py" %*
"""


def _human(size: int) -> str:
    return f"{size / 1048576:.1f} MB"


def _dir_size(path: Path) -> int:
    total = 0
    stack = [path]
    while stack:
        with os.scandir(stack.pop()) as entries:
            for entry in entries:
                if entry.is_symlink():
                    continue
                if entry.is_dir(follow_symlinks=False):
                    stack.append(Path(entry.path))
                else:
                    try:
                        total += entry.stat(follow_symlinks=False).st_size
                    except OSError:
                        pass
    return total


def _ignore_site_packages(root: Path):
    def ignore(dir_path: str, names: list[str]) -> list[str]:
        rel = Path(dir_path).relative_to(root)
        at_top = rel == Path(".")
        dropped = []
        for name in names:
            relname = (rel / name).as_posix()
            if at_top and any(
                name == prefix or name.startswith(f"{prefix}-")
                for prefix in SP_DROP_PREFIXES
            ):
                dropped.append(name)
            elif name == "tests" or name.endswith(".pyi") or relname in SP_DROP_PATHS:
                dropped.append(name)
        return dropped

    return ignore


def _ignore_app_code(dir_path: str, names: list[str]) -> list[str]:
    return [n for n in names if n in {"__pycache__", ".DS_Store"} or n.endswith(".pyc")]


def _site_packages(prefix: Path, python_name: str) -> Path:
    if IS_WINDOWS:
        return prefix / "Lib" / "site-packages"
    return prefix / "lib" / python_name / "site-packages"


def _venv_paths() -> tuple[Path, str]:
    """Return the interpreter prefix backing `.venv` and its `python<major>.<minor>` name."""
    venv = REPO / ".venv"
    cfg = venv / "pyvenv.cfg"
    if not cfg.is_file():
        raise SystemExit("error: .venv/pyvenv.cfg not found — run `uv sync` first")
    home = version = None
    for line in cfg.read_text().splitlines():
        key, _, value = line.partition("=")
        if key.strip() == "home":
            home = value.strip()
        elif key.strip() == "version_info":
            version = value.strip()
    if not home or not version:
        raise SystemExit("error: .venv/pyvenv.cfg is missing home/version_info")
    # POSIX points `home` at <prefix>/bin; Windows points it at <prefix> itself.
    home_dir = Path(home)
    prefix = home_dir if IS_WINDOWS else home_dir.parent
    major_minor = ".".join(version.split(".")[:2])
    return prefix, f"python{major_minor}"


def _build_tree(target: Path) -> None:
    prefix, python_name = _venv_paths()
    sp_src = _site_packages(REPO / ".venv", python_name)
    sp_dst = _site_packages(target / RUNTIME_DIR, python_name)
    scripts_dir = target / RUNTIME_DIR / ("Scripts" if IS_WINDOWS else "bin")

    print(f"[1/6] interpreter  {prefix}")
    shutil.copytree(prefix, target / RUNTIME_DIR, symlinks=True)

    print(f"[2/6] dependencies  {sp_src.relative_to(REPO)} (pruned)")
    shutil.copytree(
        sp_src,
        sp_dst,
        symlinks=True,
        dirs_exist_ok=True,
        ignore=_ignore_site_packages(sp_src),
    )
    for entry in sp_dst.glob("pip*"):
        if entry.is_dir():
            shutil.rmtree(entry)
        else:
            entry.unlink()
    for entry in scripts_dir.glob("pip*"):
        entry.unlink()

    print("[3/6] application packages")
    for name in APP_PACKAGES:
        shutil.copytree(
            REPO / name, target / name, symlinks=True, ignore=_ignore_app_code
        )
    for name in APP_FILES:
        shutil.copy2(REPO / name, target / name)

    print("[4/6] frontend/dist")
    shutil.copytree(REPO / "frontend" / "dist", target / "frontend" / "dist")

    print("[5/6] browsers/ (Chromium + ffmpeg)")
    shutil.copytree(REPO / "browsers", target / "browsers", symlinks=True)

    print("[6/6] launcher")
    if IS_WINDOWS:
        launcher = target / "ScriptorDB.cmd"
        launcher.write_text(LAUNCHER_WINDOWS)
    else:
        launcher = target / "ScriptorDB.command"
        launcher.write_text(LAUNCHER_POSIX.replace("__PYTHON__", python_name))
    launcher.chmod(0o755)


def _archive(target: Path, output: Path) -> None:
    with tarfile.open(output, "w:gz", compresslevel=6) as tar:
        tar.add(target, arcname=target.name)


def _artifact_name(version: str) -> str:
    os_name = {"darwin": "macos", "linux": "linux", "windows": "windows"}.get(
        platform.system().lower(), platform.system().lower()
    )
    machine = {
        "arm64": "arm64",
        "aarch64": "arm64",
        "AMD64": "x86_64",
        "x86_64": "x86_64",
    }.get(platform.machine(), platform.machine().lower())
    return f"scriptordb-{version}-{os_name}-{machine}"


def main() -> int:
    version = tomllib.loads((REPO / "pyproject.toml").read_text())["project"]["version"]
    name = _artifact_name(version)
    target = DIST / name
    output = DIST / f"{name}.tar.gz"

    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    DIST.mkdir(exist_ok=True)

    _build_tree(target)

    print()
    for part in sorted(target.iterdir()):
        size = _human(_dir_size(part)) if part.is_dir() else ""
        print(f"  {part.name:<16} {size}")
    print(f"  {'total':<16} {_human(_dir_size(target))}")

    print(f"\narchiving -> {output.relative_to(REPO)}")
    if output.exists():
        output.unlink()
    _archive(target, output)
    print(f"archive          {_human(output.stat().st_size)}")
    print(f"bundle           {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
