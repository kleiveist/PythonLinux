#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, re, tempfile
from pathlib import Path
from typing import List, Tuple, Dict

# ===== Einstellungen (einfach halten) =====
KEYS        = ["MuiChoi", "TextA1", "TextA2", "TransA3"]
MAX_POINTS  = 90  # 90-Punkte-Variante
PASS_PERCENT= 50
GRADE_THRESHOLDS = [  # Prozentgrenzen → (Icon, Note)
    (90, "🔵", 1),
    (80, "🟢", 2),
    (70, "🟡", 3),
    (50, "🟠", 4),
    (45, "🔴", 5),
]
ARCHIVE_DIR = ".archive"
BACKUP_DIR  = "backup"
BK_PREFIX   = "bk"
BK_MAX      = 9999
BK_PAD      = 4  # bk0001

# ===== Icons =====
I_FILE="📄"; I_SCAN="🔎"; I_OK="✅"; I_MISS="⚠️"; I_CALC="🧮"; I_WRITE="✍️"; I_SKIP="⛔"; I_BEGIN="🚫"; I_SUM="📊"

# ===== Bewertung =====
def status_icon(p:int):  return ("✅","Bestanden") if p>=PASS_PERCENT else ("❌","Nicht bestanden")
def grade_icon(p:int):
    for t,icon,note in GRADE_THRESHOLDS:
        if p>=t: return icon,note
    return "⚫",6

# ===== Regex =====
RESULT_PAT = re.compile(r'^\s*(Ergebnis|Prozent)\s*:', re.IGNORECASE)
FM_DELIM   = re.compile(r'^\s*---\s*$')
def key_pat(key:str) -> re.Pattern:
    # z.B. TextA1: '12'   # Kommentar
    return re.compile(rf'^\s*{re.escape(key)}\s*:\s*([\'"]?)(-?\d+)\1\s*(?:#.*)?$')

def find_frontmatter(lines:List[str]) -> Tuple[int,int] | None:
    if not lines or not FM_DELIM.match(lines[0]): return None
    for i in range(1,len(lines)):
        if FM_DELIM.match(lines[i]): return (0,i)
    return None

def parse_values(lines:List[str]) -> Dict[str,int]:
    values={}
    pats={k:key_pat(k) for k in KEYS}
    for ln in lines:
        for k,pat in pats.items():
            m=pat.match(ln)
            if m:
                try: values[k]=int(m.group(2))
                except: pass
    return values

def build_result(total:int):
    percent = round((total / MAX_POINTS) * 100) if MAX_POINTS>0 else 0
    if total==0 and percent==0:
        return f'Ergebnis: 0 | {I_BEGIN} Nicht begonnen\n', 'Prozent: 0% | ⚪ 0\n', percent
    si,st = status_icon(percent)
    gi,gn = grade_icon(percent)
    return f'Ergebnis: {total} | {si} {st}\n', f'Prozent: {percent}% | {gi} {gn}\n', percent

# ===== Backup-Handling in .archive/backup/bkXXXX =====
def ensure_dirs(base:Path) -> Path:
    archive = base / ARCHIVE_DIR
    backup_root = archive / BACKUP_DIR
    archive.mkdir(exist_ok=True)
    backup_root.mkdir(parents=True, exist_ok=True)
    return backup_root

def get_or_create_session_dir(backup_root:Path) -> Path:
    session_marker = backup_root.parent / ".current_session"  # liegt in .archive
    # Reuse: vorhandene Session-Nummer?
    if session_marker.exists():
        try:
            n = int(session_marker.read_text(encoding="utf-8").strip())
            if 1 <= n <= BK_MAX:
                d = backup_root / f"{BK_PREFIX}{n:0{BK_PAD}d}"
                d.mkdir(parents=True, exist_ok=True)
                return d
        except Exception:
            pass
    # Neu: finde nächste Nummer
    nums = []
    for child in backup_root.iterdir():
        if child.is_dir() and child.name.startswith(BK_PREFIX):
            s = child.name[len(BK_PREFIX):]
            if s.isdigit():
                nums.append(int(s))
    n = (max(nums) + 1) if nums else 1
    if n > BK_MAX: n = 1  # wrap-around
    d = backup_root / f"{BK_PREFIX}{n:0{BK_PAD}d}"
    d.mkdir(parents=True, exist_ok=True)
    # Session-Nummer merken
    (backup_root.parent / ".current_session").write_text(str(n), encoding="utf-8")
    return d

def write_backup(original_path:Path, session_dir:Path, base_dir:Path):
    # relative Struktur beibehalten (falls später Unterordner kommen)
    try:
        rel = original_path.relative_to(base_dir)
    except ValueError:
        rel = original_path.name
    dest = session_dir / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    data = original_path.read_text(encoding="utf-8")
    dest.write_text(data, encoding="utf-8")  # überschreibt bestehende Backups in derselben Session

# ===== Schreiben (atomar ins Original) =====
def atomic_write(path:Path, data:str):
    with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8", dir=str(path.parent)) as tmp:
        tmp.write(data); tmp_path=Path(tmp.name)
    tmp_path.replace(path)

# ===== Datei-Verarbeitung =====
def process_file(path:Path, session_dir:Path, base_dir:Path):
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)

    fm = find_frontmatter(lines)
    scan = lines[(fm[0]+1):fm[1]] if fm else lines
    values = parse_values(scan)

    found_count = sum(1 for k in KEYS if k in values)
    total = sum(values.get(k,0) for k in KEYS)
    erg, proz, percent = build_result(total)

    if found_count == 0:
        print(f"{I_FILE}  Datei: {path}")
        print(f"   {I_SCAN}  Keys gescannt:")
        for k in KEYS: print(f"      {I_MISS}  {k}: —")
        print(f"   {I_CALC}  Summe: 0/{MAX_POINTS} → 0%")
        print(f"   {I_SKIP}  Übersprungen: keine Keys gefunden\n")
        return False

    # Ergebnis/Prozent-Zeilen entfernen & neu einfügen (vor erster Key-Zeile)
    if fm:
        start,end = fm
        block = [ln for ln in lines[start+1:end] if not RESULT_PAT.match(ln)]
        idx=None
        for i,ln in enumerate(block):
            if any(key_pat(k).match(ln) for k in KEYS): idx=i; break
        if idx is None: block = [erg,proz]+block
        else:           block = block[:idx]+[erg,proz]+block[idx:]
        new_lines = lines[:start+1]+block+lines[end:]
    else:
        filtered = [ln for ln in lines if not RESULT_PAT.match(ln)]
        idx=None
        for i,ln in enumerate(filtered):
            if any(key_pat(k).match(ln) for k in KEYS): idx=i; break
        if idx is None: filtered = [erg,proz]+filtered
        else:           filtered = filtered[:idx]+[erg,proz]+filtered[idx:]
        new_lines = filtered

    new_text = "".join(new_lines)
    changed = (new_text != text)

    if changed:
        # Backup in Session-Ordner schreiben, dann Original aktualisieren
        write_backup(path, session_dir, base_dir)
        atomic_write(path, new_text)

    # Konsole
    print(f"{I_FILE}  Datei: {path}")
    print(f"   {I_SCAN}  Keys gescannt:")
    for k in KEYS:
        v = values.get(k)
        print(f"      {(I_OK if v is not None else I_MISS)}  {k}: {v if v is not None else '—'}")
    print(f"   {I_CALC}  Summe: {total}/{MAX_POINTS} → {percent}%")
    print(f"   {(I_WRITE if changed else I_SKIP)}  {'Ergebnis/Prozent aktualisiert' if changed else 'keine Änderungen nötig'}\n")
    return changed

def main():
    # Im Skriptordner arbeiten
    script_dir = Path(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(script_dir)

    # Backup-Struktur anlegen und Session-Verzeichnis bestimmen
    backup_root = ensure_dirs(script_dir)
    session_dir = get_or_create_session_dir(backup_root)

    # Nur .md im selben Ordner
    md_files = [p for p in sorted(script_dir.iterdir()) if p.is_file() and p.suffix.lower()==".md"]

    changed = 0
    for p in md_files:
        try:
            if process_file(p, session_dir, script_dir): changed += 1
        except Exception as e:
            print(f"❌ Fehler in {p}: {e}")

    print(f"{I_SUM}  Zusammenfassung: geändert: {changed} / gesamt: {len(md_files)}")
    print(f"     Backups: {session_dir}")

if __name__ == "__main__":
    main()
