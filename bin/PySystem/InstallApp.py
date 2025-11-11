#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
InstallAppImage.py
- Sucht im aktuellen Verzeichnis nach *.AppImage / *.appimage
- Setzt Ausführungsrechte
- Erstellt .desktop-Dateien in ~/.local/share/applications
- Verwendet optional eine PNG mit gleichem Basisnamen als Icon
- Erstellt KEINEN Wrapper in /bin (wie gewünscht)

Aufruf:
    python3 InstallAppImage.py
"""

import os
import re
import stat
import sys
from pathlib import Path

ARCH_TOKENS = {"x86_64", "amd64", "arm64", "aarch64", "i386", "i686"}

def human_name_from_basename(basename: str) -> str:
    """Erzeuge einen hübschen Namen aus dem Dateinamen ohne Endung."""
    name = basename
    # Entferne offensichtliche Architekturzusätze am Ende
    parts = re.split(r"[-_ ]+", name)
    if parts and parts[-1].lower() in ARCH_TOKENS:
        parts = parts[:-1]
    name = " ".join(parts)
    # Entferne typische Versionsendungen am Ende (z. B. -1.2.3, _v2.0, 2024.10)
    name = re.sub(r"([-_ ]?v?\d+(\.\d+){0,3}([-_][A-Za-z0-9]+)?)$", "", name).strip()
    # Ersetze weitere Trenner durch Leerzeichen
    name = re.sub(r"[_\-]+", " ", name).strip()
    # Titelcase, aber "AppImage" nicht anhängen
    return name[:1].upper() + name[1:] if name else basename

def make_appimage_executable(path: Path) -> None:
    st = path.stat()
    new_mode = st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
    if new_mode != st.st_mode:
        path.chmod(new_mode)

def safe_id_from_name(name: str) -> str:
    """Erzeuge eine dateinamenfreundliche ID (lowercase, a-z0-9-)."""
    safe = name.lower()
    safe = re.sub(r"[^a-z0-9]+", "-", safe).strip("-")
    return safe or "appimage-app"

def unique_path(base: Path) -> Path:
    """Erzeuge eindeutigen Pfad, falls bereits vorhanden (suffix -1, -2, ...)."""
    if not base.exists():
        return base
    i = 1
    while True:
        candidate = base.with_name(f"{base.stem}-{i}{base.suffix}")
        if not candidate.exists():
            return candidate
        i += 1

def build_desktop_entry(name: str, exec_path: Path, icon_path: Path | None, workdir: Path) -> str:
    # Desktop Spec: Exec unterstützt Anführungszeichen um Pfade mit Leerzeichen.
    exec_field = f"\"{exec_path}\" %U"
    lines = [
        "[Desktop Entry]",
        "Type=Application",
        f"Name={name}",
        f"Exec={exec_field}",
        f"Path={workdir}",
        "Terminal=false",
        "Categories=Utility;",
        "NoDisplay=false",
        "StartupNotify=true",
    ]
    if icon_path:
        lines.append(f"Icon={icon_path}")
    return "\n".join(lines) + "\n"

def find_icon_for(appimage: Path) -> Path | None:
    candidate = appimage.with_suffix(".png")
    return candidate if candidate.exists() else None

def main():
    cwd = Path.cwd()
    # Zielordner für .desktop gemäß XDG
    xdg_data_home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    applications_dir = xdg_data_home / "applications"
    applications_dir.mkdir(parents=True, exist_ok=True)

    # Finde AppImages (beide Schreibweisen)
    appimages = sorted(list(cwd.glob("*.AppImage")) + list(cwd.glob("*.appimage")))
    if not appimages:
        print("Keine AppImage-Dateien im aktuellen Ordner gefunden.")
        sys.exit(0)

    created = 0
    for appimage in appimages:
        try:
            # 1) Ausführbar machen
            make_appimage_executable(appimage)

            # 2) Namen und IDs ableiten
            base = appimage.name.rsplit(".", 1)[0]
            human_name = human_name_from_basename(base)
            app_id = safe_id_from_name(human_name)  # nutze hübschen Namen als Basis der ID

            # 3) Icon bestimmen
            icon_path = find_icon_for(appimage)

            # 4) .desktop-Inhalt erzeugen
            desktop_text = build_desktop_entry(
                name=human_name,
                exec_path=appimage.resolve(),
                icon_path=icon_path.resolve() if icon_path else None,
                workdir=appimage.parent.resolve()
            )

            # 5) .desktop-Datei schreiben (kollisionssicher)
            desktop_filename = f"{app_id}.desktop"
            desktop_path = unique_path(applications_dir / desktop_filename)
            desktop_path.write_text(desktop_text, encoding="utf-8")
            # Leserechte 0644
            desktop_path.chmod(0o644)

            print(f"✓ Integriert: {appimage.name}")
            print(f"  Name:   {human_name}")
            print(f"  Exec:   {appimage.resolve()}")
            if icon_path:
                print(f"  Icon:   {icon_path.resolve()}")
            print(f"  .desktop: {desktop_path}")
            created += 1

        except Exception as e:
            print(f"⚠ Fehler bei {appimage.name}: {e}")

    if created:
        # Optional: Desktop-Cache anstoßen (falls vorhanden, Fehler ignorieren)
        for cmd in ("update-desktop-database", "xdg-desktop-menu"):
            try:
                os.system(f"{cmd} >/dev/null 2>&1")
            except Exception:
                pass
        print(f"\nFertig. {created} AppImage(s) integriert.")
        print("Hinweis: Ein Wrapper in bin wurde nicht erstellt (wie gewünscht).")
    else:
        print("Nichts erstellt.")

if __name__ == "__main__":
    main()
