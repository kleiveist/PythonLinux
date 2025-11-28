#!/usr/bin/env python3
"""
Steuerskript für PythonLinux.

Aufrufe:
  - Ohne Optionen: ruft Inst/PyInstall.py mit allen weiteren Argumenten auf.
  - --bash:        ruft Inst/PyInstall.sh auf.
  - --uninstall:   ruft Inst/PyUnistall.py auf.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import List, Sequence

USE_ICONS = os.environ.get("PLAIN_LOGS") is None
ICON_INFO = "ℹ️" if USE_ICONS else "[INFO]"
ICON_WARN = "⚠️" if USE_ICONS else "[WARN]"
ICON_ERR = "❌" if USE_ICONS else "[ERROR]"
ICON_ROOT = "🔒" if USE_ICONS else "[ROOT]"


def log(msg: str) -> None:
    print(f"{ICON_INFO} {msg}")


def warn(msg: str) -> None:
    print(f"{ICON_WARN} {msg}", file=sys.stderr)


def err(msg: str) -> None:
    print(f"{ICON_ERR} {msg}", file=sys.stderr)


def parse_mode(argv: Sequence[str]) -> tuple[str, List[str]]:
    mode = "install"
    rest: List[str] = []
    for arg in argv:
        if arg == "--bash":
            mode = "bash"
        elif arg == "--uninstall":
            mode = "uninstall"
        else:
            rest.append(arg)
    return mode, rest


def run(cmd: Sequence[str], cwd: Path, env_overrides: dict[str, str] | None = None) -> int:
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)
    log("Starte: " + " ".join(cmd))
    try:
        proc = subprocess.run(cmd, cwd=str(cwd), env=env)
    except FileNotFoundError:
        err(f"Kommando nicht gefunden: {cmd[0]}")
        return 1
    return proc.returncode


def main(argv: Sequence[str]) -> int:
    script_dir = Path(__file__).resolve().parent
    inst_dir = script_dir / "Inst"

    py_install = inst_dir / "PyInstall.py"
    sh_install = inst_dir / "PyInstall.sh"
    py_uninstall = inst_dir / "PyUnistall.py"

    mode, rest = parse_mode(argv)

    if mode == "bash":
        if not sh_install.exists():
            err(f"PyInstall.sh nicht gefunden unter {sh_install}")
            return 1
        env_overrides = {"START_DIR": str(script_dir)}
        return run(["bash", str(sh_install), *rest], cwd=script_dir, env_overrides=env_overrides)

    if mode == "uninstall":
        if not py_uninstall.exists():
            err(f"PyUnistall.py nicht gefunden unter {py_uninstall}")
            return 1
        return run([sys.executable, str(py_uninstall), *rest], cwd=script_dir)

    # Default: Install
    if not py_install.exists():
        err(f"PyInstall.py nicht gefunden unter {py_install}")
        return 1
    env_overrides = {"START_DIR": str(script_dir)}
    return run([sys.executable, str(py_install), *rest], cwd=script_dir, env_overrides=env_overrides)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
