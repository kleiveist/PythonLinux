#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Folder listing CLI for Linux.
# Einheitliche Beispiele:
#   folderlist                       -> Standard: eine Datei 'FolderList.txt', Icons an, Tiefe 5
#   folderlist --3                   -> wie oben, aber Tiefe = 3
#   folderlist 3                     -> (weiterhin unterstützt) Tiefe = 3
#   folderlist --noic 3              -> Icons aus, Tiefe = 3
#   folderlist --no-files --4        -> nur Ordner, Tiefe = 4
#   folderlist --multi --3           -> erzeugt 1..3-FolderList.txt
#   folderlist --start .             -> starte in Pfad (Standard: aktuelles Verzeichnis)
#   folderlist --output out.txt      -> Name der Zieldatei im Einzeldatei-Modus

import argparse
import os
import sys
from typing import List, Dict, Optional, Tuple

ICON_MAP: Dict[str, str] = {
    '.py':        '🐍',
    '.ini':       '⚙️',
    '.html':      '🌐',
    '.css':       '🎨',
    '.js':        '📜',
    '.db':        '💾',
    '.txt':       '📝',
    '.md':        '📝',
    '.mp3':       '🎵',
    '.wav':       '🎶',
    '.flac':      '💽',
    '.ogg':       '🎧',
    '.m4a':       '🎼',
    '.wma':       '🎤',
    '.gitignore': '📝',
}
DEFAULT_FILE_ICON = '📄 '
DEFAULT_FOLDER_ICON = '📁 '

def actual_max_depth(root: str) -> int:
    max_d = 0
    for current, _dirs, _files in os.walk(root, topdown=True):
        rel = os.path.relpath(current, root)
        depth = 0 if rel == "." else rel.count(os.sep)
        if depth > max_d:
            max_d = depth
    return max_d

def _file_icon(name: str, icon_map: Optional[Dict[str, str]], default_icon: str) -> str:
    if not icon_map:
        return default_icon
    lname = name.lower()
    if lname in icon_map:
        return icon_map[lname]
    _base, ext = os.path.splitext(lname)
    return icon_map.get(ext, default_icon)

def build_tree(
    path: str,
    limit_depth: int,
    indent: str = "",
    depth: int = 0,
    use_icons: bool = True,
    folder_icon: str = DEFAULT_FOLDER_ICON,
    files_scan: bool = True,
    icon_map: Optional[Dict[str, str]] = None,
    default_file_icon: str = DEFAULT_FILE_ICON
) -> List[str]:
    if depth >= limit_depth:
        return []

    lines: List[str] = []
    try:
        all_entries = sorted(os.listdir(path))
    except PermissionError:
        return lines
    except FileNotFoundError:
        return lines

    dirs = [e for e in all_entries if os.path.isdir(os.path.join(path, e))]
    files = [e for e in all_entries if os.path.isfile(os.path.join(path, e))] if files_scan else []
    items = [('dir', d) for d in dirs] + [('file', f) for f in files]

    for i, (kind, entry) in enumerate(items):
        connector = "└── " if i == len(items) - 1 else "├── "
        if kind == 'dir':
            name = f"{folder_icon}{entry}" if use_icons and folder_icon else entry
            lines.append(indent + connector + name)
            new_indent = indent + ("    " if i == len(items) - 1 else "│   ")
            lines.extend(
                build_tree(
                    os.path.join(path, entry),
                    limit_depth,
                    new_indent,
                    depth + 1,
                    use_icons,
                    folder_icon,
                    files_scan,
                    icon_map,
                    default_file_icon
                )
            )
        else:
            ficon = _file_icon(entry, icon_map, default_file_icon) if use_icons else ""
            name = f"{ficon}{entry}" if ficon else entry
            lines.append(indent + connector + name)
    return lines

def write_structure(
    start_path: str,
    depth_limit: int,
    outfile: str,
    use_icons: bool = True,
    folder_icon: str = DEFAULT_FOLDER_ICON,
    files_scan: bool = True,
    icon_map: Optional[Dict[str, str]] = None,
    default_file_icon: str = DEFAULT_FILE_ICON
):
    icon = folder_icon if use_icons else ""
    root_name = os.path.basename(os.path.abspath(start_path)) or start_path
    lines = [f"{icon}{root_name}"]
    if depth_limit > 0:
        lines.extend(
            build_tree(
                start_path,
                depth_limit,
                use_icons=use_icons,
                folder_icon=folder_icon,
                files_scan=files_scan,
                icon_map=icon_map,
                default_file_icon=default_file_icon
            )
        )
    with open(outfile, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
        f.write("\n")

def _postprocess_unknown(unknown: list) -> Tuple[Optional[int], bool]:
    # Erlaube '--<zahl>' und '--noic' als unbekannte Optionen im Sinne der Kurzsyntax.
    depth_from_unknown: Optional[int] = None
    noic = False
    for u in unknown:
        if u.startswith("--") and u[2:].isdigit():
            depth_from_unknown = int(u[2:])
        elif u == "--noic":
            noic = True
        else:
            raise SystemExit(f"Unbekannte Option: {u}")
    return depth_from_unknown, noic

def parse_args(argv: list) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="folderlist",
        add_help=True,
        description="Erstellt eine textuelle Baumansicht des Verzeichnisses."
    )
    # Bewusst generisch: erlauben Positions-Tokens (z. B. '3' oder 'noic')
    parser.add_argument("tokens", nargs="*", help="Optionale freie Tokens: Tiefe (Zahl) und/oder 'noic'")
    parser.add_argument("--no-icons", "-N", action="store_true", help="Icons deaktivieren")
    parser.add_argument("--noic", action="store_true", dest="no_icons_alias", help="Alias für --no-icons")
    parser.add_argument("--files", dest="files", action=argparse.BooleanOptionalAction, default=True, help="Dateien auflisten (Standard: an). '--no-files' nur Ordner.")
    parser.add_argument("--multi", "-m", action="store_true", help="1..Tiefe-FolderList.txt erzeugen (statt einer Datei)")
    parser.add_argument("--output", "-o", default="FolderList.txt", help="Zieldateiname im Einzeldatei-Modus (Standard: FolderList.txt)")
    parser.add_argument("--start", "-s", default=".", help="Startpfad (Standard: aktuelles Verzeichnis)")
    parser.add_argument("--depth", "-d", type=int, default=None, help="Tiefe explizit setzen (überschreibt Token)")
    parser.add_argument("--max", type=int, default=5, help="Standard-Tiefe wenn keine Tiefe angegeben wurde (nur Einzeldatei-Modus). Default: 5")

    # parse_known_args erlaubt uns, "--3" als unknown einzusammeln
    args, unknown = parser.parse_known_args(argv)
    depth_from_unknown, noic_from_unknown = _postprocess_unknown(unknown)

    # frei eingegebene Tokens
    depth_from_token: Optional[int] = None
    noic_from_token = False
    for t in args.tokens:
        tl = t.lower()
        if tl in {"noic", "noicon", "noicons"}:
            noic_from_token = True
        else:
            try:
                depth_from_token = int(tl)
            except ValueError:
                raise SystemExit(f"Unbekanntes Token: '{t}'. Erlaubt: <Zahl> oder 'noic'.")

    # Zusammenführen der Tiefe-Präferenzen: --depth > --<zahl> > Token
    if args.depth is not None:
        depth_final = args.depth
    elif depth_from_unknown is not None:
        depth_final = depth_from_unknown
    else:
        depth_final = depth_from_token
    args.depth = depth_final

    # Icons-Flag zusammenführen (irgendein Hinweis deaktiviert Icons)
    args.no_icons = bool(args.no_icons or args.no_icons_alias or noic_from_unknown or noic_from_token)
    delattr(args, "no_icons_alias")

    return args

def main(argv: list) -> int:
    args = parse_args(argv)

    start_path = os.path.abspath(args.start)
    if not os.path.isdir(start_path):
        print(f"Fehler: Startpfad existiert nicht oder ist kein Verzeichnis: {start_path}", file=sys.stderr)
        return 2

    if args.multi:
        depth = args.depth if args.depth is not None else actual_max_depth(start_path)
        if depth <= 0:
            write_structure(start_path, 0, os.path.join(start_path, "0-FolderList.txt"),
                            use_icons=not args.no_icons, files_scan=args.files, icon_map=ICON_MAP)
            print("Erstellt: 0-FolderList.txt")
            return 0
        for d in range(1, depth + 1):
            outfile = os.path.join(start_path, f"{d}-FolderList.txt")
            write_structure(start_path, d, outfile,
                            use_icons=not args.no_icons, files_scan=args.files, icon_map=ICON_MAP)
            print(f"Erstellt: {os.path.basename(outfile)}")
        return 0
    else:
        depth = args.depth if args.depth is not None else args.max
        if depth < 0:
            print("Fehler: Tiefe muss >= 0 sein.", file=sys.stderr)
            return 2
        outfile = os.path.join(start_path, args.output)
        write_structure(start_path, depth, outfile,
                        use_icons=not args.no_icons, files_scan=args.files, icon_map=ICON_MAP)
        print(f"Erstellt: {os.path.basename(outfile)} in {start_path}")
        return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
