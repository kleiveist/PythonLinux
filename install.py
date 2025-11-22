#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import pwd
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Iterable, List, Sequence
from dataclasses import dataclass, field

USE_ICONS = os.environ.get("PLAIN_LOGS") is None
ICON_INFO = "ℹ️" if USE_ICONS else "[INFO]"
ICON_WARN = "⚠️" if USE_ICONS else "[WARN]"
ICON_ERR = "❌" if USE_ICONS else "[ERROR]"
ICON_SUMMARY = "📊" if USE_ICONS else "[SUM]"
ICON_PY = "📂" if USE_ICONS else "[PY]"
ICON_VENV = "🐍" if USE_ICONS else "[VENV]"
ICON_WRAP = "🧩" if USE_ICONS else "[WRAP]"
ICON_MODE = "⚙️" if USE_ICONS else "[MODE]"
ICON_ROOT = "🔒" if USE_ICONS else "[ROOT]"

@dataclass
class VenvReport:
    src_venv_txt: Path
    target_dir: Path
    venv_dir: Path
    created: bool           # True = neu (oder würde neu angelegt)
    venv_ok: bool           # True = venv-Erstellung ok (bzw. Dry-Run)
    requirements: List[str] # Pakete aus venv.txt
    pip_ok: bool | None     # True/False = pip ok/Fehler, None = nicht ausgeführt (z.B. Dry-Run)


@dataclass
class InstallReport:
    dry_run: bool
    start_dir: Path
    dest_base: Path
    copied_files: int = 0
    installed_dirs: set[Path] = field(default_factory=set)
    venv_created_count: int = 0
    venv_reports: List[VenvReport] = field(default_factory=list)
    wrapper_count: int = 0
    wrapper_paths: List[Path] = field(default_factory=list)

def log(msg: str) -> None:
    prefix = ICON_INFO if USE_ICONS else ICON_INFO
    print(f"{prefix} {msg}")


def warn(msg: str) -> None:
    prefix = ICON_WARN if USE_ICONS else ICON_WARN
    print(f"{prefix} {msg}", file=sys.stderr)


def err(msg: str) -> None:
    prefix = ICON_ERR if USE_ICONS else ICON_ERR
    print(f"{prefix} {msg}", file=sys.stderr)


def print_help() -> None:
    print(
        "Usage: ./install.py [--clear] [--yes|-y] [--dry-run] [--help]\n"
        "\n"
        "--clear     Führt vor der Installation eine bereinigte Neuinstallation aus:\n"
        "            - Löscht DEST_BASE/bin und DEST_BASE/game (falls vorhanden)\n"
        "            - Entfernt markierte Wrapper im WRAPPER_DIR\n"
        "--yes, -y   Bestätigt Rückfragen automatisch (non-interaktiv)\n"
        "--dry-run   Zeigt nur an, was gelöscht/erstellt würde (keine Änderungen)\n"
        "--help      Diese Hilfe"
    )


PRUNE_NAMES = {".git", "__pycache__", "venv", ".venv", ".archive"}
WRAP_MARKER = "# Managed by PythonLinux install.sh"


def should_prune_dir(path: Path) -> bool:
    name = path.name
    if name in PRUNE_NAMES or ".name" in name:
        return True
    return (path / ".name").exists()


def walk_filtered(base: Path) -> Iterable[tuple[Path, List[str]]]:
    if should_prune_dir(base):
        return
    for root, dirs, files in os.walk(base):
        root_path = Path(root)
        dirs[:] = [d for d in dirs if not should_prune_dir(root_path / d)]
        yield root_path, files


def confirm(prompt: str, assume_yes: bool) -> bool:
    if assume_yes:
        return True
    try:
        ans = input(f"{prompt} [y/N] ").strip()
    except EOFError:
        return False
    return ans.lower() == "y"


def safe_rm_path(path: Path, dry_run: bool) -> None:
    if not path:
        err("Interner Fehler: leerer Pfad in safe_rm_path")
        return
    if str(path) in {"/", "/root", str(Path.home())}:
        err(f"Abbruch: Schutzgeländer verhindern Löschen von '{path}'.")
        return
    if path.exists():
        if dry_run:
            log(f"[dry-run] rm -rf -- {path}")
        else:
            shutil.rmtree(path)
            log(f"Gelöscht: {path}")


def safe_rm_file(path: Path, dry_run: bool) -> None:
    if not path:
        return
    if path.exists():
        if dry_run:
            log(f"[dry-run] rm -f -- {path}")
        else:
            path.unlink()
            log(f"Entfernt: {path}")


def clear_install(dest_base: Path, wrapper_dir: Path, dry_run: bool, assume_yes: bool) -> None:
    log("Starte bereinigte Neuinstallation (--clear).")

    remove_paths: List[Path] = []
    for name in ("bin", "game"):
        candidate = dest_base / name
        if candidate.exists():
            remove_paths.append(candidate)

    if remove_paths:
        log("Zum Löschen vorgemerkt (DEST_BASE):")
        for p in remove_paths:
            print(f"  {p}")
        if confirm("Diese Pfade löschen?", assume_yes):
            for p in remove_paths:
                safe_rm_path(p, dry_run)
        else:
            warn("Löschen der Ziel-Unterbäume abgebrochen.")
    else:
        log("Keine bin/ oder game/ in DEST_BASE vorhanden – nichts zu löschen.")

    if wrapper_dir.is_dir():
        log(f"Prüfe Wrapper in '{wrapper_dir}' (nur markierte werden gelöscht)...")
        for wrapper in wrapper_dir.iterdir():
            if not wrapper.is_file() or not os.access(wrapper, os.X_OK):
                continue
            try:
                if WRAP_MARKER in wrapper.read_text(errors="ignore"):
                    if confirm(f"Wrapper entfernen: {wrapper}?", assume_yes):
                        safe_rm_file(wrapper, dry_run)
                    else:
                        warn(f"Übersprungen: {wrapper}")
            except OSError as exc:
                warn(f"Kann Wrapper nicht prüfen ({wrapper}): {exc}")
    else:
        log("WRAPPER_DIR existiert (noch) nicht – keine Wrapper zu löschen.")


def collect_files(start_dir: Path, pattern: str) -> List[Path]:
    matches: List[Path] = []
    for root, files in walk_filtered(start_dir):
        for file_name in files:
            if ".name" in file_name:
                continue
            if pattern == "*.py" and file_name.endswith(".py"):
                matches.append(root / file_name)
            elif pattern == "venv.txt" and file_name == "venv.txt":
                matches.append(root / file_name)
    return matches


def copy_py_files(
    py_files: Sequence[Path],
    start_dir: Path,
    dest_base: Path,
    dry_run: bool,
    report: InstallReport | None = None,
) -> int:
    copied = 0
    for src in py_files:
        try:
            rel = src.relative_to(start_dir)
        except ValueError:
            warn(f"Überspringe Datei außerhalb von START_DIR: {src}")
            continue
        dest = dest_base / rel
        if dry_run:
            log(f"[dry-run] mkdir -p -- {dest.parent}")
            log(f"[dry-run] cp -f -- {src} {dest}")
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
        copied += 1
        if report is not None:
            # Zielordner merken (auch im Dry-Run)
            report.installed_dirs.add(dest.parent)
    log(f"Kopiert: {copied} .py-Dateien nach '{dest_base}'.")
    if report is not None:
        report.copied_files = copied
    return copied


def load_requirements(file_path: Path) -> List[str]:
    try:
        lines = file_path.read_text().splitlines()
    except OSError as exc:
        warn(f"Kann {file_path} nicht lesen: {exc}")
        return []
    reqs = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            reqs.append(stripped)
    return reqs


def ensure_venv(target_dir: Path, dry_run: bool) -> bool:
    venv_dir = target_dir / ".venv"
    if venv_dir.is_dir():
        log(f"venv existiert bereits: {venv_dir}")
        return True
    log(f"Erstelle venv: {venv_dir}")
    if dry_run:
        log(f"[dry-run] python3 -m venv \"{venv_dir}\"")
        return True
    try:
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
        return True
    except subprocess.CalledProcessError:
        err("Konnte venv nicht erstellen (ggf. python3-venv Paket installieren).")
        return False


def install_requirements(venv_dir: Path, requirements: List[str], dry_run: bool, src_label: str) -> bool:
    py_bin = venv_dir / "bin" / "python"
    pip_bin = venv_dir / "bin" / "pip"

    if dry_run:
        log(f"[dry-run] \"{py_bin}\" -m pip install --upgrade pip")
        if requirements:
            log(f"[dry-run] \"{pip_bin}\" install -r <temp_req_from_{src_label}>")
        else:
            log(f"Keine Pakete in {src_label} – leere venv.")
        return True

    try:
        subprocess.run(
            [str(py_bin), "-m", "pip", "install", "--upgrade", "pip"],
            check=True,
            stdout=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError as exc:
        warn(f"pip konnte nicht aktualisiert werden ({src_label}): {exc}")

    if not requirements:
        log(f"Keine Pakete in {src_label} – leere venv.")
        return True

    with tempfile.NamedTemporaryFile("w", delete=False) as tmp:
        tmp_path = Path(tmp.name)
        tmp.write("\n".join(requirements))

    try:
        subprocess.run([str(pip_bin), "install", "-r", str(tmp_path)], check=True)
        log(f"Installiere Pakete aus {src_label}")
        return True
    except subprocess.CalledProcessError as exc:
        warn(f"Installation fehlgeschlagen ({src_label}): {exc}")
        return False
    finally:
        tmp_path.unlink(missing_ok=True)

def handle_venvs(
    venv_txt_files: Sequence[Path],
    start_dir: Path,
    dest_base: Path,
    dry_run: bool,
    report: InstallReport | None = None,
) -> int:
    created = 0
    for vfile in venv_txt_files:
        src_dir = vfile.parent
        try:
            rel_dir = src_dir.relative_to(start_dir)
        except ValueError:
            warn(f"Überspringe venv.txt außerhalb von START_DIR: {vfile}")
            continue
        tgt_dir = dest_base / rel_dir
        venv_dir = tgt_dir / ".venv"
        if dry_run:
            log(f"[dry-run] mkdir -p -- {tgt_dir}")
        else:
            tgt_dir.mkdir(parents=True, exist_ok=True)

        existed = venv_dir.exists()
        venv_ok = ensure_venv(tgt_dir, dry_run)

        reqs = load_requirements(vfile)
        try:
            label = vfile.relative_to(start_dir)
        except ValueError:
            label = vfile

        pip_ok: bool | None = None
        if venv_ok:
            if dry_run:
                # nur Kommandos anzeigen
                install_requirements(venv_dir, reqs, dry_run, str(label))
            else:
                pip_ok = install_requirements(venv_dir, reqs, dry_run, str(label))
            if not existed:
                created += 1

        if report is not None:
            report.installed_dirs.add(tgt_dir)
            report.venv_reports.append(
                VenvReport(
                    src_venv_txt=vfile,
                    target_dir=tgt_dir,
                    venv_dir=venv_dir,
                    created=(not existed and venv_ok),
                    venv_ok=venv_ok,
                    requirements=reqs,
                    pip_ok=None if dry_run else pip_ok,
                )
            )

    if created:
        log(f"Angelegte venvs: {created}")
    if report is not None:
        report.venv_created_count = created
    return created

def find_dest_py_files(dest_base: Path) -> List[Path]:
    matches: List[Path] = []
    for root, dirs, files in os.walk(dest_base):
        root_path = Path(root)
        dirs[:] = [d for d in dirs if d not in {".venv", "venv", "__pycache__"}]
        for file_name in files:
            if file_name.endswith(".py"):
                matches.append(root_path / file_name)
    return matches


def write_wrapper_content(script_abs: Path) -> str:
    return "\n".join(
        [
            "#!/usr/bin/env bash",
            "set -euo pipefail",
            WRAP_MARKER,
            f"SCRIPT_PATH={shlex_quote(str(script_abs))}",
            'dir="$(dirname "$SCRIPT_PATH")"',
            'py="python3"',
            'while [[ "$dir" != "/" ]]; do',
            '  if [[ -x "$dir/.venv/bin/python" ]]; then',
            '    py="$dir/.venv/bin/python"',
            "    break",
            "  fi",
            '  dir="$(dirname "$dir")"',
            "done",
            'exec "$py" "$SCRIPT_PATH" "$@"',
            "",
        ]
    )


def shlex_quote(val: str) -> str:
    return shlex.quote(val)


def install_wrapper(wrapper_path: Path, content: str, dry_run: bool, force_root: bool) -> bool:
    if dry_run:
        log(f"[dry-run] install -m 0755 <tmp> {wrapper_path}")
        return True

    wrapper_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", delete=False) as tmp:
        tmp_path = Path(tmp.name)
        tmp.write(content)

    try:
        if os.access(wrapper_path.parent, os.W_OK) and not force_root:
            shutil.copy2(tmp_path, wrapper_path)
            wrapper_path.chmod(0o755)
        else:
            try:
                subprocess.run(["sudo", "install", "-m", "0755", str(tmp_path), str(wrapper_path)], check=True)
                subprocess.run(["sudo", "chown", "root:root", str(wrapper_path)], check=True)
            except subprocess.CalledProcessError:
                warn(f"Keine Schreibrechte für '{wrapper_path.parent}' und keine sudo-Rechte – Wrapper '{wrapper_path.name}' wurde NICHT installiert.")
                return False
    finally:
        tmp_path.unlink(missing_ok=True)

    log(f"Wrapper installiert: {wrapper_path}")
    return True


def create_wrappers(
    dest_py_files: Sequence[Path],
    wrapper_dir: Path,
    dry_run: bool,
    force_root: bool,
    report: InstallReport | None = None,
) -> int:
    wrappers = 0
    for file_path in dest_py_files:
        name = file_path.stem
        wrapper_path = wrapper_dir / name
        content = write_wrapper_content(file_path)
        if install_wrapper(wrapper_path, content, dry_run, force_root):
            wrappers += 1
            if report is not None:
                report.wrapper_paths.append(wrapper_path)
        else:
            warn(f"Wrapper für '{file_path}' konnte nicht erstellt werden.")
    log(f"Wrapper erstellt: {wrappers}")
    if report is not None:
        report.wrapper_count = wrappers
    return wrappers

def print_summary(report: InstallReport) -> None:
    print(f"{ICON_SUMMARY} Übersicht:")
    print(f"  {ICON_MODE} Modus: {'Dry-Run (keine Änderungen)' if report.dry_run else 'Ausgeführt'}")

    venv_total = len(report.venv_reports)
    pip_ok = sum(1 for v in report.venv_reports if v.pip_ok is True)
    pip_fail = sum(1 for v in report.venv_reports if v.pip_ok is False)

    print(f"  {ICON_PY} .py-Dateien kopiert: {report.copied_files}")
    print(f"  {ICON_VENV} venvs gesamt: {venv_total} (neu: {report.venv_created_count})")
    if not report.dry_run and venv_total:
        print(f"           pip-Installationen: OK: {pip_ok}, Fehler: {pip_fail}")
    print(f"  {ICON_WRAP} Wrapper erstellt: {report.wrapper_count}")
    print()

    # 1) Welche Zielordner wurden installiert?
    if report.installed_dirs:
        print(f"{ICON_PY} Installierte Zielordner (relativ zu {report.dest_base}):")
        for d in sorted(report.installed_dirs):
            try:
                rel = d.relative_to(report.dest_base)
            except ValueError:
                rel = d
            print(f"   - {rel}")
        print()
    else:
        print(f"{ICON_PY} Keine Zielordner mit .py-Dateien oder venvs.")
        print()

    # 2) VMs / venvs – wurden sie alle installiert?
    if report.venv_reports:
        print(f"{ICON_VENV} Details zu virtuellen Umgebungen:")
        for v in sorted(report.venv_reports, key=lambda x: str(x.target_dir)):
            try:
                rel = v.target_dir.relative_to(report.dest_base)
            except ValueError:
                rel = v.target_dir

            if not v.venv_ok and not report.dry_run:
                status = "FEHLER: venv konnte nicht erstellt werden"
            else:
                if v.created and report.dry_run:
                    status = "würde neu erstellt (Dry-Run)"
                elif v.created:
                    status = "neu erstellt"
                else:
                    status = "bereits vorhanden"

            if report.dry_run:
                pip_status = "pip: (Dry-Run – keine Installation ausgeführt)"
            elif not v.venv_ok:
                pip_status = "pip: nicht ausgeführt (venv-Fehler)"
            elif not v.requirements:
                pip_status = "pip: keine Pakete (leere venv)"
            else:
                if v.pip_ok is True:
                    pip_status = "pip: OK"
                elif v.pip_ok is False:
                    pip_status = "pip: FEHLER (siehe Log oben)"
                else:
                    pip_status = "pip: unbekannter Status"

            print(f"   - {rel} [{status}]")
            if v.requirements:
                print(f"     Pakete ({len(v.requirements)}): {', '.join(v.requirements)}")
            else:
                print("     Pakete: (keine)")
            print(f"     {pip_status}")
        print()
    else:
        print(f"{ICON_VENV} Keine venvs verarbeitet.")
        print()

def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--clear", action="store_true")
    parser.add_argument("--yes", "-y", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--root", action="store_true", help="Erzwingt Wrapper-Installation via sudo nach /usr/local/bin")
    parser.add_argument("--help", "-h", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str]) -> int:
    args = parse_args(argv)
    if args.help:
        print_help()
        return 0

    start_dir = Path(os.environ.get("START_DIR", Path.cwd()))

    if args.root:
        base_home = Path("/root")
    else:
        sudo_user = os.environ.get("SUDO_USER")
        if sudo_user:
            try:
                base_home = Path(pwd.getpwnam(sudo_user).pw_dir)
            except KeyError:
                base_home = Path.home()
        else:
            base_home = Path.home()

    dest_base_env = os.environ.get("DEST_BASE")
    dest_base = Path(dest_base_env) if dest_base_env else base_home / "Dokumente/Python"

    wrapper_dir = Path("/usr/local/bin") if args.root else Path(os.environ.get("WRAPPER_DIR", "/usr/local/bin"))

    log(f"Startordner: {start_dir}")
    log(f"Zielbasis:   {dest_base}")
    log(f"Wrapper:     {wrapper_dir}")
    if args.root:
        log(f"{ICON_ROOT} Root-Modus aktiv: Wrapper werden mit sudo nach /usr/local/bin installiert.")
    if args.dry_run:
        log("Modus:       --dry-run (keine Änderungen)")

    dest_base.mkdir(parents=True, exist_ok=True)

    # Neuer Report für die Zusammenfassung
    report = InstallReport(dry_run=args.dry_run, start_dir=start_dir, dest_base=dest_base)

    if args.clear:
        clear_install(dest_base, wrapper_dir, args.dry_run, args.yes)

    log("Suche nach .py-Dateien ...")
    py_files = collect_files(start_dir, "*.py")
    if py_files:
        log(f"Gefundene .py-Dateien: {len(py_files)}")
    else:
        warn("Keine .py-Dateien gefunden (nach Ausschlüssen).")

    # Füllt report.copied_files und report.installed_dirs
    copy_py_files(py_files, start_dir, dest_base, args.dry_run, report)

    log("Suche nach venv.txt ...")
    venv_txt_files = collect_files(start_dir, "venv.txt")
    if venv_txt_files:
        log(f"Gefundene venv.txt-Dateien: {len(venv_txt_files)}")
    else:
        log("Keine venv.txt gefunden. Überspringe venv-Erstellung.")

    # Füllt report.venv_reports und report.venv_created_count
    handle_venvs(venv_txt_files, start_dir, dest_base, args.dry_run, report)

    log("Erzeuge Wrapper ...")
    dest_py_files = find_dest_py_files(dest_base)

    # Füllt report.wrapper_paths und report.wrapper_count
    create_wrappers(dest_py_files, wrapper_dir, args.dry_run, args.root, report)

    log("Fertig.")
    print_summary(report)
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
