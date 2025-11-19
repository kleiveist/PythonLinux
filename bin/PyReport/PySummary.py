#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import re
import time
from pathlib import Path
from datetime import datetime

# =========================
# Settings
# =========================
# Ausgabeziel:
# True  -> schreibe in Unterordner ./scan relativ zur CWD
# False -> schreibe in den Ordner, in dem diese .py-Datei liegt
USE_SUBFOLDER = False
OUTPUT_SUBFOLDER_NAME = "scan"

# Ausschlüsse (Ordnernamen relativ zur CWD)
EXCLUDE = [".git", "node_modules", "scan"]

# Dateinamen
REPORT_FILENAME = "summary.md"
INDEX_FILENAME = "index.json"
AGG_FILENAME = "allsummary.md"  # nur bei CONTENT_MODE == "full" oder --all

# Inhaltserfassung im Bericht: "none" | "snippet" | "full"
CONTENT_MODE = "snippet"
SNIPPET_CHARS = 800
TOC_DEPTH = 3

# Welche Text-/Code-Dateien sollen gescannt werden?
# Hinweis: Groß-/Kleinschreibung der Endungen wird ignoriert.
FILE_TYPES = [".py"]

# Verbosität / Konsolen-Feedback
VERBOSE = True
SHOW_DIRS = True
SHOW_FILES = True
MAX_NAME_WIDTH = 60
PROGRESS_EVERY = 25  # 0 = aus

# Icons (Console)
IC_SCAN = "🔍"
IC_DIR = "📁"
IC_FILE = "📝"
IC_SAVE = "💾"
IC_DONE = "✅"
IC_WARN = "⚠️"
IC_INFO = "ℹ️"
IC_SUM = "📊"
IC_TIME = "⏱️"
IC_OUT = "📦"

# Icons (Report/Struktur)
FOLDER_ICON = "📁"
FILE_ICON = "📝"

# Neu: Flag, ob immer eine Aggregatdatei über alle Dateien erzeugt wird (--all)
ALWAYS_AGGREGATE = False


# =========================
# Utils
# =========================
def human_size(num: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB", "PB"]:
        if num < 1024.0 or unit == "PB":
            return f"{num:.2f} {unit}" if unit != "B" else f"{num} {unit}"
        num /= 1024.0


def is_wanted_file(name: str) -> bool:
    return Path(name).suffix.lower() in {ext.lower() for ext in FILE_TYPES}


def extract_md_title_and_counts(text: str):
    title = None
    headings = 0
    lines = 0
    for line in text.splitlines():
        lines += 1
        s = line.strip()
        if s.startswith("#"):
            headings += 1
            if title is None:
                title = s.lstrip("#").strip()
    return title, headings, lines


def extract_toc(text: str, max_depth: int = 3):
    toc = []
    for line in text.splitlines():
        m = re.match(r"^(#{1,6})\s+(.*)", line.strip())
        if m:
            level = len(m.group(1))
            if level <= max_depth:
                toc.append((level, m.group(2).strip()))
    return toc


def make_snippet(text: str, max_chars: int = 600):
    in_code = False
    acc = []
    for raw in text.splitlines():
        line = raw.rstrip("\n")
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        s = line.strip()
        if not s:
            if acc:
                break
            else:
                continue
        if s.startswith("#") or s.startswith(">") or s.startswith(("-", "*", "+")):
            if acc:
                break
            else:
                continue
        acc.append(s)
        if sum(len(x) + 1 for x in acc) >= max_chars:
            break
    snippet = " ".join(acc).strip()
    if not snippet:
        snippet = text.strip().replace("\n", " ")
    if len(snippet) > max_chars:
        snippet = snippet[:max_chars].rstrip() + " …"
    return snippet


def count_words_chars(text: str):
    words = re.findall(r"\w+", text, re.UNICODE)
    return len(words), len(text)


def is_within_root(path: Path, root: Path) -> bool:
    # keine Pfade außerhalb von root (auch nicht via Symlink)
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except Exception:
        return False


def build_tree(lines):
    tree_lines = []
    has_next_stack = []
    for depth, name, is_dir, is_last in lines:
        while len(has_next_stack) < depth:
            has_next_stack.append(False)
        prefix = (
            ""
            if depth == 0
            else "".join("│   " if has_next_stack[i] else "    " for i in range(depth - 1))
            + ("└── " if is_last else "├── ")
        )
        icon = FOLDER_ICON if is_dir else FILE_ICON
        tree_lines.append(f"{prefix}{icon} {name}")
        if depth > 0:
            has_next_stack[depth - 1] = not is_last
            has_next_stack = has_next_stack[:depth]
    return "\n".join(tree_lines)


def tree_listing_for_root(root: Path, include_only_selected_types=True, exclude_names=None):
    if exclude_names is None:
        exclude_names = set()
    lines = [(0, ".", True, True)]

    def walk_dir(path: Path, depth: int):
        try:
            entries = list(path.iterdir())
        except Exception:
            entries = []
        dirs = sorted(
            [
                e
                for e in entries
                if e.is_dir() and e.name not in exclude_names and is_within_root(e, root)
            ],
            key=lambda p: p.name.lower(),
        )
        files = sorted(
            [
                e
                for e in entries
                if e.is_file()
                and (
                    not include_only_selected_types
                    or e.suffix.lower() in {ext.lower() for ext in FILE_TYPES}
                )
            ],
            key=lambda p: p.name.lower(),
        )
        children = [("dir", d) for d in dirs] + [("file", f) for f in files]
        for idx, (typ, p) in enumerate(children):
            is_last = idx == len(children) - 1
            lines.append((depth, p.name, typ == "dir", is_last))
            if typ == "dir":
                walk_dir(p, depth + 1)

    walk_dir(root, 1)
    return build_tree(lines)


def truncate_name(name: str, width: int) -> str:
    if width <= 0 or len(name) <= width:
        return name
    half = max(1, (width - 1) // 2)
    return name[:half] + "…" + name[-(width - half - 1) :]


# =========================
# Scan + Report
# =========================
def scan_md_files(root: Path, scan_exclude_dirs, exclude_exact_files):
    results = []
    dir_count = 0
    file_count = 0
    md_count = 0
    skipped_dirs = set()

    start = time.time()
    print(f"{IC_SCAN} Start: Scanne nur unterhalb von: {root}")

    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        # Verzeichnisfilter (in-place, damit os.walk nicht hineinläuft)
        clean = []
        for d in sorted(dirnames):
            p = Path(dirpath) / d
            if d in scan_exclude_dirs:
                if d not in skipped_dirs:
                    skipped_dirs.add(d)
                continue
            if not is_within_root(p, root):
                if VERBOSE:
                    print(f"{IC_WARN} Überspringe Symlink/externes Verzeichnis: {p}")
                continue
            clean.append(d)
        dirnames[:] = clean

        dir_count += 1
        if VERBOSE and SHOW_DIRS:
            rel = Path(dirpath).relative_to(root) if Path(dirpath) != root else Path(".")
            print(f"{IC_DIR} {rel}")

        filenames = sorted(filenames)
        for fn in filenames:
            file_count += 1
            if is_wanted_file(fn):
                # bestimmte Output-Dateien explizit ausschließen
                full_path = Path(dirpath) / fn
                if full_path.resolve() in exclude_exact_files:
                    continue
                md_count += 1
                p = Path(dirpath) / fn
                if not is_within_root(p, root):
                    if VERBOSE:
                        print(f"{IC_WARN} Datei außerhalb der Root erkannt (Symlink?): {p}")
                    continue
                rel = p.relative_to(root)
                if VERBOSE and SHOW_FILES:
                    print(f"  {IC_FILE} {truncate_name(str(rel), MAX_NAME_WIDTH)}")
                try:
                    text = p.read_text(encoding="utf-8", errors="ignore")
                except Exception as e:
                    if VERBOSE:
                        print(f"  {IC_WARN} Kann Datei nicht lesen: {rel} ({e})")
                    text = ""
                title, headings, lines = extract_md_title_and_counts(text)
                ext = Path(fn).suffix.lower()
                toc = extract_toc(text, max_depth=TOC_DEPTH) if ext == ".md" else []
                snippet = make_snippet(text, max_chars=SNIPPET_CHARS) if CONTENT_MODE != "none" else None
                wc, cc = count_words_chars(text)
                stats = p.stat()
                results.append(
                    {
                        "rel_path": str(rel),
                        "name": p.name,
                        "parent": str(rel.parent) if str(rel.parent) != "." else "",
                        "size_bytes": stats.st_size,
                        "size_human": human_size(stats.st_size),
                        "mtime": datetime.fromtimestamp(stats.st_mtime).isoformat(timespec="seconds"),
                        "title": title,
                        "headings": headings,
                        "lines": lines,
                        "words": wc,
                        "chars": cc,
                        "snippet": snippet,
                        "toc": toc,
                        # Vollen Inhalt speichern, wenn CONTENT_MODE == "full" ODER --all aktiv ist
                        "content": text if (CONTENT_MODE == "full" or ALWAYS_AGGREGATE) else None,
                    }
                )
                if PROGRESS_EVERY and (md_count % PROGRESS_EVERY == 0):
                    print(f"{IC_INFO} Zwischenstand: {md_count} Dateien, {dir_count} Verzeichnisse.")

    dur = time.time() - start
    print(f"{IC_DONE} Scan fertig in {dur:.2f}s — Verzeichnisse: {dir_count}, Dateien: {file_count}, Treffer (Typen): {md_count}")
    if skipped_dirs:
        print(f"{IC_INFO} Ausgelassene Ordner: {', '.join(sorted(skipped_dirs))}")
    return results


def path_with_icons(rel_path: str) -> str:
    parts = Path(rel_path).parts
    if not parts:
        return "."
    if len(parts) == 1:
        return f"{FILE_ICON} {parts[0]}"
    return " / ".join([f"{FOLDER_ICON} {p}" for p in parts[:-1]] + [f"{FILE_ICON} {parts[-1]}"])


def write_report(root: Path, outdir: Path, md_files):
    print(f"{IC_SAVE} Schreibe Bericht …")
    report_lines = []
    now = datetime.now().isoformat(timespec="seconds")

    report_lines.append(f"Markdown-Scan – Root: {root}")
    report_lines.append(f"Erzeugt: {now}")
    report_lines.append(
        f"Einstellungen: content={CONTENT_MODE}, snippet_chars={SNIPPET_CHARS}, toc_depth={TOC_DEPTH}, types={', '.join(FILE_TYPES)}"
    )
    report_lines.append("")
    report_lines.append("=== Dateien ===")
    report_lines.append("")

    by_parent = {}
    for it in md_files:
        by_parent.setdefault(it["parent"], []).append(it)

    for parent in sorted(by_parent.keys(), key=lambda s: (s != "", s.lower())):
        folder_disp = "." if parent in ("", ".") else parent
        report_lines.append(f"{FOLDER_ICON} {folder_disp}")
        for it in by_parent[parent]:
            report_lines.append(f"  {FILE_ICON} {it['name']}")
            report_lines.append(f"     Pfad: {path_with_icons(it['rel_path'])}")
            report_lines.append(f"     Größe: {it['size_human']} ({it['size_bytes']} B)")
            report_lines.append(f"     Geändert: {it['mtime']}")
            if it["title"]:
                report_lines.append(f"     Titel: {it['title']}")
            report_lines.append(
                f"     Überschriften: {it['headings']}, Zeilen: {it['lines']}, Wörter: {it['words']}, Zeichen: {it['chars']}"
            )
            if it.get("toc"):
                report_lines.append(f"     Gliederung:")
                for level, h in it["toc"]:
                    indent = "       " + ("  " * max(0, level - 2))
                    report_lines.append(f"{indent}• {'#' * level} {h}")
            if CONTENT_MODE in ("snippet", "full") and it.get("snippet"):
                report_lines.append(f"     Inhalt (Auszug): {it['snippet']}")
            if CONTENT_MODE == "full" and it.get("content") is not None:
                report_lines.append("     Inhalt (voll):")
                for ln in it["content"].splitlines():
                    report_lines.append("       " + ln)
            report_lines.append("")
        report_lines.append("")

    report_lines.append("=== Ordnerbaum (Quelle, nur ausgewählte Typen) ===")
    report_lines.append("")
    report_lines.append(tree_listing_for_root(root, include_only_selected_types=True))
    report_lines.append("")
    report_lines.append("=== Ordnerbaum (Ausgabeordner) ===")
    report_lines.append("")
    report_lines.append(tree_listing_for_root(outdir, include_only_selected_types=False))
    report_lines.append("")

    report_path = outdir / REPORT_FILENAME
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"{IC_DONE} Bericht geschrieben: {report_path}")
    return report_path


# =========================
# CLI
# =========================
def print_usage():
    msg = """
Verwendung:
  summary.py [--.EXT ...] [--full|--snippet|--none] [--all] [--help]

Optionen:
  --.EXT       Dateityp/Endung selektieren (mehrfach möglich), z. B. --.py --.md
               Wenn keine --.<ext>-Flags gesetzt sind, wird standardmäßig .txt verwendet.
  --full       Inhaltsmodus "full" (volle Inhalte in Bericht + Aggregatdatei)
  --snippet    Inhaltsmodus "snippet" (Standard, Auszug)
  --none       Inhaltsmodus "none" (keine Inhalte in den Bericht aufnehmen)
  --all        Rekursiver Scan (Standard) und zusätzlich immer eine Gesamtdatei
               mit dem vollen Inhalt aller gefundenen Dateien schreiben (auch ohne --full)
  --help, -h   Hilfe anzeigen

Beispiele:
  summary.py --.py --full
  summary.py --.md --.py
  summary.py               (entspricht: .txt + snippet)
  summary.py --.py --full --all
""".strip()
    print(msg)


def parse_cli_args(argv):
    """
    Unterstützt Flags wie --.py, --.md sowie --full/--snippet/--none/--all.
    Gibt (types, content_mode, all_flag) zurück, wobei:
      - types: Liste der gewünschten Endungen (inkl. Punkt), z. B. ['.py', '.md']
      - content_mode: 'full' | 'snippet' | 'none' | None (None => Standard beibehalten)
      - all_flag: True, wenn --all angegeben wurde
    """
    types = []
    content_mode = None
    all_flag = False

    for arg in argv:
        if arg in ("-h", "--help"):
            print_usage()
            sys.exit(0)
        elif arg == "--full":
            content_mode = "full"
        elif arg == "--snippet":
            content_mode = "snippet"
        elif arg == "--none":
            content_mode = "none"
        elif arg == "--all":
            all_flag = True
        elif arg.startswith("--."):
            ext = arg[2:]  # alles nach den zwei Bindestrichen
            if not ext.startswith("."):
                ext = "." + ext
            types.append(ext.lower())

    return types, content_mode, all_flag


# =========================
# Main
# =========================
def main():
    t0 = time.time()

    # CLI lesen und globale Defaults ggf. überschreiben
    cli_types, cli_content_mode, cli_all = parse_cli_args(sys.argv[1:])

    # Globale Konfiguration anpassen (damit alle Hilfsfunktionen die neuen Werte sehen)
    global FILE_TYPES, CONTENT_MODE, ALWAYS_AGGREGATE

    if cli_types:
        FILE_TYPES = cli_types
    else:
        # Standard-Dateityp, wenn nichts gesetzt wurde
        FILE_TYPES = [".txt"]

    if cli_content_mode is not None:
        CONTENT_MODE = cli_content_mode

    # --all aktiviert immer Aggregation über alle Unterordner (ohne CONTENT_MODE zu ändern)
    ALWAYS_AGGREGATE = bool(cli_all)

    # Root = aktuelles Arbeitsverzeichnis (CWD). Nur darunter wird gescannt.
    root = Path.cwd()

    # Ausgabeverzeichnis bestimmen
    if USE_SUBFOLDER:
        outdir = (root / OUTPUT_SUBFOLDER_NAME).resolve()
        outdir.mkdir(parents=True, exist_ok=True)
    else:
        outdir = root  # direkt ins CWD schreiben
        outdir.mkdir(parents=True, exist_ok=True)

    # Verzeichnisse/Dateien vom Scan ausschließen
    scan_exclude_dirs = set(EXCLUDE)
    if USE_SUBFOLDER:
        # sicherstellen, dass der Output-Subfolder nicht wieder mitgescannt wird
        scan_exclude_dirs.add(OUTPUT_SUBFOLDER_NAME)

    exclude_exact_files = set()
    # Output-Artefakte vom Scan ausschließen (wichtig, wenn outdir == root)
    exclude_exact_files.add((outdir / REPORT_FILENAME).resolve())
    exclude_exact_files.add((outdir / INDEX_FILENAME).resolve())
    if CONTENT_MODE == "full" or ALWAYS_AGGREGATE:
        exclude_exact_files.add((outdir / AGG_FILENAME).resolve())

    print(f"{IC_INFO} Root (CWD): {root}")
    print(f"{IC_OUT} Ausgabepfad: {outdir}  ({'Subfolder' if USE_SUBFOLDER else 'CWD'})")
    if scan_exclude_dirs:
        print(f"{IC_INFO} Exclude-Verzeichnisse: {', '.join(sorted(scan_exclude_dirs))}")
    print(f"{IC_INFO} Modus: content={CONTENT_MODE}, toc_depth={TOC_DEPTH}, snippet={SNIPPET_CHARS}")
    if ALWAYS_AGGREGATE:
        print(f"{IC_INFO} --all aktiv: Aggregatdatei wird unabhängig vom Inhaltsmodus erstellt")

    # Scan
    md_files = scan_md_files(root, scan_exclude_dirs, exclude_exact_files)
    md_files.sort(key=lambda x: x["rel_path"].lower())

    # JSON-Index
    print(f"{IC_SAVE} Schreibe Index …")
    index_path = outdir / INDEX_FILENAME
    index = {
        "scanned_root": str(root),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "count_files": len(md_files),
        "content_mode": CONTENT_MODE,
        "types": FILE_TYPES,
        "items": md_files,
    }
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{IC_DONE} Index geschrieben: {index_path}")

    # Bericht
    report_path = write_report(root, outdir, md_files)

    # Aggregatdatei (optional/erzwingen)
    agg_path = None
    if CONTENT_MODE == "full" or ALWAYS_AGGREGATE:
        print(f"{IC_SAVE} Erzeuge Aggregatdatei …")
        agg_path = outdir / AGG_FILENAME
        with agg_path.open("w", encoding="utf-8") as agg:
            agg.write(f"# Gesamtinhalte – Root: {root}\n\n")
            for it in md_files:
                src = it["rel_path"]
                agg.write(f"## {FILE_ICON} {it['name']} — ./{src}\n\n")
                content = it.get("content") or ""
                agg.write(content)
                if not content.endswith("\n"):
                    agg.write("\n")
                agg.write("\n---\n\n")
        print(f"{IC_DONE} Aggregat geschrieben: {agg_path}")

    t1 = time.time()
    print()
    print(f"{IC_SUM} Zusammenfassung")
    print(f"  {IC_FILE} Gefundene Dateien (nach Typen gefiltert): {len(md_files)}")
    print(f"  {IC_SAVE} Bericht: {report_path}")
    print(f"  {IC_SAVE} Index:   {index_path}")
    if agg_path:
        print(f"  {IC_SAVE} Aggregat: {agg_path}")
    print(f"  {IC_TIME} Gesamtdauer: {(t1 - t0):.2f}s")
    print(f"{IC_DONE} Fertig.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
