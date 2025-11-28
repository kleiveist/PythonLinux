#!/usr/bin/env python3
"""
Entfernt Wrapper aus /usr/local/bin basierend auf dem Install-Log
und löscht anschließend den Installationsordner ~/Dokumente/Python.
"""

from __future__ import annotations

import os
import pwd
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Sequence

USE_ICONS = os.environ.get("PLAIN_LOGS") is None
ICON_INFO = "ℹ️" if USE_ICONS else "[INFO]"
ICON_WARN = "⚠️" if USE_ICONS else "[WARN]"
ICON_ERR = "❌" if USE_ICONS else "[ERROR]"
ICON_SUMMARY = "📊" if USE_ICONS else "[SUM]"
ICON_PY = "📂" if USE_ICONS else "[PY]"
ICON_VENV = "🐍" if USE_ICONS else "[VENV]"
ICON_WRAP = "🧩" if USE_ICONS else "[WRAP]"
ICON_MODE = "⚙️" if USE_ICONS else "[MODE]"
ICON_ROOT = "🔒" if USE_ICONS else "[ROOT]"


def log(msg: str) -> None:
    print(f"{ICON_INFO} {msg}")


def warn(msg: str) -> None:
    print(f"{ICON_WARN} {msg}", file=sys.stderr)


def err(msg: str) -> None:
    print(f"{ICON_ERR} {msg}", file=sys.stderr)


def running_as_root() -> bool:
    return hasattr(os, "geteuid") and os.geteuid() == 0


def get_home_base() -> Path:
    sudo_user = os.environ.get("SUDO_USER")
    if sudo_user:
        try:
            return Path(pwd.getpwnam(sudo_user).pw_dir)
        except KeyError:
            return Path.home()
    return Path.home()


def read_wrapper_names(log_file: Path) -> List[str]:
    if not log_file.is_file():
        warn(f"Log-Datei nicht gefunden: {log_file}")
        return []
    try:
        lines = log_file.read_text().splitlines()
    except OSError as exc:
        warn(f"Log-Datei kann nicht gelesen werden ({log_file}): {exc}")
        return []

    names: List[str] = []
    for line in lines:
        if "->" not in line:
            continue
        left = line.split("->", 1)[0].strip()
        if left:
            names.append(left)
    if not names:
        warn("Keine Wrapper-Einträge im Log gefunden.")
    return names


def remove_file(path: Path) -> None:
    if not path.exists():
        log(f"Wrapper nicht vorhanden: {path}")
        return
    try:
        path.unlink()
        log(f"Wrapper entfernt: {path}")
        return
    except PermissionError:
        pass
    except OSError as exc:
        warn(f"Wrapper konnte nicht entfernt werden ({path}): {exc}")
        return

    # Mit sudo erneut versuchen
    if running_as_root():
        warn(f"{ICON_ROOT} Keine Rechte zum Löschen von {path} (auch als root).")
        return
    cmd = ["sudo", "rm", "-f", str(path)]
    log("Fehlende Berechtigung – versuche mit sudo:")
    log("  " + " ".join(cmd))
    try:
        subprocess.run(cmd, check=True)
        log(f"Wrapper entfernt (sudo): {path}")
    except subprocess.CalledProcessError as exc:
        err(f"sudo rm fehlgeschlagen ({path}): {exc}")
    except FileNotFoundError:
        err("sudo nicht gefunden – bitte manuell löschen.")


def remove_wrappers(wrapper_names: Sequence[str], wrapper_dir: Path) -> None:
    if not wrapper_names:
        log("Keine Wrapper aus dem Log zu entfernen.")
        return
    for name in wrapper_names:
        target = wrapper_dir / name
        remove_file(target)


def safe_remove_tree(path: Path) -> None:
    try:
        resolved = path.resolve()
    except OSError:
        resolved = path

    protected = {Path("/"), Path("/home"), Path("/root")}
    if resolved in protected or resolved == Path():
        err(f"Abbruch: Gefährlicher Löschpfad '{resolved}'.")
        return

    if not path.exists():
        log(f"Zielordner existiert nicht: {path}")
        return

    try:
        shutil.rmtree(path)
        log(f"Ordner entfernt: {path}")
        return
    except PermissionError:
        pass
    except OSError as exc:
        warn(f"Ordner konnte nicht entfernt werden ({path}): {exc}")
        return

    if running_as_root():
        warn(f"{ICON_ROOT} Keine Rechte zum Löschen von {path} (auch als root).")
        return
    cmd = ["sudo", "rm", "-rf", str(path)]
    log("Fehlende Berechtigung – versuche mit sudo:")
    log("  " + " ".join(cmd))
    try:
        subprocess.run(cmd, check=True)
        log(f"Ordner entfernt (sudo): {path}")
    except subprocess.CalledProcessError as exc:
        err(f"sudo rm -rf fehlgeschlagen ({path}): {exc}")
    except FileNotFoundError:
        err("sudo nicht gefunden – bitte Ordner manuell löschen.")


def main() -> int:
    base_home = get_home_base()
    dest_base = base_home / "Dokumente/Python"
    log_dir = dest_base / ".log"

    # Sowohl logs.txt (aktueller Name) als auch log.txt (Fallback) prüfen
    log_file = log_dir / "logs.txt"
    if not log_file.exists():
        alt_log = log_dir / "log.txt"
        log_file = alt_log if alt_log.exists() else log_file

    wrapper_dir = Path("/usr/local/bin")

    log(f"Zielbasis: {dest_base}")
    log(f"Wrapper-Verzeichnis: {wrapper_dir}")
    log(f"Log-Datei: {log_file}")

    wrappers = read_wrapper_names(log_file)
    remove_wrappers(wrappers, wrapper_dir)

    # Installationsordner löschen
    safe_remove_tree(dest_base)
    log("Fertig.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
