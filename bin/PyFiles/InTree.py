#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dieses Skript durchsucht rekursiv Projektordner und schreibt die Ordner- und Dateistruktur
in jeweils eine "InTree.txt"-Datei pro Projekt.
Optional (bei CONTENT_CRAWL=True) wird zusätzlich eine "InContent.txt" angelegt, die die Struktur
und den Code-/Textinhalt enthält.

Einstellungen:
- INCLUDE_FILES: Sollen Dateien in der Struktur-Ausgabe erscheinen?
- USE_ICONS: Unicode‑Symbole für Dateien/Ordner verwenden?
- CONTENT_CRAWL: Inhalte definierter Datei­typen in "InContent.txt" anhängen (True/False)?
- EXCLUDE_DIRS: Liste von Ordnernamen, die übersprungen werden sollen.
- EXCLUDE_FILES: Liste von Dateinamen (mit Endung), die übersprungen werden sollen.
- CONTENT_EXTENSIONS: Dateiendungen, deren Inhalt in die Ausgabe übernommen wird.
- USE_PROJECT_PATHS: Projektpfade aus den Einstellungen verwenden (True/False)?
- PROJECT_PATHS: Liste von Projekt­unterordnern (relativ zum Skript­verzeichnis).
"""
import os
import sys

# -------- Einstellungen --------
INCLUDE_FILES    = True
USE_ICONS        = True
CONTENT_CRAWL    = False
EXCLUDE_DIRS     = [
    ".git",
    "__pycache__",
    "_InTree",
    "venv",
    "250422",
]
EXCLUDE_FILES    = [
    "InTree.py",
    "InTree.txt",
]
CONTENT_EXTENSIONS = {'.py', '.md', '.txt', '.js', '.html', '.css'}

USE_PROJECT_PATHS = False  # Projektpfade aus SETTINGS verwenden?
PROJECT_PATHS     = [   # relativ zum Skriptverzeichnis
    'P25AutoChat/AutoChat',
    'P25AutoChat/MyAutoChat',
    'P25Images_extract/ImagesExtract',
]
# --------------------------------

# Icon-Mapping basierend auf Datei-Extension
ICON_MAP = {
    '.py':        '🐍',
    '.html':      '🌐',
    '.css':       '🎨',
    '.js':        '📜',
    '.db':        '💾',
    '.txt':       '📝',
    '.md':        '📝',
    '.gitignore': '📝',
}
FOLDER_ICON = '📂'
DEFAULT_FILE_ICON = '📄'

def get_icon_for_file(filename):
    if filename == '.gitignore':
        return ICON_MAP['.gitignore']
    _, ext = os.path.splitext(filename)
    return ICON_MAP.get(ext.lower(), DEFAULT_FILE_ICON)


def generate_tree_lines(base_path, prefix=''):
    lines = []
    try:
        entries = sorted(os.listdir(base_path))
    except PermissionError:
        return lines

    # Filter Ordner und Dateien
    filtered = [
        e for e in entries
        if not ((os.path.isdir(os.path.join(base_path, e)) and e in EXCLUDE_DIRS)
                or (os.path.isfile(os.path.join(base_path, e)) and e in EXCLUDE_FILES))
    ]
    count = len(filtered)

    for idx, entry in enumerate(filtered):
        entry_path = os.path.join(base_path, entry)
        is_last = (idx == count - 1)
        connector = '└── ' if is_last else '├── '

        if os.path.isdir(entry_path):
            icon = (FOLDER_ICON + ' ') if USE_ICONS else ''
            lines.append(prefix + connector + icon + f'{entry}/')
            indent = '    ' if is_last else '│   '
            lines.extend(generate_tree_lines(entry_path, prefix + indent))
        elif INCLUDE_FILES and os.path.isfile(entry_path):
            icon = (get_icon_for_file(entry) + ' ') if USE_ICONS else ''
            lines.append(prefix + connector + icon + entry)
    return lines


def write_tree(base_path):
    # Schreibe nur Verzeichnisstruktur in InTree.txt
    tree_file = os.path.join(base_path, 'InTree.txt')
    root_name = os.path.basename(os.path.abspath(base_path))
    icon = (FOLDER_ICON + ' ') if USE_ICONS else ''
    lines = [f'{icon}{root_name}'] + generate_tree_lines(base_path)
    with open(tree_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f'InTree erstellt: {tree_file}')


def write_content(base_path):
    # Schreibe Struktur + Inhalte in InContent.txt
    content_file = os.path.join(base_path, 'InContent.txt')
    root_name = os.path.basename(os.path.abspath(base_path))
    icon = (FOLDER_ICON + ' ') if USE_ICONS else ''
    lines = [f'{icon}{root_name}'] + generate_tree_lines(base_path)
    with open(content_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
        f.write('\n\n=== Datei-Inhalte ===\n\n')
        for root, dirs, files in os.walk(base_path):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for file in sorted(files):
                if file in EXCLUDE_FILES:
                    continue
                ext = os.path.splitext(file)[1].lower()
                if ext in CONTENT_EXTENSIONS or file == '.gitignore':
                    path = os.path.join(root, file)
                    rel_path = os.path.relpath(path, base_path)
                    icon_f = get_icon_for_file(file) + ' ' if USE_ICONS else ''
                    f.write(f"{icon_f}--- {rel_path} ---\n")
                    try:
                        with open(path, 'r', encoding='utf-8', errors='replace') as cf:
                            f.write(cf.read())
                    except Exception as e:
                        f.write(f"[Fehler beim Lesen: {e}]\n")
                    f.write('\n')
    print(f'InContent erstellt: {content_file}')


if __name__ == '__main__':
    script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    targets = []
    if USE_PROJECT_PATHS:
        for rel in PROJECT_PATHS:
            proj = os.path.join(script_dir, rel)
            if os.path.isdir(proj):
                targets.append(proj)
            else:
                print(f'Projektpfad nicht gefunden: {proj}')
    else:
        targets = [os.getcwd()]

    for base in targets:
        print(f'Bearbeite Projekt: {base}')
        write_tree(base)
        if CONTENT_CRAWL:
            write_content(base)
