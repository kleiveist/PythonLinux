#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PyHelp – Übersicht aller Python-Skripte im bin-Ordner.

Funktionen:
- scannt rekursiv nach *.py
- zieht Kurzbeschreibung aus Docstring oder Kopf-Kommentaren
- hübsche Ausgabe mit Icons, Farben, Gruppierung nach Ordner
- hinterlegte Beschreibungen/Beispiele für bekannte Skripte
- CLI-Optionen: --root, --long, --grep, --json, --no-emoji, --no-color
"""

from __future__ import annotations

import argparse
import ast
import os
import re
import sys
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ============ Icons / Farben ============

def _use_emoji() -> bool:
    if os.environ.get("NO_EMOJI") == "1":
        return False
    # crude TTY check; allow emojis by default
    return True

def _use_color() -> bool:
    if os.environ.get("NO_COLOR") == "1":
        return False
    return sys.stdout.isatty()

USE_EMOJI = _use_emoji()
USE_COLOR = _use_color()

class C:
    if _use_color():
        RESET = "\033[0m"
        BOLD  = "\033[1m"
        DIM   = "\033[2m"
        FG    = type("FG", (), {
            "BLUE":"\033[34m", "CYAN":"\033[36m", "GREEN":"\033[32m",
            "YELLOW":"\033[33m", "RED":"\033[31m", "MAGENTA":"\033[35m",
            "GREY":"\033[90m"
        })()
    else:
        RESET = BOLD = DIM = ""
        FG = type("FG", (), { "BLUE":"", "CYAN":"", "GREEN":"", "YELLOW":"", "RED":"", "MAGENTA":"", "GREY":"" })()

ICON = {
    "folder": "📁" if USE_EMOJI else "[DIR]",
    "file":   "📝" if USE_EMOJI else "[PY]",
    "info":   "ℹ️" if USE_EMOJI else "[i]",
    "ok":     "✅" if USE_EMOJI else "[OK]",
    "warn":   "⚠️" if USE_EMOJI else "[!]",
    "err":    "❌" if USE_EMOJI else "[X]",
    "game":   "🎮" if USE_EMOJI else "[GAME]",
    "img":    "🖼️" if USE_EMOJI else "[IMG]",
    "pdf":    "📄" if USE_EMOJI else "[PDF]",
    "report": "🧾" if USE_EMOJI else "[REP]",
    "sys":    "🖥️" if USE_EMOJI else "[SYS]",
    "obi":    "🔌" if USE_EMOJI else "[OBIS]",
    "tools":  "🧰" if USE_EMOJI else "[TOOL]",
    "arrow":  "→"  if USE_EMOJI else "->",
    "star":   "★"  if USE_EMOJI else "*",
}

# ============ Datenstrukturen ============

@dataclass
class ScriptInfo:
    rel_dir: str
    filename: str
    path: Path
    title: str
    short: str
    category: str
    examples: Optional[List[str]] = None

# ============ Hilfen: Kurztexte extrahieren ============

def read_text_safe(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        try:
            return p.read_text(encoding="latin-1", errors="replace")
        except Exception:
            return ""

def docstring_of(py_path: Path) -> Optional[str]:
    try:
        src = read_text_safe(py_path)
        mod = ast.parse(src)
        doc = ast.get_docstring(mod)
        return doc
    except Exception:
        return None

def header_comment_of(py_path: Path, max_lines: int = 30) -> Optional[str]:
    txt = read_text_safe(py_path)
    lines = txt.splitlines()
    header: List[str] = []
    for i, line in enumerate(lines[:max_lines]):
        s = line.strip()
        if i == 0 and s.startswith("#!") :
            # shebang -> ignore, keep scanning
            continue
        if s.startswith('"""') or s.startswith("'''"):
            # a top-level docstring starts; we skip here because docstring_of handles this
            break
        if s.startswith("#"):
            header.append(s.lstrip("#").strip())
        elif s == "":
            # allow sparse empty lines at the top
            if header:
                header.append("")
        else:
            break
    cleaned = "\n".join([ln for ln in header]).strip()
    return cleaned or None

def first_sentence(text: str, limit: int = 200) -> str:
    t = " ".join(text.strip().split())
    # split by sentence end markers
    m = re.split(r"(?<=[.!?])\s+", t)
    s = m[0] if m else t
    if len(s) > limit:
        return s[:limit-1] + "…"
    return s

# ============ Kategorien / hinterlegte Beschreibungen ============

def guess_category(rel_dir: str, filename: str) -> str:
    d = rel_dir.lower()
    f = filename.lower()
    if "imgconvert" in d or "image" in f:
        return "img"
    if "pypdf" in d or "pdf" in f:
        return "pdf"
    if "pyreport" in d or "summary" in f or "folderlist" in f:
        return "report"
    if "pysystem" in d or "system" in f:
        return "sys"
    if "pyobis" in d or "obis" in f:
        return "obi"
    if "pygame" in d or "snake" in f or "spaceship" in f:
        return "game"
    return "tools"

CATEGORY_ICON = {
    "img": ICON["img"],
    "pdf": ICON["pdf"],
    "report": ICON["report"],
    "sys": ICON["sys"],
    "obi": ICON["obi"],
    "game": ICON["game"],
    "tools": ICON["tools"],
}

# Hinterlegte Texte für deine bekannten Skripte (relativ zum Root)
KNOWN: Dict[str, Dict[str, object]] = {
    "ImgConvert/ImgConvert.py": {
        "title": "Bild‑Konverter (CLI)",
        "short": "Konvertiert PNG/JPG/WEBP/BMP/TIFF/ICO; rekursiv, Qualitäts‑Optionen, Dry‑Run.",
        "examples": [
            "python ImgConvert.py --png --webp --all",
            "python ImgConvert.py --from png --to ico --ico-sizes 16,32,48,64,128,256",
            "python ImgConvert.py --png --jpg --bg \"#1e1e1e\" --quality 90",
        ],
        "cat": "img",
    },
    "PyReport/folderlist.py": {
        "title": "Ordnerbaum als Liste",
        "short": "Erzeugt FolderList‑Dateien je Tiefe; optional Dateien, Icons, Mehrfach‑Modus.",
        "examples": [
            "python folderlist.py --multi             # 1‑..‑N‑FolderList.txt",
            "python folderlist.py --depth 3 --files   # bis Tiefe 3 inkl. Dateien",
        ],
        "cat": "report",
    },
    "PyReport/exfolderlist.py": {
        "title": "FolderList‑Parser",
        "short": "Parst Baum‑Zeilen (mit │├└📁) zu Pfadlisten; kleines Beispielskript.",
        "cat": "report",
    },
    "PyReport/summary.py": {
        "title": "Markdown‑Scanner & Report",
        "short": "Findet .md/.py, erzeugt JSON‑Index und Bericht; Inhalte als full/snippet/none.",
        "examples": [
            "python summary.py --.py --full",
            "python summary.py --.md --.py",
            "python summary.py --all                 # Aggregat unabhängig vom Inhaltsmodus",
        ],
        "cat": "report",
    },
    "PySystem/InstallApp.py": {
        "title": "AppImage → Desktop",
        "short": "Integriert AppImage in das Menü (.desktop, Icon); kein Wrapper in bin.",
        "cat": "sys",
    },
    "PySystem/System.py": {
        "title": "System‑Report",
        "short": "Zeigt OS/CPU/RAM/GPU/Disks/Netzwerk; optional Markdown‑Export (rich).",
        "cat": "sys",
    },
    "PyPDF/pdf2md.py": {
        "title": "PDF → Markdown",
        "short": "Konvertiert PDF(s) nach Markdown via pymupdf4llm – Ordner‑ oder Einzelmodus.",
        "examples": [
            "python pdf2md.py               # alle PDFs → ./md",
            "python pdf2md.py ~/doc/A.pdf   # nur diese Datei → ./md neben A.pdf",
        ],
        "cat": "pdf",
    },
    "PYGame/snake.py": {
        "title": "Snake (Terminal)",
        "short": "Curses‑Snake mit Leben, Gift, Flash‑Mechanik; Pfeiltasten‑Steuerung.",
        "cat": "game",
    },
    "PYGame/spaceship.py": {
        "title": "Spaceship (ASCII)",
        "short": "Kleines Terminal‑Game im Weltraum‑Setting.",
        "cat": "game",
    },
    "PyObis/P25ObisLinks.py": {
        "title": "OBIS Markdown‑Pflege",
        "short": "Pflegt AUTOGEN‑Blöcke und kanonische Indexdateien in OBIS‑Markdown‑Strukturen.",
        "cat": "obi",
    },
    "PyObis/ObisDatabase.py": {
        "title": "OBIS‑Datenbank",
        "short": "Werkzeuge rund um OBIS‑Daten (Details per Docstring/Kopfzeile).",
        "cat": "obi",
    },
    "PyFiles/ExTree.py": {
        "title": "Datei‑/Baum‑Werkzeug",
        "short": "Hilfsskript für Datei‑/Ordnerlisten (Details per Docstring).",
        "cat": "tools",
    },
    "PyFiles/InTree.py": {
        "title": "Ordner‑Scanner",
        "short": "Scannt Verzeichnisse und erstellt Übersichten (Details per Docstring).",
        "cat": "tools",
    },
    "PyFiles/FilesDate.py": {
        "title": "Dateidatum‑Utilities",
        "short": "Arbeitet mit Datei‑Zeitstempeln (Details per Docstring).",
        "cat": "tools",
    },
}

# ============ Scan & Sammeln ============

EXCLUDE_DIRS = {".git", "__pycache__", "venv", ".venv", ".mypy_cache", ".pytest_cache"}

def collect_scripts(root: Path, grep: Optional[str]) -> List[ScriptInfo]:
    items: List[ScriptInfo] = []
    for p in sorted(root.rglob("*.py")):
        if any(part in EXCLUDE_DIRS for part in p.parts):
            continue
        # selbst ausschließen
        try:
            if p.resolve() == Path(__file__).resolve():
                continue
        except Exception:
            pass

        rel = p.relative_to(root)
        rel_dir = str(rel.parent).replace("\\", "/")
        filename = rel.name

        key = f"{rel_dir}/{filename}" if rel_dir != "." else filename
        known = KNOWN.get(key)

        cat = (known.get("cat") if known else None) or guess_category(rel_dir, filename)
        title = (known.get("title") if known else None) or filename
        examples = known.get("examples") if known else None

        short: Optional[str] = (known.get("short") if known else None)  # type: ignore

        if not short:
            # docstring / header
            ds = docstring_of(p)
            if ds:
                short = first_sentence(ds, 220)
            else:
                hc = header_comment_of(p)
                if hc:
                    short = first_sentence(hc, 220)
        if not short:
            short = "Keine Kurzbeschreibung gefunden."

        si = ScriptInfo(
            rel_dir=rel_dir if rel_dir != "." else "",
            filename=filename,
            path=p,
            title=str(title),
            short=short,
            category=str(cat),
            examples=list(examples) if isinstance(examples, list) else None,
        )
        if grep:
            g = grep.lower()
            blob = " ".join([si.title, si.short, key]).lower()
            if g not in blob:
                continue
        items.append(si)

    # sort: group by folder, then by filename
    items.sort(key=lambda s: (s.rel_dir.lower(), s.filename.lower()))
    return items

# ============ Rendering ============

def colorize(s: str, color: str) -> str:
    return f"{color}{s}{C.RESET}" if USE_COLOR and color else s

def bold(s: str) -> str:
    return f"{C.BOLD}{s}{C.RESET}" if USE_COLOR else s

def icon_for(cat: str) -> str:
    return CATEGORY_ICON.get(cat, ICON["tools"])

def print_grouped(items: List[ScriptInfo], long: bool = False) -> None:
    if not items:
        print(f"{ICON['warn']} Keine Skripte gefunden.")
        return

    # group by folder
    groups: Dict[str, List[ScriptInfo]] = {}
    for it in items:
        groups.setdefault(it.rel_dir or ".", []).append(it)

    for gdir in sorted(groups.keys(), key=lambda x: (x != ".", x.lower())):
        gitems = groups[gdir]
        head = f"{ICON['folder']} {gdir if gdir != '.' else '(Root)'}"
        print(bold(colorize(head, C.FG.BLUE)))
        for it in gitems:
            lead = f"  {icon_for(it.category)} {ICON['file']} {bold(it.title)}"
            trail = f"{colorize(' — ' + it.short, C.FG.GREY)}"
            print(f"{lead}{trail}")
            if long and it.examples:
                for ex in it.examples:
                    print(f"      {colorize(ICON['arrow'] + ' ' + ex, C.FG.CYAN)}")
        print()  # spacer

def print_json(items: List[ScriptInfo]) -> None:
    out = []
    for s in items:
        out.append({
            "folder": s.rel_dir or ".",
            "file": s.filename,
            "path": str(s.path),
            "title": s.title,
            "short": s.short,
            "category": s.category,
            "examples": s.examples or [],
        })
    print(json.dumps(out, ensure_ascii=False, indent=2))

# ============ CLI ============

def parse_args(argv: List[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="PyHelp – hübsche Übersicht deiner Skripte im Terminal",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ap.add_argument("--root", type=Path, default=Path.cwd(), help="Wurzelordner (z. B. dein bin)")
    ap.add_argument("--long", action="store_true", help="lange Ausgabe inkl. Beispiele (falls vorhanden)")
    ap.add_argument("--grep", type=str, default=None, help="Filter (Name/Beschreibung enthält …)")
    ap.add_argument("--json", action="store_true", help="JSON statt hübscher Ansicht")
    ap.add_argument("--no-emoji", action="store_true", help="Emojis abschalten")
    ap.add_argument("--no-color", action="store_true", help="Farben abschalten")
    return ap.parse_args(argv)

def main(argv: List[str] | None = None) -> int:
    ns = parse_args(argv or sys.argv[1:])

    global USE_EMOJI, USE_COLOR
    if ns.no_emoji:
        USE_EMOJI = False
    if ns.no_color:
        USE_COLOR = False

    root = ns.root.expanduser().resolve()
    if not root.is_dir():
        print(f"{ICON['err']} Wurzelordner nicht gefunden: {root}", file=sys.stderr)
        return 2

    head = f"{ICON['info']} PyHelp – Übersicht in {root}"
    print(bold(colorize(head, C.FG.MAGENTA)))
    print()

    items = collect_scripts(root, grep=ns.grep)

    if ns.json:
        print_json(items)
        return 0

    print_grouped(items, long=ns.long)

    print(colorize(f"{ICON['ok']} {len(items)} Skript(e) gelistet.", C.FG.GREEN))
    if not ns.long:
        print(colorize(f"{ICON['info']} Tipp: --long zeigt Beispiele, --grep <wort> filtert.", C.FG.BLUE))
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print()
        print(f"{ICON['warn']} Abgebrochen.")
        raise
