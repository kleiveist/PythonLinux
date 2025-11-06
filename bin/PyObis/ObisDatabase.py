#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YAML-Frontmatter-Manager (v5)

NEU (zur Pfadlogik):
- %rootN%: Zählt **vom Start-Root/Anker nach unten** entlang des Datei-Pfades.
  • %root0% = Name des Start-Roots (oder des Ankers, s.u.)
  • %root1% = 1. Unterordner unterhalb Start-Root auf dem Weg zur Datei, usw.
  • Fallback: Ist N größer als die tatsächliche Tiefe, wird %root0% verwendet.
- _settings.base_root: "<Ordnername>" ankert die Zählung (und optional den Scope) unterhalb dieses Ordners.
- _settings.scope_under_base_root: true → verarbeite **nur** Dateien unterhalb des Ankers.

Bestehendes bleibt:
- %folder%: Name des Start-Roots (Alias: %root0%)
- %folderN%: Zählt **von der Datei nach oben** (Elternordner). Fallback: %folder0%
- %datum% / %date%: Erstellungsdatum (YYYY-MM-DD)
- %data%: Dateiname der .md ohne Erweiterung
- %wert%: vorhandenen Wert beibehalten (nur Felder); wenn nicht vorhanden → Key nicht anlegen
- =leer=: Mapping → leeres Feld ""; Liste → Element entfernen
- _settings.key_mode: strict|merge; _settings.keep_extra_keys: [Globs]
- _settings.exclude_folders: [Ordner/Globs]

Reihenfolge: Felder werden **in der Reihenfolge der YAML.ini** ausgegeben. In strict werden nicht genannte Keys entfernt (außer Whitelist).

Voraussetzung: PyYAML (pip install pyyaml)
"""
from __future__ import annotations

import argparse
import datetime
import fnmatch
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    sys.stderr.write("[FEHLER] PyYAML nicht installiert. Bitte ausführen: pip install pyyaml\n")
    raise

# ======================= Konstanten =======================
CONFIG_FILENAMES = ("ObisDatabase.ini", "ObisDatabase-Timetable.ini", "ObisDatabase-Klausur.ini", "ObisDatabase-Skript.ini", "YAML.ini")
FRONTMATTER_DELIM = "---"
SENTINEL_EMPTY = "=leer="
KEEP_TOKEN = "%wert%"
FOLDER_N_RE = re.compile(r"%folder(\d+)%")      # aufwärts (von Datei)
ROOT_N_RE = re.compile(r"%root(\d+)%")          # abwärts (vom Start-Root/Anker)

class _KEEP:  # Marker für %wert%
    pass

KEEP_EXISTING = _KEEP()

# ======================= Hilfsfunktionen =======================

def get_creation_date(p: Path) -> str:
    """YYYY-MM-DD; bevorzugt st_birthtime (macOS/Windows), sonst st_mtime (Linux)."""
    st = p.stat()
    try:
        ts = st.st_birthtime  # type: ignore[attr-defined]
    except AttributeError:
        ts = st.st_mtime
    return datetime.date.fromtimestamp(ts).isoformat()


def read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def write_text(p: Path, content: str) -> None:
    p.write_text(content, encoding="utf-8", newline="\n")

# ======================= Settings =======================

@dataclass
class Settings:
    exclude_folders: Tuple[str, ...] = (
        ".git",
        "Python",
        "node_modules",
        ".obsidian",
        ".venv",
        "__pycache__",
    )
    key_mode: str = "strict"            # oder "merge"
    keep_extra_keys: Tuple[str, ...] = ()
    base_root: str | None = None         # Anker-Ordnername unterhalb --root
    scope_under_base_root: bool = False  # nur Dateien unterhalb des Ankers verarbeiten
    # NEU: selektive Verarbeitung nach Ordnernamen (abschaltbar)
    include_folders_by_name: Tuple[str, ...] = ()
    selective_processing_active: bool = False

    @staticmethod
    def from_cfg(cfg: Dict[str, Any]) -> "Settings":
        s = cfg.get("_settings", {}) or {}
        excl = tuple(s.get("exclude_folders", []) or []) or Settings().exclude_folders
        key_mode = str(s.get("key_mode", "strict")).strip().lower()
        if key_mode not in {"strict", "merge"}:
            key_mode = "strict"
        keep_extra = tuple(s.get("keep_extra_keys", []) or [])
        base_root = s.get("base_root")
        scope_under = bool(s.get("scope_under_base_root", False))
        include_only = tuple(s.get("include_folders_by_name", []) or [])
        selective_on = bool(s.get("selective_processing_active", False))
        return Settings(
            exclude_folders=excl,
            key_mode=key_mode,
            keep_extra_keys=keep_extra,
            base_root=base_root,
            scope_under_base_root=scope_under,
            include_folders_by_name=include_only,
            selective_processing_active=selective_on,
        )

# ======================= YAML-INI Laden =======================

def load_config(root: Path) -> Tuple[Settings, Dict[str, Any]]:
    ini_path: Path | None = None
    for name in CONFIG_FILENAMES:
        candidate = root / name
        if candidate.is_file():
            ini_path = candidate
            break
    if ini_path is None:
        opts = " oder ".join(CONFIG_FILENAMES)
        sys.stderr.write(f"[FEHLER] Keine Konfigurationsdatei gefunden ({opts}) in {root}\n")
        sys.exit(2)

    # Vorab: YAML verbietet Tabs -> klare Fehlermeldung statt kryptischem ScannerError
    raw_ini = ini_path.read_text(encoding="utf-8")
    if "\t" in raw_ini:
        sys.stderr.write(f"[FEHLER] Tabs in {ini_path.name} gefunden. YAML erlaubt keine Tabs. Ersetze Tabs durch Spaces.\n")
        sys.exit(2)
    try:
        cfg: Dict[str, Any] = yaml.safe_load(raw_ini) or {}
    except yaml.YAMLError as e:  # pragma: no cover
        sys.stderr.write(f"[FEHLER] {ini_path.name} ist keine gültige YAML-Datei: {e}\n")
        sys.exit(2)

    settings = Settings.from_cfg(cfg)
    # Frontmatter-Vorlage: nur Keys ohne führenden Unterstrich (Reihenfolge bleibt erhalten)
    template = {k: v for k, v in cfg.items() if not str(k).startswith("_")}
    return settings, template

# ======================= Frontmatter Parser =======================

def split_frontmatter(text: str) -> Tuple[Dict[str, Any], str]:
    if not text.startswith(FRONTMATTER_DELIM):
        return {}, text
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != FRONTMATTER_DELIM:
        return {}, text
    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() in (FRONTMATTER_DELIM, "..."):
            end_idx = i
            break
    if end_idx is None:
        return {}, text
    fm_text = "".join(lines[1:end_idx])
    body = "".join(lines[end_idx + 1 :])
    try:
        data = yaml.safe_load(fm_text) or {}
        if not isinstance(data, dict):
            data = {}
    except yaml.YAMLError:
        data = {}
    return data, body


def dump_frontmatter(data: Dict[str, Any]) -> str:
    payload = yaml.safe_dump(
        data,
        allow_unicode=True,
        sort_keys=False,          # Reihenfolge beibehalten
        default_flow_style=False,
    )
    return f"{FRONTMATTER_DELIM}\n{payload}{FRONTMATTER_DELIM}\n\n"

# ======================= Pfad-Hilfen =======================

def compute_folder_levels_up(md_path: Path) -> List[str]:
    """[folder0, folder1, folder2, ...] = Elternordner von der Datei aus nach oben."""
    levels: List[str] = []
    cur = md_path.parent
    while True:
        levels.append(cur.name)
        parent = cur.parent
        if parent == cur:
            break
        cur = parent
    return [x for x in levels if x]


def compute_root_parts_down(base: Path, md_parent: Path) -> List[str]:
    """[root1, root2, ...] = Pfadteile von base → md_parent. root0 = base.name."""
    try:
        rel = md_parent.resolve().relative_to(base.resolve())
    except Exception:
        return []
    return list(rel.parts)  # kann leer sein (Datei liegt direkt unter base)

# ======================= Platzhalter & Transform =======================

def _subst_scalar(
    val: str,
    *,
    exec_base: Path,
    exec_root_name: str,
    folder_levels_up: List[str],
    root_parts_down: List[str],
    file_date: str,
    file_stem: str,
    file_name: str,
) -> Any:
    """Ersetzt Platzhalter in einem String.
    Rückgabe: str | KEEP_EXISTING | None (bei =leer=)
    """
    if val == SENTINEL_EMPTY:
        return None
    if val == KEEP_TOKEN:
        return KEEP_EXISTING

    out = val

    # Datum/Alias
    out = out.replace("%datum%", file_date).replace("%date%", file_date)
    # Dateiname
    out = out.replace("%data%", file_stem)

    # Aliasse für Root-Name
    out = out.replace("%folder%", exec_root_name)
    out = out.replace("%root0%", exec_root_name)

    # Aufwärts (%folderN%)
    def repl_up(m: re.Match[str]) -> str:
        idx = int(m.group(1))
        if not folder_levels_up:
            return ""
        return folder_levels_up[idx] if idx < len(folder_levels_up) else folder_levels_up[0]

    out = FOLDER_N_RE.sub(repl_up, out)

    # Abwärts (%rootN%)
    def repl_down(m: re.Match[str]) -> str:
        idx = int(m.group(1))
        if idx == 0:
            return exec_root_name
        if not root_parts_down:
            return exec_root_name
        # %root1% ist root_parts_down[0]
        return root_parts_down[idx - 1] if (idx - 1) < len(root_parts_down) else exec_root_name

    out = ROOT_N_RE.sub(repl_down, out)

    return out


def apply_template(
    template: Any,
    *,
    exec_base: Path,
    exec_root_name: str,
    folder_levels_up: List[str],
    root_parts_down: List[str],
    file_date: str,
    file_stem: str,
    file_name: str,
) -> Any:
    if isinstance(template, dict):
        out: Dict[str, Any] = {}
        for k, v in template.items():
            new_v = apply_template(
                v,
                exec_base=exec_base,
                exec_root_name=exec_root_name,
                folder_levels_up=folder_levels_up,
                root_parts_down=root_parts_down,
                file_date=file_date,
                file_stem=file_stem,
                file_name=file_name,
            )
            if new_v is None:
                out[k] = ""  # =leer= in Mappings -> leeres Feld
            else:
                out[k] = new_v
        return out

    if isinstance(template, list):
        out_list = []
        for item in template:
            new_item = apply_template(
                item,
                exec_base=exec_base,
                exec_root_name=exec_root_name,
                folder_levels_up=folder_levels_up,
                root_parts_down=root_parts_down,
                file_date=file_date,
                file_stem=file_stem,
                file_name=file_name,
             
            )
        
            if new_item is None:
                continue  # =leer= in Listen -> Element verwerfen
            if new_item is KEEP_EXISTING:
                # %wert% in Listen-Elementen ist uneindeutig -> ignorieren (Element weglassen)
                continue
            out_list.append(new_item)
        return out_list

    if isinstance(template, str):
        return _subst_scalar(
            template,
            exec_base=exec_base,
            exec_root_name=exec_root_name,
            folder_levels_up=folder_levels_up,
            root_parts_down=root_parts_down,
            file_date=file_date,
            file_stem=file_stem,
            file_name=file_name,
        )

    # andere Typen (int/bool/None) unverändert
    return template

# ======================= Merge/Build-Strategie =======================

def resolve_renames(applied: Dict[str, Any], existing: Dict[str, Any]) -> Tuple[Dict[str, Any], set[str]]:
    """
    Interpretiert Template-Keys der Form 'ALT/NEU'.
    - Nur sinnvoll mit %wert% (wird bereits als KEEP_EXISTING markiert).
    - Überträgt vorhandenen Wert von existing[ALT] (Fallback: existing[NEU]) nach Key 'NEU'.
    - ALT wird als zu löschender Key markiert (auch in key_mode=merge).
    - Keys ohne '/' bleiben unverändert.
    """
    out: Dict[str, Any] = {}
    drop_sources: set[str] = set()
    for k, v in applied.items():
        if "/" in k:
            src, dst = k.split("/", 1)
            src, dst = src.strip(), dst.strip()
            drop_sources.add(src)
            if v is KEEP_EXISTING:
                if src in existing:
                    out[dst] = existing[src]
                elif dst in existing:
                    out[dst] = existing[dst]
                else:
                    # Weder ALT noch NEU vorhanden -> nichts anlegen
                    pass
            else:
                # Falls jemand doch einen anderen Wert einträgt: direkt zuweisen
                out[dst] = v
        else:
            out[k] = v
    return out, drop_sources

def should_keep_extra_key(key: str, keep_patterns: Tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatch(key, pat) for pat in keep_patterns)


def build_result(existing: Dict[str, Any], applied: Dict[str, Any], *, key_mode: str, keep_extra: Tuple[str, ...]) -> Dict[str, Any]:
    """Konstruiert das finale Frontmatter **in Template-Reihenfolge**.
    - %wert%: vorhandenen Wert behalten; wenn nicht vorhanden -> Key auslassen
    - strict: nur Template-Keys; merge: plus restliche existing-Keys (am Ende, Original-Reihenfolge)
    - keep_extra_keys (nur sinnvoll in strict): lässt ausgewählte Keys trotz strict stehen
    """
    result: Dict[str, Any] = {}

    # 1) Template-Keys in Reihenfolge verarbeiten
    for k, v in applied.items():
        if v is KEEP_EXISTING:
            if k in existing:
                result[k] = existing[k]
            else:
                # nicht anlegen
                continue
        else:
            result[k] = v

    # 2) Zusätzliche Keys
    if key_mode == "merge":
        for k, v in existing.items():
            if k not in result:
                result[k] = v
    else:  # strict
        if keep_extra:
            for k, v in existing.items():
                if k not in result and should_keep_extra_key(k, keep_extra):
                    result[k] = v

    return result

# ======================= Exklusionslogik =======================

def is_excluded(md_path: Path, exclude_folders: Iterable[str]) -> bool:
    parts = [p.name for p in md_path.parents]
    for pat in exclude_folders:
        for name in parts:
            if fnmatch.fnmatch(name, pat):
                return True
    return False


# ======================= Selektions-/Anker-Helfer =======================
def nearest_named_ancestor(dir_path: Path, names: Iterable[str]) -> Path | None:
    """Nächster Vorfahr (inkl. dir_path) mit Name in 'names', sonst None."""
    name_set = set(names)
    for d in [dir_path, *dir_path.parents]:
        if d.name in name_set:
            return d
    return None

def has_excluded_child_folder(dir_path: Path, exclude_folders: Iterable[str]) -> bool:
    """
    Prüft, ob der gegebene Ordner einen DIREKTEN Unterordner hat, dessen Name in 'exclude_folders' matcht.
    Achtung: absichtliche Beschränkung auf unmittelbare Kinder, um false positives zu vermeiden.
    """
    try:
        child_dirs = [p.name for p in dir_path.iterdir() if p.is_dir()]
    except FileNotFoundError:
        return False
    for pat in exclude_folders:
        for name in child_dirs:
            if fnmatch.fnmatch(name, pat):
                return True
    return False
 
# ======================= Hauptlogik =======================
def find_anchor_by_name(exec_base: Path, md_path: Path, anchor_name: str) -> Path | None:
    p = md_path.parent.resolve()
    eb = exec_base.resolve()
    # nur innerhalb des --root suchen
    for ancestor in [p, *p.parents]:
        if ancestor == eb.parent:  # außerhalb von --root stoppen
            break
        if ancestor.name == anchor_name:
            return ancestor
    return None

def process_md(md_path: Path, template: Dict[str, Any], *, exec_base: Path, settings: Settings) -> bool:
    text = read_text(md_path)
    existing, body = split_frontmatter(text)

    # Anker bestimmen
    base = exec_base
    if settings.base_root:
        anchor = find_anchor_by_name(exec_base, md_path, settings.base_root)
        if settings.scope_under_base_root and anchor is None:
            return False  # Datei liegt nicht unter einem 'Skript'-Ordner
        if anchor is not None:
            base = anchor  # Anker = das konkrete 'Skript' über der Datei

    # Pfadebenen
    folder_levels_up = compute_folder_levels_up(md_path)
    root_parts_down = compute_root_parts_down(base, md_path.parent)
    file_date = get_creation_date(md_path)
    file_stem = md_path.stem         # Dateiname ohne Erweiterung
    file_name = md_path.name         # Dateiname mit Erweiterung

    applied = apply_template(
        template,
        exec_base=base,
        exec_root_name=base.name,
        folder_levels_up=folder_levels_up,
        root_parts_down=root_parts_down,
        file_date=file_date,
        file_stem=file_stem,
        file_name=file_name,
    )
    if not isinstance(applied, dict):
        raise ValueError("Template muss ein Mapping auf Top-Level sein.")

    # NEU: Rename-Direktiven 'ALT/NEU' mit Wertübertragung anwenden
    applied2, drop_sources = resolve_renames(applied, existing)
    # Sicherstellen, dass alte Keys in jedem Modus verschwinden:
    existing2 = {k: v for k, v in existing.items() if k not in drop_sources}

    final_data = build_result(
        existing2,
        applied2,
        key_mode=settings.key_mode,
        keep_extra=settings.keep_extra_keys,
    )

    new_content = dump_frontmatter(final_data) + body.lstrip("\n")
    if new_content != text:
        write_text(md_path, new_content)
        return True
    return False


def run(root: Path) -> None:
    settings, template = load_config(root)

    exec_base = root.resolve()

    changed = 0
    total = 0
    include_names = tuple(settings.include_folders_by_name)
    use_selection = bool(settings.selective_processing_active and include_names)

    for md in root.rglob("*.md"):
        if is_excluded(md, settings.exclude_folders):
            continue

        # 2) Selektionslogik: nur Dateien unter explizit benannten Ordnern
        if use_selection:
            # Finde nächstgelegenen selektierten Anker (z. B. 'Klausur')
            anchor_dir = nearest_named_ancestor(md.parent, include_names)
            if anchor_dir is None:
                # Datei liegt NICHT unter einem gewünschten Ordner
                continue

            # 3) ANKER-Exklusion per Ordner (integriert in exclude_folders):
            #    Wenn der selektierte Anker einen *direkten* Unterordner hat,
            #    dessen Name in exclude_folders matcht (z. B. '.archive'),
            #    wird der gesamte Ankerzweig ausgelassen.
            if has_excluded_child_folder(anchor_dir, settings.exclude_folders):
                continue

        total += 1
        if process_md(md, template, exec_base=exec_base, settings=settings):
            changed += 1
            print(f"[OK]   aktualisiert: {md}")
        else:
            print(f"[SKIP] unverändert: {md}")

    print(f"\nFertig. Dateien gesamt: {total}, geändert: {changed}.")

# ======================= CLI =======================

def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="YAML-Frontmatter-Manager (rekursiv)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ap.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Startverzeichnis (Standard: aktuelles Arbeitsverzeichnis)",
    )
    return ap.parse_args(argv)


if __name__ == "__main__":
    ns = parse_args(sys.argv[1:])
    run(ns.root.resolve())
