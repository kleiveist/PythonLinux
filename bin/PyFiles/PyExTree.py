#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tree2fs.py  –  Version 2025‑04‑18

Erstellt Ordner‑/Dateistrukturen aus Textdateien, die eine `tree`‑ähnliche
Darstellung (Unicode oder ASCII) enthalten.

Features
~~~~~~~~
* **Emoji‑Icons** (📁, 📄 …) werden ignoriert.
* **InTree.txt** wird als ganze Datei übersprungen (case‑insensitiv).
* Die Routemap‑Dateien können an beliebiger Stelle Zeilen für
  **ExTree.py** oder **InTree.py** enthalten – diese beiden Dateien werden
  grundsätzlich nicht angelegt.
* Nummerierung ist standardmäßig ausgeschaltet (Schalter `-n`).
"""
from __future__ import annotations

import argparse
import os
import re
from typing import List, Optional, Tuple

###########################
# Globale Ausschlusslisten
###########################
EXCLUDED_TXT = {"intree.txt"}                  # wird gar nicht eingelesen
SKIP_NODES = {"intree.py", "extree.py"}         # werden nicht materialisiert

###########################
# Parsing‑Utilities
###########################

CONNECT_RE = re.compile(r"(├[─-]+|└[─-]+|\+--|\|--|`--)")
SEPARATOR_RE = re.compile(r"^[│|]+\s*$")            # reine Pipes/Striche
EMOJI_RE = re.compile(r"^[📁📄]+\s*")                # Icons am Zeilenanfang


def _clean(line: str) -> str:
    """Entfernt Kommentare (ab '#') und end‑of‑line‑Whitespace."""
    return line.split("#", 1)[0].rstrip("\n\r").rstrip()


def _parse_line(line: str, seen_root: bool) -> Tuple[Optional[int], Optional[str]]:
    """Liefert (level, name) oder (None, None) für irrelevante Zeilen."""
    line = _clean(line)
    if not line or SEPARATOR_RE.match(line):
        return None, None

    m = CONNECT_RE.search(line)
    if m:
        level = m.start() // 4 + 1
        name = line[m.end() :].strip()
    else:
        if seen_root:
            return None, None  # weitere Kopfzeilen ignorieren
        level, name = 0, line.strip()

    name = EMOJI_RE.sub("", name)  # Emojis weg
    return level, name

###########################
# Routemap → Speicherbaum
###########################

def build_tree(lines: List[str]):
    items, stack = [], []  # stack: (level, idx)
    seen_root = False

    for raw in lines:
        level, name = _parse_line(raw, seen_root)
        if name is None:
            continue
        if level == 0:
            seen_root = True

        is_folder = name.endswith("/")
        if is_folder:
            name = name[:-1]

        # vollständiger Zeilenausschluss
        if not is_folder and name.lower() in SKIP_NODES:
            continue

        # Elternreferenz ermitteln
        while stack and stack[-1][0] >= level:
            stack.pop()
        parent = stack[-1][1] if stack else None

        idx = len(items)
        items.append(
            {
                "level": level,
                "raw_name": name,
                "is_folder": is_folder,
                "parent": parent,
                "children": [],
                "final_name": name,  # wird evtl. nummeriert
            }
        )
        if parent is not None:
            items[parent]["children"].append(idx)
        stack.append((level, idx))

    return items

###########################
# Optionale Nummerierung
###########################

def assign_numbering(items):
    roots = [i for i, it in enumerate(items) if it["parent"] is None]
    for r in roots:
        _number_children(items, r)


def _number_children(items, parent):
    counter = 1
    for idx in items[parent]["children"]:
        ch = items[idx]
        if ch["is_folder"] and not ch["raw_name"].startswith("_"):
            ch["final_name"] = f"{counter:02d}{ch['raw_name']}"
            counter += 1
        if ch["is_folder"]:
            _number_children(items, idx)

###########################
# Namenskollisionen lösen
###########################

def unique_path(parent: str, name: str) -> str:
    path = os.path.join(parent, name)
    if not os.path.exists(path):
        return path

    # Versions‑Mechanismus für V‑Dateien
    if name.startswith("V"):
        m = re.match(r"^(V((?:\d+(?:\.\d+)*)))([-_ ]?)(.*)$", name)
        if m:
            nums, sep, rest = m.group(2), m.group(3), m.group(4)
            parts = nums.split(".")
            if len(parts) == 1:  # V1 → V2 … V100
                start = int(parts[0])
                for i in range(start + 1, 101):
                    cand = os.path.join(parent, f"V{i}{sep}{rest}")
                    if not os.path.exists(cand):
                        return cand
            else:
                last = int(parts[-1])
                if last < 9:
                    parts[-1] = str(last + 1)
                    cand = os.path.join(parent, f"V{'.'.join(parts)}{sep}{rest}")
                    if not os.path.exists(cand):
                        return cand

    # Fallback: Name01 … Name99
    for i in range(1, 100):
        cand = os.path.join(parent, f"{name}{i:02d}")
        if not os.path.exists(cand):
            return cand

    raise RuntimeError(f"Kein eindeutiger Name für {name}")

###########################
# Baum materialisieren
###########################

def create_fs(items):
    roots = [i for i, it in enumerate(items) if it["parent"] is None]
    for r in roots:
        _emit(items, r, os.getcwd())


def _emit(items, idx, parent_path):
    node = items[idx]
    tgt = unique_path(parent_path, node["final_name"])

    if node["is_folder"]:
        os.makedirs(tgt, exist_ok=True)
        print(f"Ordner: {tgt}")
        for c in node["children"]:
            _emit(items, c, tgt)
    else:
        os.makedirs(os.path.dirname(tgt), exist_ok=True)
        open(tgt, "w", encoding="utf-8").close()
        print(f"Datei : {tgt}")

###########################
# Hauptprogramm
###########################

def process(txt: str, numbering: bool):
    with open(txt, "r", encoding="utf-8") as fh:
        lines = fh.readlines()

    tree = build_tree(lines)
    if not tree:
        print(f"{txt}: keine verwertbaren Einträge – übersprungen.")
        return

    if numbering:
        assign_numbering(tree)

    create_fs(tree)


def main():
    ap = argparse.ArgumentParser(description="Tree‑Textdateien in Ordner/Dateien umsetzen")
    ap.add_argument("-n", "--numbering", action="store_true", help="zweistellige Nummernpräfixe für Geschwisterordner hinzufügen")
    args = ap.parse_args()

    txts = [f for f in os.listdir(".") if f.lower().endswith(".txt") and f.lower() not in EXCLUDED_TXT]
    if not txts:
        print("Keine passenden .txt‑Dateien gefunden.")
        return

    for txt in txts:
        print(f"\n>>> {txt}")
        process(txt, args.numbering)


if __name__ == "__main__":
    main()
