#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

# ──────────────────────────────────────────────────────────────────────────────
# Optionale Abhängigkeiten (werden automatisch ignoriert, wenn nicht vorhanden)
# ──────────────────────────────────────────────────────────────────────────────
# EXIF (für Foto-Aufnahmedatum)
try:
    from PIL import Image, ExifTags  # type: ignore
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False

# Bessere ANSI-Unterstützung auf Windows (optional)
COLORAMA_AVAILABLE = False
try:
    import colorama  # type: ignore
    colorama.just_fix_windows_console()
    COLORAMA_AVAILABLE = True
except Exception:
    pass

# ──────────────────────────────────────────────────────────────────────────────
# Grundkonfiguration
# ──────────────────────────────────────────────────────────────────────────────
CONFIG = {
    "folder_naming": "de_months",  # "international_day" | "years" | "de_months"
}

DEUTSCHE_MONATE = {
    1:  "01 – Januar",
    2:  "02 – Februar",
    3:  "03 – März",
    4:  "04 – April",
    5:  "05 – Mai",
    6:  "06 – Juni",
    7:  "07 – Juli",
    8:  "08 – August",
    9:  "09 – September",
    10: "10 – Oktober",
    11: "11 – November",
    12: "12 – Dezember",
}

# Häufige Bild-Endungen, bei denen EXIF-Datum sinnvoll ist (JPEG primär)
IMAGE_EXTS = {".jpg", ".jpeg", ".tif", ".tiff", ".png", ".webp", ".heic", ".heif"}

# ──────────────────────────────────────────────────────────────────────────────
# Konsolen-Styling (Farben & Icons) – ohne Pflichtpakete
# ──────────────────────────────────────────────────────────────────────────────
def _supports_color() -> bool:
    if not sys.stdout.isatty():
        return False
    if os.name == "nt":
        # Windows: colorama oder moderne Terminals (Windows Terminal/VSCode)
        return COLORAMA_AVAILABLE or bool(
            os.environ.get("WT_SESSION") or os.environ.get("TERM_PROGRAM") == "vscode"
        )
    # Unix: übliche TERM-Varianten
    return True

USE_COLOR = _supports_color()

class C:
    RESET = "\x1b[0m" if USE_COLOR else ""
    BOLD = "\x1b[1m" if USE_COLOR else ""
    DIM = "\x1b[2m" if USE_COLOR else ""
    FG_GREEN = "\x1b[32m" if USE_COLOR else ""
    FG_RED = "\x1b[31m" if USE_COLOR else ""
    FG_YELLOW = "\x1b[33m" if USE_COLOR else ""
    FG_BLUE = "\x1b[34m" if USE_COLOR else ""
    FG_CYAN = "\x1b[36m" if USE_COLOR else ""
    FG_MAGENTA = "\x1b[35m" if USE_COLOR else ""
    FG_GRAY = "\x1b[90m" if USE_COLOR else ""

def _use_emoji() -> bool:
    if os.environ.get("NO_EMOJI", "").lower() in {"1", "true", "yes"}:
        return False
    enc = (sys.stdout.encoding or "utf-8").lower()
    return "utf" in enc

if _use_emoji():
    ICON = {
        "info": "ℹ️",
        "ok": "✅",
        "warn": "⚠️",
        "err": "❌",
        "move": "📦",
        "dry": "📝",
        "scan": "🔎",
        "folder": "📁",
        "file": "📄",
        "arrow": "→",
        "gear": "⚙️",
        "sum": "🧾",
    }
else:
    ICON = {
        "info": "[i]",
        "ok": "[OK]",
        "warn": "[!]",
        "err": "[X]",
        "move": "[MOVE]",
        "dry": "[DRY]",
        "scan": "[SCAN]",
        "folder": "[DIR]",
        "file": "[FILE]",
        "arrow": "->",
        "gear": "[CFG]",
        "sum": "[SUM]",
    }

def log_info(msg: str) -> None:
    print(f"{C.FG_BLUE}{ICON['info']} {msg}{C.RESET}")

def log_ok(msg: str) -> None:
    print(f"{C.FG_GREEN}{ICON['ok']} {msg}{C.RESET}")

def log_warn(msg: str) -> None:
    print(f"{C.FG_YELLOW}{ICON['warn']} {msg}{C.RESET}")

def log_err(msg: str) -> None:
    print(f"{C.FG_RED}{ICON['err']} {msg}{C.RESET}")

def log_move(src: str, dst: str, dry: bool) -> None:
    tag = ICON["dry"] if dry else ICON["move"]
    color = C.FG_CYAN if dry else C.FG_GREEN
    print(f"{color}{tag} {src} {ICON['arrow']} {dst}{C.RESET}")

def print_header(title: str) -> None:
    line = "─" * max(8, min(80, (shutil.get_terminal_size().columns if sys.stdout.isatty() else 80) - 2))
    print(f"{C.FG_MAGENTA}┌{line}┐{C.RESET}")
    print(f"{C.FG_MAGENTA}│ {C.BOLD}{ICON['gear']} {title}{C.RESET}{C.FG_MAGENTA}{' ' * max(0, len(line) - len(title) - 2)}│{C.RESET}")
    print(f"{C.FG_MAGENTA}└{line}┘{C.RESET}")

def print_summary(total: int, processed: int, skipped: int, moved: int, errors: int) -> None:
    print(f"\n{C.BOLD}{ICON['sum']} Zusammenfassung{C.RESET}")
    print(f"  {ICON['scan']} gesamt gefunden : {total}")
    print(f"  {ICON['file']} verarbeitet     : {processed}  ({C.FG_GRAY}übersprungen: {skipped}{C.RESET})")
    print(f"  {ICON['move']} verschoben      : {C.FG_GREEN}{moved}{C.RESET}")
    if errors:
        print(f"  {ICON['err']} Fehler          : {C.FG_RED}{errors}{C.RESET}")
    else:
        print(f"  {ICON['ok']} Fehler          : 0")

# ──────────────────────────────────────────────────────────────────────────────
# Hilfsfunktionen
# ──────────────────────────────────────────────────────────────────────────────
def ask_yes_no(prompt: str) -> bool:
    while True:
        ans = input(f"{ICON['info']} {prompt}").strip().lower()
        if ans in {"y", "j", "yes"}:
            return True
        if ans in {"n", "no"}:
            return False
        log_warn("Bitte 'y' oder 'n' eingeben.")

def normalize_exts(exts: Iterable[str]) -> List[str]:
    out: List[str] = []
    for e in exts:
        e = e.strip()
        if not e:
            continue
        if not e.startswith("."):
            e = "." + e
        out.append(e.lower())
    # Deduplizieren, Reihenfolge behalten
    seen = set()
    uniq = []
    for e in out:
        if e not in seen:
            uniq.append(e)
            seen.add(e)
    return uniq

def get_exif_datetime(path: Path) -> Optional[datetime]:
    if not PIL_AVAILABLE:
        return None
    if path.suffix.lower() not in IMAGE_EXTS:
        return None
    try:
        from PIL import Image, ExifTags  # re-import for type-checkers
        with Image.open(path) as img:
            exif = getattr(img, "_getexif", lambda: None)()
            if not exif:
                d = img.info or {}
                for key in ("date:create", "date:modify"):
                    if key in d:
                        try:
                            return datetime.fromisoformat(str(d[key]))
                        except Exception:
                            pass
                return None
            tag_map = {ExifTags.TAGS.get(k, str(k)): v for k, v in exif.items()}
            for key in ("DateTimeOriginal", "DateTime", "DateTimeDigitized"):
                val = tag_map.get(key)
                if not val:
                    continue
                if isinstance(val, bytes):
                    try:
                        val = val.decode("utf-8", errors="ignore")
                    except Exception:
                        continue
                for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
                    try:
                        return datetime.strptime(str(val), fmt)
                    except Exception:
                        continue
    except Exception:
        return None
    return None

def get_filesystem_datetime(path: Path) -> datetime:
    st = path.stat()
    return datetime.fromtimestamp(st.st_mtime)

def determine_datetime(path: Path, prefer_exif: bool) -> datetime:
    if prefer_exif:
        dt = get_exif_datetime(path)
        if dt:
            return dt
    return get_filesystem_datetime(path)

def build_target_dir(root_dir: Path, dt: datetime, scheme: str, years_folder: bool) -> Path:
    if scheme == "international_day":
        ordner_name = dt.strftime("%y%m%d")
        if years_folder:
            return root_dir / str(dt.year) / ordner_name
        return root_dir / ordner_name
    elif scheme == "years":
        return root_dir / str(dt.year)
    else:  # de_months
        jahr = str(dt.year)
        monat = DEUTSCHE_MONATE[dt.month]
        return root_dir / jahr / monat

def unique_destination(dest: Path) -> Path:
    if not dest.exists():
        return dest
    stem = dest.stem
    suffix = dest.suffix
    i = 1
    while True:
        cand = dest.with_name(f"{stem} ({i}){suffix}")
        if not cand.exists():
            return cand
        i += 1

def snapshot_files(root_dir: Path) -> List[Path]:
    files: List[Path] = []
    for p in root_dir.rglob("*"):
        try:
            if p.is_file():
                files.append(p)
        except Exception:
            continue
    return files

def filter_by_ext(files: Iterable[Path], exts: List[str]) -> List[Path]:
    if not exts:
        return list(files)
    exts_l = set(e.lower() for e in exts)
    out = []
    for f in files:
        if f.suffix.lower() in exts_l:
            out.append(f)
    return out

# ──────────────────────────────────────────────────────────────────────────────
# Kernlogik
# ──────────────────────────────────────────────────────────────────────────────
def move_files(
    files: List[Path],
    root_dir: Path,
    scheme: str,
    years_folder: bool,
    prefer_exif: bool,
    dry_run: bool = False,
) -> Tuple[int, int]:
    moved = 0
    errors = 0
    for src in files:
        try:
            dt = determine_datetime(src, prefer_exif=prefer_exif)
            target_dir = build_target_dir(root_dir, dt, scheme=scheme, years_folder=years_folder)
            dest = unique_destination(target_dir / src.name)
            src_rel = str(src.relative_to(root_dir)) if root_dir in src.parents or src == root_dir else str(src)
            dst_rel = str(dest.relative_to(root_dir)) if dest.is_absolute() else str(dest)
            if dry_run:
                log_move(src_rel, dst_rel, dry=True)
            else:
                target_dir.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(dest))
                log_move(src_rel, dst_rel, dry=False)
            moved += 1
        except Exception as e:
            errors += 1
            log_err(f"{src}: {e}")
    return moved, errors

# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="FilesDate",
        description="Sortiert Dateien nach Datum in konfigurierbare Ordnerstrukturen.",
        epilog=(
            "Beispiele:\n"
            "  FilesDate                         # alle Dateien verarbeiten\n"
            "  FilesDate --ext .md .txt          # nur .md und .txt\n"
            "  FilesDate .jpg .png               # nur .jpg und .png (positional)\n"
            "  FilesDate --root /pfad --scheme international_day\n"
            "  FilesDate --dry-run               # nur anzeigen\n"
            "ENV:\n"
            "  NO_EMOJI=1  -> Emojis/Icons aus\n"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    p.add_argument("--root", default=".", help="Wurzelverzeichnis (Standard: aktuelles Verzeichnis)")
    p.add_argument(
        "--scheme",
        choices=["international_day", "years", "de_months"],
        default=CONFIG["folder_naming"],
        help="Ordnerstruktur (Standard: de_months)",
    )
    p.add_argument("--ext", nargs="*", default=None, help="Nur diese Dateiendungen verarbeiten, z.B. --ext .md .jpg")
    p.add_argument("ext_positionals", nargs="*", help="Alternative zu --ext: Endungen direkt angeben (.md .jpg ...)")
    p.add_argument("--dry-run", action="store_true", help="Nur anzeigen, keine Dateien verschieben")
    return p.parse_args()

def main() -> None:
    print_header("FilesDate – Datumssortierung")
    args = parse_args()
    root_dir = Path(args.root).resolve()
    if not root_dir.exists() or not root_dir.is_dir():
        log_err(f"Root-Verzeichnis existiert nicht: {root_dir}")
        raise SystemExit(2)

    # Interaktive Fragen
    years_folder = ask_yes_no("Soll ein 'years' Ordner angelegt/verwendet werden? (y/n): ")
    prefer_exif = ask_yes_no("EXIF-Datum verwenden, falls vorhanden? (y/n): ")

    if prefer_exif and not PIL_AVAILABLE:
        log_warn("Pillow (PIL) ist nicht installiert – EXIF wird ignoriert. Tipp: pip install Pillow")

    # Endungen auswerten
    provided_exts = args.ext if args.ext is not None else args.ext_positionals
    extensions = normalize_exts(provided_exts)

    log_info(f"Wurzel: {C.BOLD}{root_dir}{C.RESET}")
    log_info(f"Schema: {C.BOLD}{args.scheme}{C.RESET} | years-Ordner: {C.BOLD}{'ja' if years_folder else 'nein'}{C.RESET} | EXIF: {C.BOLD}{'ja' if prefer_exif else 'nein'}{C.RESET}")
    if extensions:
        log_info(f"Filter-Endungen: {', '.join(extensions)}")
    else:
        log_info("Filter-Endungen: (keine) – alle Dateien werden verarbeitet")

    # Schnappschuss + Filter
    all_files = snapshot_files(root_dir)
    candidates = filter_by_ext(all_files, extensions)

    # Eigene Skriptdatei ausschließen (falls im selben Ordner)
    try:
        self_path = Path(__file__).resolve()
        candidates = [p for p in candidates if p.resolve() != self_path]
    except Exception:
        pass

    # Verschieben / Anzeigen
    moved, errors = move_files(
        candidates,
        root_dir=root_dir,
        scheme=args.scheme,
        years_folder=years_folder,
        prefer_exif=prefer_exif,
        dry_run=args.dry_run,
    )

    skipped = len(all_files) - len(candidates)
    print_summary(total=len(all_files), processed=len(candidates), skipped=skipped, moved=moved, errors=errors)

if __name__ == "__main__":
    main()
