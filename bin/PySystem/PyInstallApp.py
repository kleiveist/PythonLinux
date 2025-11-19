#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
InstallAppImage.py

Ablauf:

1. Im AKTUELLEN ORDNER nach *.AppImage / *.appimage suchen.
2. Für jede gefundene AppImage-Datei:
   - AppImage nach  <HOME>/Dokumente|Documents/AppImage  kopieren
   - PNG mit gleichem Namen (falls vorhanden) ebenfalls dorthin kopieren
   - PNG zusätzlich als Kopie nach  <HOME>/.local/share/icons  kopieren
3. Aus der Kopie im Dokumentenordner:
   - Ausführbar machen
   - .desktop-Datei in ~/.local/share/applications erzeugen
     - Exec = Pfad zur AppImage-Kopie im Dokumentenordner
     - Path = Dokumentenordner/AppImage
     - Icon = NUR der PNG-Dateiname (z.B. Obsidian.png)
4. KEIN Wrapper-Script in /bin o.ä.

Aufruf:
    python3 InstallApp.py
"""

import os
import re
import stat
import sys
import shutil
from pathlib import Path

ARCH_TOKENS = {"x86_64", "amd64", "arm64", "aarch64", "i386", "i686"}


def human_name_from_basename(basename: str) -> str:
    """Erzeuge einen hübschen Anzeigenamen aus dem Dateinamen ohne Endung."""
    name = basename
    parts = re.split(r"[-_ ]+", name)
    if parts and parts[-1].lower() in ARCH_TOKENS:
        parts = parts[:-1]
    name = " ".join(parts)
    name = re.sub(r"([-_ ]?v?\d+(\.\d+){0,3}([-_][A-Za-z0-9]+)?)$", "", name).strip()
    name = re.sub(r"[_\-]+", " ", name).strip()
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


def build_desktop_entry(
    name: str,
    exec_path: Path,
    workdir: Path,
    icon_name: str | None,
) -> str:
    """
    Erzeuge den Inhalt einer .desktop-Datei.

    - Exec: voller Pfad zur AppImage-Kopie im Dokumentenordner
    - Path: Dokumenten-AppImage-Ordner
    - Icon: nur der Dateiname (z.B. Obsidian.png), KEIN vollständiger Pfad
    """
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
    if icon_name:
        lines.append(f"Icon={icon_name}")
    return "\n".join(lines) + "\n"


def get_documents_dir() -> Path:
    """
    Versuche, das Dokumentenverzeichnis zu finden.
    - erst XDG_DOCUMENTS_DIR (falls gesetzt)
    - dann ~/Documents
    - dann ~/Dokumente
    - Fallback: ~/Documents
    """
    xdg_docs = os.environ.get("XDG_DOCUMENTS_DIR")
    if xdg_docs:
        p = Path(os.path.expanduser(xdg_docs))
        if p.exists():
            return p

    for name in ("Documents", "Dokumente"):
        p = Path.home() / name
        if p.exists():
            return p

    return Path.home() / "Documents"


def get_icons_dir() -> Path:
    """
    Liefert den Icon-Ordner:
    <HOME>/.local/share/icons  (bzw. $XDG_DATA_HOME/icons)
    """
    xdg_data_home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return xdg_data_home / "icons"


def main():
    cwd = Path.cwd()

    # .desktop-Zielordner
    xdg_data_home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    applications_dir = xdg_data_home / "applications"
    applications_dir.mkdir(parents=True, exist_ok=True)

    # Zielordner für AppImages: <HOME>/Dokumente|Documents/AppImage
    documents_dir = get_documents_dir()
    appimage_repo = documents_dir / "AppImage"
    appimage_repo.mkdir(parents=True, exist_ok=True)

    # Zielordner für Icons: <HOME>/.local/share/icons
    icons_dir = get_icons_dir()
    icons_dir.mkdir(parents=True, exist_ok=True)

    # AppImages im aktuellen Ordner finden
    appimages = sorted(list(cwd.glob("*.AppImage")) + list(cwd.glob("*.appimage")))
    if not appimages:
        print("Keine AppImage-Dateien im aktuellen Ordner gefunden.")
        sys.exit(0)

    print(f"Dokumentenverzeichnis: {documents_dir}")
    print(f"Zielordner für AppImages: {appimage_repo}")
    print(f"Icon-Ordner: {icons_dir}\n")

    created = 0

    for original_appimage in appimages:
        try:
            # --- STEP 1: AppImage nach Dokumente/AppImage kopieren ---
            target_appimage = appimage_repo / original_appimage.name
            shutil.copy2(original_appimage, target_appimage)

            # PNG mit gleichem Namen im ursprünglichen Ordner?
            original_icon = original_appimage.with_suffix(".png")
            icon_name = None

            if original_icon.exists():
                icon_name = original_icon.name

                # PNG in Dokumente/AppImage kopieren
                target_icon_in_repo = appimage_repo / original_icon.name
                shutil.copy2(original_icon, target_icon_in_repo)

                # PNG zusätzlich nach ~/.local/share/icons kopieren
                target_icon_in_icons = icons_dir / original_icon.name
                shutil.copy2(original_icon, target_icon_in_icons)

            # --- Ab hier mit der KOPIE im Dokumentenordner arbeiten ---
            make_appimage_executable(target_appimage)

            base = target_appimage.name.rsplit(".", 1)[0]
            human_name = human_name_from_basename(base)
            app_id = safe_id_from_name(human_name)

            # .desktop-Inhalt erzeugen:
            # - Exec und Path zeigen auf Dokumente/AppImage
            # - Icon = nur Dateiname (z.B. Obsidian.png)
            desktop_text = build_desktop_entry(
                name=human_name,
                exec_path=target_appimage.resolve(),
                workdir=appimage_repo.resolve(),
                icon_name=icon_name,
            )

            desktop_filename = f"{app_id}.desktop"
            desktop_path = applications_dir / desktop_filename

            # Optionale Aufräumaktion: alte -1, -2, ... Dateien löschen
            for old in applications_dir.glob(f"{app_id}-*.desktop"):
                try:
                    old.unlink()
                except Exception:
                    pass

            # Datei mit festem Namen immer überschreiben
            desktop_path.write_text(desktop_text, encoding="utf-8")
            desktop_path.chmod(0o644)

            print(f"✓ Integriert: {original_appimage.name}")
            print(f"  Kopie:   {target_appimage.resolve()}")
            print(f"  Name:    {human_name}")
            print(f"  Exec:    {target_appimage.resolve()}")
            print(f"  Path:    {appimage_repo.resolve()}")
            if icon_name:
                print(f"  Icon:    {icon_name} (Kopie in {icons_dir} und {appimage_repo})")
            else:
                print("  Icon:    (keine passende PNG gefunden)")
            print(f"  .desktop: {desktop_path}\n")

            created += 1

        except Exception as e:
            print(f"⚠ Fehler bei {original_appimage.name}: {e}")

    if created:
        # Desktop-Cache optional aktualisieren (Fehler ignorieren)
        for cmd in ("update-desktop-database", "xdg-desktop-menu"):
            try:
                os.system(f"{cmd} >/dev/null 2>&1")
            except Exception:
                pass

        print(f"Fertig. {created} AppImage(s) integriert.")
        print("Hinweis: Wrapper sind .desktop-Dateien, keine Skripte in /bin.")
    else:
        print("Nichts erstellt.")


if __name__ == "__main__":
    main()
