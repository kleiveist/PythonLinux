#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import os
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple

# =========================
# USER SETTINGS (hier anpassen)
# =========================
SETTINGS: Dict[str, Any] = {
    # Ordnernamen (genau, ohne Pfad) die NICHT bearbeitet / NICHT traversiert werden
    "EXCLUDE_FOLDERS": {
        ".git",
        "Python"
        "node_modules",
        ".venv",
        "__pycache__",
        ".obsidian",
        ".archive",
    },
    # Prefix für Ordner-Links unter #Folder, z. B. "Data-" -> [[Data-Unternehmertum]]
    "FOLDER_LINK_PREFIX": "",
    # Versteckte Elemente (beginnen mit ".") generell ignorieren?
    "IGNORE_DOT_ITEMS": True,
}

AUTOGEN_START = "<!-- AUTOGEN_START -->"
AUTOGEN_END = "<!-- AUTOGEN_END -->"


# ---------- Hilfsfunktionen ----------

def is_hidden(p: Path) -> bool:
    return SETTINGS["IGNORE_DOT_ITEMS"] and p.name.startswith(".")

def list_immediate(path: Path, excluded: set) -> Tuple[List[Path], List[Path], List[Path]]:
    subs = sorted([d for d in path.iterdir()
                   if d.is_dir() and not is_hidden(d) and d.name not in excluded],
                  key=lambda p: p.name.lower())
    mds  = sorted([f for f in path.iterdir()
                   if f.is_file() and f.suffix.lower()==".md" and not is_hidden(f)],
                  key=lambda p: p.name.lower())
    files= sorted([f for f in path.iterdir()
                   if f.is_file() and f.suffix.lower()!=".md" and not is_hidden(f)],
                  key=lambda p: p.name.lower())
    return subs, mds, files

def read_text_safe(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        # Fallback, falls Encoding daneben lag
        return p.read_text(errors="ignore")

def build_block(subfolders: List[Path], md_files: List[Path], other_files: List[Path],
                index_filename: str) -> str:
    parts: List[str] = [AUTOGEN_START]

    # #Folder
    folder_lines = []
    for d in subfolders:
        link_target = f"{SETTINGS['FOLDER_LINK_PREFIX']}{d.name}" if SETTINGS["FOLDER_LINK_PREFIX"] else d.name
        folder_lines.append(f"[[{link_target}]]")
    if folder_lines:
        parts.append("\n---\n#Folder")
        parts.extend(folder_lines)

    # #Markdown
    md_lines = []
    for f in md_files:
        if f.name == index_filename:
            continue  # nicht sich selbst einbetten
        md_lines.append(f"![[{f.name}]]")
    if md_lines:
        parts.append("\n---\n#Markdown")
        parts.extend(md_lines)

    # #Files
    file_lines = [f"![[{f.name}]]" for f in other_files]
    if file_lines:
        parts.append("\n---\n#Files")
        parts.extend(file_lines)

    parts.append(AUTOGEN_END)
    return ("\n".join(parts)).strip() + "\n"

def strip_placeholder_links(content: str) -> str:
    """
    Entfernt NUR einen Platzhalterblock mit leeren Links:
    # Links
    [[]]
    [[]]
    ...
    """
    pattern = re.compile(
        r"(^|\n)#{1,6}\s*Links\s*\n(?:\s*\[\[\]\]\s*\n?)+",
        flags=re.IGNORECASE
    )
    return re.sub(pattern, r"\\1", content)

def merge_content(existing: str, new_block: str) -> str:
    if not existing:
        return new_block
    cleaned = strip_placeholder_links(existing)
    if AUTOGEN_START in cleaned and AUTOGEN_END in cleaned:
        pattern = re.compile(
            re.escape(AUTOGEN_START) + r".*?" + re.escape(AUTOGEN_END),
            flags=re.DOTALL
        )
        merged = pattern.sub(new_block.strip(), cleaned)
        if not merged.endswith("\\n"):
            merged += "\\n"
        return merged
    else:
        sep = "" if cleaned.endswith("\\n\\n") else ("\\n" if cleaned.endswith("\\n") else "\\n\\n")
        return f"{cleaned}{sep}{new_block}"

def determine_index_name(dir_name: str) -> str:
    # Immer <Ordnername>.md (kein Sonderfall)
    return f"{dir_name}.md"

def has_autogen_block(p: Path) -> bool:
    try:
        text = read_text_safe(p)
    except Exception:
        return False
    return (AUTOGEN_START in text) and (AUTOGEN_END in text)

def remove_autogen_block_from_text(text: str) -> str:
    pattern = re.compile(
        re.escape(AUTOGEN_START) + r".*?" + re.escape(AUTOGEN_END),
        flags=re.DOTALL
    )
    cleaned = pattern.sub("", text).strip()
    if cleaned and not cleaned.endswith("\\n"):
        cleaned += "\\n"
    return cleaned

def remove_autogen_block_from_file(path: Path, dry_run: bool = False) -> None:
    content = read_text_safe(path)
    if AUTOGEN_START in content and AUTOGEN_END in content:
        cleaned = remove_autogen_block_from_text(content)
        if dry_run:
            print(f"[DRY][CLEAN] würde AUTOGEN-Block entfernen aus: {path}")
        else:
            path.write_text(cleaned, encoding="utf-8")
            print(f"[CLEAN] AUTOGEN-Block entfernt aus: {path}")

# ---------- Verarbeitung ----------

def choose_canonical_index(dir_path: Path, md_files: List[Path], expected_index: Path) -> Tuple[Path, List[Path]]:
    """
    Wählt die *kanonische* Index-Datei (die die AUTOGEN-Sektion tragen soll) und liefert
    zusätzlich die Liste aller weiteren Dateien, die fälschlich eine AUTOGEN-Sektion enthalten.
    """
    # Kandidaten mit AUTOGEN-Sektion
    candidates = [p for p in md_files if has_autogen_block(p)]

    # Falls erwartete Indexdatei existiert, priorisieren
    if expected_index.exists():
        canonical = expected_index
        duplicates = [p for p in candidates if p.resolve() != expected_index.resolve()]
        return canonical, duplicates

    # Keine Kandidaten -> erwartete Indexdatei wird neu gebaut
    if not candidates:
        return expected_index, []

    # Exakt ein Kandidat -> das ist der Kanon
    if len(candidates) == 1:
        return candidates[0], []

    # Mehrere Kandidaten -> bevorzugt die erwartete Namensdatei, sonst jüngste mtime
    for p in candidates:
        if p.name == expected_index.name:
            canonical = p
            duplicates = [q for q in candidates if q.resolve() != p.resolve()]
            return canonical, duplicates

    # Keine trägt den erwarteten Namen -> nimm die jüngste Datei als Kanon
    canonical = max(candidates, key=lambda p: p.stat().st_mtime)
    duplicates = [q for q in candidates if q.resolve() != canonical.resolve()]
    return canonical, duplicates

def process_dir(dir_path: Path, excluded: set, dry_run: bool = False):
    subs, mds, files = list_immediate(dir_path, excluded)

    expected_index_name = determine_index_name(dir_path.name)
    expected_index_path = dir_path / expected_index_name

    # 1) Kanonische Indexdatei wählen + Dubletten mit AUTOGEN erkennen
    canonical_path, duplicates = choose_canonical_index(dir_path, mds, expected_index_path)

    # 2) Falls Kanon nicht dem erwarteten Namen entspricht -> umbenennen
    if canonical_path.exists() and canonical_path.name != expected_index_name:
        target = expected_index_path
        if target.exists() and canonical_path.resolve() != target.resolve():
            # Konflikt: Ziel existiert bereits (unterschiedliche Datei)
            # Strategie: Ziel bleibt Kanon; AUTOGEN-Block aus der "alten" Datei entfernen
            if canonical_path in duplicates:
                # schon als Duplikat markiert; fällt unten heraus
                pass
            else:
                duplicates.append(canonical_path)
            canonical_path = target  # arbeite mit dem Ziel weiter
        else:
            # Umbenennen
            if dry_run:
                print(f"[DRY][RENAME] {canonical_path} -> {target}")
            else:
                canonical_path.rename(target)
                print(f"[RENAME] {canonical_path} -> {target}")
            canonical_path = target

    # 3) Sicherstellen: pro Ordner nur *eine* Datei mit AUTOGEN-Block -> aus Duplikaten Block entfernen
    for dup in duplicates:
        remove_autogen_block_from_file(dup, dry_run=dry_run)

    # 4) Nach evtl. Umbenennungen/Cleans: Verzeichnis-Inhalt neu erfassen
    subs, mds, files = list_immediate(dir_path, excluded)

    # 5) Block erzeugen und in die kanonische Datei mergen
    index_name = determine_index_name(dir_path.name)  # nach evtl. Umbenennung erneut bestimmen
    index_path = dir_path / index_name

    block = build_block(
        subfolders=subs,
        md_files=mds,
        other_files=files,
        index_filename=index_name,
    )

    existing = read_text_safe(index_path) if index_path.exists() else ""
    merged = merge_content(existing, block)

    if dry_run:
        action = "würde schreiben (update/erzeugen)"
        print(f"[DRY] {action}: {index_path}")
    else:
        index_path.write_text(merged, encoding="utf-8")
        print(f"[OK]  {index_path}")

def walk_all(root: Path, excluded: set, dry_run: bool = False):
    for dirpath, dirnames, filenames in os.walk(root):
        p = Path(dirpath)

        # Prune bevor Abstieg
        dirnames[:] = [
            d for d in dirnames
            if not (SETTINGS["IGNORE_DOT_ITEMS"] and d.startswith(".")) and d not in excluded
        ]

        # Falls doch in ausgeschlossenen/versteckten Ordner geraten -> überspringen
        if (SETTINGS["IGNORE_DOT_ITEMS"] and p.name.startswith(".")) or p.name in excluded:
            continue

        process_dir(p, excluded, dry_run=dry_run)

def main():
    parser = argparse.ArgumentParser(
        description="Erzeuge/aktualisiere Ordner-Index-Markdown-Dateien ab Startpunkt rekursiv nach unten.\n"
                    "Neue Logik: erkennt bestehende Index-Dateien via AUTOGEN-Block, benennt bei Ordner-Umbenennung korrekt um\n"
                    "und stellt sicher, dass je Ordner nur *eine* Datei den AUTOGEN-Block enthält."
    )
    parser.add_argument("root", nargs="?", default=Path("."), type=Path,
                        help="Startordner (Default: aktuelles Verzeichnis '.')")
    parser.add_argument("--dry-run", action="store_true", help="Nur Aktionen anzeigen (inkl. Rename/Clean), keine Schreibzugriffe.")
    args = parser.parse_args()

    root = args.root.resolve()
    if not root.exists() or not root.is_dir():
        raise SystemExit(f"Root nicht gefunden/kein Ordner: {root}")

    excluded = set(SETTINGS["EXCLUDE_FOLDERS"])

    walk_all(root, excluded, dry_run=args.dry_run)

if __name__ == "__main__":
    main()
