#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ganttify_simple (Obsidian-Version)

- Sucht die Tabelle strikt zwischen <!-- GANTT:DATA START --> ... <!-- GANTT:DATA END -->
- Konvertiert sie in ein fixes Mermaid-Gantt-Diagramm
- Wählt ein Mermaid-Theme (null, default, forest, dark, neutral) per Index:
  0 = null
  1 = default
  2 = forest
  3 = dark
  4 = neutral

Aufruf-Beispiele:
  Interaktive Stilwahl:
    python3 Ganttify.py README.md

  Direktes Theme per Argument (keine Nachfrage):
    python3 Ganttify.py --0 README.md   # theme = null
    python3 Ganttify.py --2 README.md   # theme = forest
"""

from __future__ import annotations

import argparse
import re
import sys
import json
from pathlib import Path
from typing import Dict, List, Optional

VERSION = "1.3.0-obsidian-theme"

# Feste Marker für den generierten Block
MARKER_START_NORM = "<!-- GANTT:GENERATED START -->"
MARKER_END_NORM   = "<!-- GANTT:GENERATED END -->"
DATA_START_NORM   = "<!-- GANTT:DATA START -->"
DATA_END_NORM     = "<!-- GANTT:DATA END -->"

# Tolerante Erkennung (beliebige Whitespaces)
RE_GEN_START  = re.compile(r"<!--\s*GANTT:GENERATED\s+START\s*-->", re.I)
RE_GEN_END    = re.compile(r"<!--\s*GANTT:GENERATED\s+END\s*-->", re.I)
RE_DATA_START = re.compile(r"<!--\s*GANTT:DATA\s+START\s*-->", re.I)
RE_DATA_END   = re.compile(r"<!--\s*GANTT:DATA\s+END\s*-->", re.I)


def read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def write_text(p: Path, s: str) -> None:
    p.write_text(s, encoding="utf-8")


# ---------- Data-block + Table parsing ----------

def _slice_data_block(text: str, debug: bool = False, path: Optional[Path] = None) -> Optional[str]:
    m1 = RE_DATA_START.search(text)
    m2 = RE_DATA_END.search(text, m1.end()) if m1 else None
    if not m1:
        if debug:
            print(f"[DEBUG] DATA START Marker nicht gefunden in {path or ''}", file=sys.stderr)
        return None
    if not m2:
        if debug:
            print(f"[DEBUG] DATA END Marker nicht gefunden in {path or ''}", file=sys.stderr)
        return None
    return text[m1.end():m2.start()]


# Akzeptiere -, :, = und auch Unicode –/— als Trenner
RE_TABLE_SEP = re.compile(r"^\s*\|?[\-\=\:\u2013\u2014\s\|]+\|?\s*$")


def _split_row(row: str) -> List[str]:
    s = row.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def _normalize_header(name: str) -> str:
    n = re.sub(r"\s+", "", name.strip().lower())
    mapping = {
        "bereich":   "section",
        "section":   "section",
        "aufgabe":   "title",
        "task":      "title",
        "title":     "title",
        "start":     "start",
        "dauer":     "duration",
        "duration":  "duration",
        "datum":     "date",
        "date":      "date",
        "id":        "id",
        "status":    "status",
        "klasse":    "class",
        "class":     "class",
    }
    return mapping.get(n, n)


def _find_table_in_block(block: str, debug: bool = False, path: Optional[Path] = None) -> Optional[List[str]]:
    lines = block.splitlines()
    i = 0
    while i < len(lines) - 1:
        l1 = lines[i]
        l2 = lines[i + 1] if i + 1 < len(lines) else ""
        if ("|" in l1) and RE_TABLE_SEP.match(l2 or ""):
            # Tabelle gefunden, nach unten sammeln
            j = i + 2
            while j < len(lines):
                lj = lines[j]
                if not lj.strip() or "|" not in lj or lj.strip().startswith(">"):
                    break
                j += 1
            return lines[i:j]
        i += 1
    if debug:
        snippet = "\n".join(lines[:10])
        print(f"[DEBUG] Keine Tabelle im DATA-Block gefunden ({path or ''}). Erste Zeilen:\n{snippet}", file=sys.stderr)
    return None


def parse_table(text: str, debug: bool = False, path: Optional[Path] = None) -> List[Dict[str, str]]:
    """
    Sucht im DATA-Block die erste Markdown-Tabelle und gibt eine Liste von Zeilen-Dicts zurück.
    Erwartete Kernspalten: Start, Dauer (Duration).
    Optional: Bereich/Section, Aufgabe/Title, Datum/Date, id, status, class.
    """
    block = _slice_data_block(text, debug=debug, path=path)
    if block is None:
        return []

    raw = _find_table_in_block(block, debug=debug, path=path)
    if not raw or len(raw) < 2:
        return []

    header_cells = _split_row(raw[0])
    if not RE_TABLE_SEP.search(raw[1]):
        if debug:
            print(f"[DEBUG] Separator-Zeile unplausibel: {raw[1]!r}", file=sys.stderr)
        return []

    headers = [_normalize_header(h) for h in header_cells]

    rows: List[Dict[str, str]] = []
    for line in raw[2:]:
        if not line.strip() or "|" not in line:
            break
        cells = _split_row(line)
        if len(cells) < len(headers):
            cells += [""] * (len(headers) - len(cells))
        if len(cells) > len(headers):
            cells = cells[:len(headers)]
        row = {headers[i]: cells[i] for i in range(len(headers))}
        # Wir verlangen mindestens Start + Dauer
        if not (row.get("start") and row.get("duration")):
            continue
        rows.append(row)

    if debug and not rows:
        print(f"[DEBUG] Alle Tabellenzeilen wurden als unvollständig verworfen.", file=sys.stderr)
    return rows


# ---------- Mermaid generation ----------

GANTT_TITLE       = "Ganttablauf"
GANTT_AXIS_FORMAT = "%d.%m."
GANTT_TODAY       = True
GANTT_DATEFORMAT  = "YYYY-MM-DD HH:mm"  # Datum + Uhrzeit

# Basisdatum, falls in der Tabelle nur Uhrzeiten stehen (Start-Spalte = "09:00" etc.)
BASE_DATE         = "2025-11-01"

TIME_ONLY_RE   = re.compile(r"^\d{1,2}:\d{2}(?::\d{2})?$")
DATETIME_RE    = re.compile(r"^\d{4}-\d{2}-\d{2}(?:[ T]\d{1,2}:\d{2}(?::\d{2})?)?$")
DATE_ONLY_RE   = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def build_start_datetime(row: Dict[str, str]) -> str:
    """
    Erzeugt aus den Feldern einer Tabellenzeile ein Start-Datum/Zeit im Format:
      YYYY-MM-DD HH:mm

    Unterstützte Fälle:
    1) Datum + Start  (Spalten 'Datum'/'Date' + 'Start')
       z.B. 2025-11-17 + 09:00 -> 2025-11-17 09:00

    2) Nur Start + Dauer, Start = Uhrzeit (z.B. 15:30)
       -> BASE_DATE + Uhrzeit, z.B. 2025-11-01 15:30

    3) Nur Start = vollständiges Datum oder Datum+Zeit
       z.B. 2025-11-17 09:00 -> unverändert
            2025-11-17       -> 2025-11-17 00:00
    """
    # deutsche/englische Varianten für Datumsspalte
    date_val = (row.get("datum") or row.get("date") or "").strip()
    start_raw = (row.get("start") or "").strip()

    # 1) Wenn Datum + Start vorhanden
    if date_val and start_raw:
        if TIME_ONLY_RE.match(start_raw):
            # z.B. "2025-11-17" + "09:00" -> "2025-11-17 09:00"
            return f"{date_val} {start_raw}"
        # falls Start selbst schon ein Datum enthält, dieses bevorzugen
        if DATETIME_RE.match(start_raw):
            if DATE_ONLY_RE.match(start_raw):
                return f"{start_raw} 00:00"
            return start_raw
        # Fallback: Datum + Start aneinander hängen
        return f"{date_val} {start_raw}"

    # 2) Kein Datum in eigener Spalte -> Start auswerten
    if DATETIME_RE.match(start_raw):
        # "2025-11-17 09:00" oder "2025-11-17"
        if DATE_ONLY_RE.match(start_raw):
            return f"{start_raw} 00:00"
        return start_raw

    if TIME_ONLY_RE.match(start_raw):
        # Nur Uhrzeit, z.B. Tabellenform "Start | Dauer"
        # -> mit Basisdatum kombinieren
        return f"{BASE_DATE} {start_raw}"

    # Fallback: so wie es ist – Mermaid wird ggf. meckern, aber wir probieren es
    return start_raw


# ---------- Styles (Mermaid-Theme-Auswahl) ----------

# Index -> (Anzeige-Name, Mermaid-Theme-Name)
STYLE_OPTIONS = [
    ("Theme: null (kein Mermaid-Theme, reine CSS)", "null"),      # 0
    ("Theme: default", "default"),                                # 1
    ("Theme: forest", "forest"),                                  # 2
    ("Theme: dark", "dark"),                                      # 3
    ("Theme: neutral", "neutral"),                                # 4
]


def choose_theme(preselected_idx: Optional[int] = None, debug: bool = False) -> str:
    """
    Wählt das Theme:
      - Wenn preselected_idx gesetzt ist (z.B. über --0, --1, ...), wird direkt dieses genommen.
      - Sonst interaktive Auswahl im Terminal (0..N-1).
    Gibt den Theme-String zurück, z.B. "null", "forest", ...
    """
    max_idx = len(STYLE_OPTIONS) - 1

    def _validate_idx(idx: int) -> int:
        if 0 <= idx <= max_idx:
            return idx
        print(f"[INFO] Ungültiger Theme-Index {idx}, es wird 0 (null) verwendet.", file=sys.stderr)
        return 0

    # Fall A: Theme wurde über CLI vorgegeben
    if preselected_idx is not None:
        idx = _validate_idx(preselected_idx)
        name, theme = STYLE_OPTIONS[idx]
        if debug:
            print(f"[DEBUG] Theme per Argument gewählt: {idx} -> {name} ({theme})", file=sys.stderr)
        else:
            print(f"→ Theme: {name} ({theme})")
        return theme

    # Fall B: Interaktive Auswahl
    print("\nTheme-Auswahl:")
    for i, (name, theme) in enumerate(STYLE_OPTIONS):
        print(f"  {i}) {name} [{theme}]")

    choice = input(f"Auswahl (0-{max_idx}) [0]: ").strip()
    if choice == "":
        choice = "0"

    try:
        idx = int(choice)
    except ValueError:
        print("[INFO] Ungültige Eingabe, Theme 0 (null) wird verwendet.", file=sys.stderr)
        idx = 0

    idx = _validate_idx(idx)
    name, theme = STYLE_OPTIONS[idx]
    if debug:
        print(f"[DEBUG] Theme gewählt: {idx} -> {name} ({theme})", file=sys.stderr)
    else:
        print(f"→ Theme: {name} ({theme})")
    return theme


def mermaid_from_rows(
    rows: List[Dict[str, str]],
    theme: str,
) -> str:
    out: List[str] = []

    # Init-Konfiguration als Python-Dict
    init_cfg = {
        "theme": theme,
        "gantt": {
            "todayMarker": GANTT_TODAY,
        },
    }

    # Sichere JSON-Serialisierung (keine Klammerprobleme)
    init_json = json.dumps(init_cfg, ensure_ascii=False)

    out.append("```mermaid")
    out.append(f"%%{{init: {init_json}}}%%")
    out.append("gantt")
    out.append(f"  title {GANTT_TITLE}")
    out.append(f"  dateFormat  {GANTT_DATEFORMAT}")
    out.append(f"  axisFormat  {GANTT_AXIS_FORMAT}")

    cur_sec: Optional[str] = None
    for idx, r in enumerate(rows):
        sec = (r.get("section") or "Allgemein").strip() or "Allgemein"
        if sec != cur_sec:
            out.append(f"\n  section {sec}")
            cur_sec = sec

        title = (r.get("title") or "").strip() or f"Eintrag {idx + 1}"

        # Start-Datum/Zeit über Hilfsfunktion bauen
        start = build_start_datetime(r)
        dur   = (r.get("duration") or "").strip()
        status = (r.get("status") or "").strip()
        tid    = (r.get("id") or "").strip()

        status_part = f"{status}, " if status else ""
        id_part     = f"{tid}, " if tid else ""

        out.append(f"  {title} :{status_part}{id_part}{start}, {dur}")

    out.append("```")
    return "\n".join(out)


# ---------- Injection ----------

def inject_generated(md_text: str, generated_block: str) -> str:
    """
    Fügt den generierten Block zwischen MARKER_START_NORM und MARKER_END_NORM ein.
    Falls der Bereich schon existiert, wird er ersetzt.
    """
    replacement = f"{MARKER_START_NORM}\n{generated_block}\n\n{MARKER_END_NORM}"

    m1 = RE_GEN_START.search(md_text)
    m2 = RE_GEN_END.search(md_text, m1.end()) if m1 else None
    if m1 and m2:
        span = (m1.start(), m2.end())
        return md_text[:span[0]] + replacement + md_text[span[1]:]

    # kein vorhandener Generated-Block -> vorne einfügen
    return replacement + "\n\n" + md_text


# ---------- Prozess ----------

def process_file(
    path: Path,
    stdout: bool = False,
    dry_run: bool = False,
    debug: bool = False,
    theme: str = "null",
) -> bool:
    md = read_text(path)
    rows = parse_table(md, debug=debug, path=path)
    if not rows:
        print(f"[SKIP] Keine gültige Tabelle gefunden: {path}", file=sys.stderr)
        return False

    code = mermaid_from_rows(rows, theme=theme)

    new_md = inject_generated(md, code)
    changed = (new_md != md)

    if stdout:
        # Nur den Block mit Markern ausgeben
        print(f"{MARKER_START_NORM}\n{code}\n\n{MARKER_END_NORM}")
        return changed

    if dry_run:
        print(f"[DRY] {'würde ändern' if changed else 'keine Änderung'}: {path}")
        return changed

    if changed:
        write_text(path, new_md)
        print(f"[OK] Aktualisiert: {path}")
    else:
        print(f"[OK] Keine Änderungen: {path}")
    return changed


# ---------- CLI ----------

def collect_targets(inputs: List[str], ext: str, recursive: bool) -> List[Path]:
    targets: List[Path] = []
    items = inputs or [str(Path.cwd())]
    for item in items:
        p = Path(item)
        if p.is_dir():
            it = p.rglob(f"*{ext}") if recursive else p.glob(f"*{ext}")
            targets.extend(sorted(x for x in it if x.is_file()))
        elif p.is_file():
            targets.append(p)
        else:
            print(f"[WARN] Übersprungen (nicht gefunden): {p}", file=sys.stderr)
    seen = set()
    out: List[Path] = []
    for t in targets:
        r = t.resolve()
        if r not in seen:
            seen.add(r)
            out.append(t)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Erzeugt ein einfaches Mermaid-Gantt aus MD-Tabelle im GANTT:DATA-Block und pflegt ihn ein (mit Mermaid-Theme-Auswahl)."
    )
    ap.add_argument("files", nargs="*", help="Markdown-Dateien oder Ordner")
    ap.add_argument("-r", "--recursive", action="store_true", help="Ordner rekursiv durchsuchen")
    ap.add_argument("--ext", default=".md", help="Dateiendung (Default: .md)")
    ap.add_argument("--stdout", action="store_true", help="nur den generierten Gantt-Block (mit Markern) ausgeben")
    ap.add_argument("--dry-run", action="store_true", help="Änderungen anzeigen, aber nicht schreiben")
    ap.add_argument("--debug", action="store_true", help="zusätzliche Diagnosemeldungen ausgeben")
    ap.add_argument("-V", "--version", action="store_true", help="Version anzeigen und beenden")

    # Generisches Argument für Stilindex, z.B. --style 2
    ap.add_argument(
        "--style",
        type=int,
        dest="style_index",
        help="Theme-Index (0 = null, 1 = default, 2 = forest, 3 = dark, 4 = neutral). "
             "Alternativ: direkt --0, --1, ... verwenden.",
    )

    # Spezielle Shortcuts: --0, --1, --2, ...
    for idx, (name, theme) in enumerate(STYLE_OPTIONS):
        ap.add_argument(
            f"--{idx}",
            dest="style_index",
            action="store_const",
            const=idx,
            help=f"Theme {idx}: {name} [{theme}]",
        )

    args = ap.parse_args()

    if args.version:
        print(f"ganttify_simple {VERSION}")
        sys.exit(0)

    targets = collect_targets(args.files, args.ext, args.recursive)
    if not targets:
        ap.print_usage(sys.stderr)
        sys.exit(2)

    # Theme wählen (entweder per Argument vorgegeben oder interaktiv)
    theme = choose_theme(preselected_idx=args.style_index, debug=args.debug)

    rc = 0
    for f in targets:
        try:
            process_file(
                Path(f),
                stdout=args.stdout,
                dry_run=args.dry_run,
                debug=args.debug,
                theme=theme,
            )
        except Exception as e:
            rc = 1
            print(f"[FEHLER] {f}: {e}", file=sys.stderr)
    sys.exit(rc)


if __name__ == "__main__":
    main()
