#!/usr/bin/env python3
"""
PyInstallApp - Installiere AppImages und .desktop-Dateien bequem ins System.

Funktionen:
- AppImages in ein zentrales Verzeichnis unter ~/Dokumente/Apps/AppImage kopieren
- Wrapper-Desktop-Dateien für AppImages in ~/.local/share/applications anlegen
- .desktop-Dateien aus einem Ordner "Desktop" installieren
- .png-Icons nach ~/.local/share/icons kopieren
- Kann sowohl mit Unterordnern AppImage/Desktop als auch direkt mit Dateien im aktuellen Ordner umgehen.
"""

import sys
import shutil
from pathlib import Path

# ======= Einfache Terminal-Formatierung =======
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"

def headline(text: str) -> None:
    print(f"\n{BOLD}┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓{RESET}")
    print(f"{BOLD}┃ {text:<44}┃{RESET}")
    print(f"{BOLD}┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛{RESET}\n")

def info(msg: str) -> None:
    print(f"ℹ️  {msg}")

def success(msg: str) -> None:
    print(f"{GREEN}✅ {msg}{RESET}")

def warn(msg: str) -> None:
    print(f"{YELLOW}⚠️  {msg}{RESET}")

def error(msg: str) -> None:
    print(f"{RED}❌ {msg}{RESET}")

# ======= Pfade ermitteln =======

def detect_docs_dir() -> Path:
    home = Path.home()
    for name in ("Dokumente", "Documents"):
        candidate = home / name
        if candidate.is_dir():
            return candidate
    return home

HOME = Path.home()
DOCS_DIR = detect_docs_dir()
APPS_DIR = DOCS_DIR / "Apps"
APPIMAGE_TARGET = APPS_DIR / "AppImage"
DESKTOP_TARGET = APPS_DIR / "Desktop"
ICON_DIR = HOME / ".local" / "share" / "icons"
APPLICATIONS_DIR = HOME / ".local" / "share" / "applications"

def ensure_directories():
    for d in (APPS_DIR, APPIMAGE_TARGET, DESKTOP_TARGET, ICON_DIR, APPLICATIONS_DIR):
        d.mkdir(parents=True, exist_ok=True)

# ======= Hilfsfunktionen =======

def slugify_name(name: str) -> str:
    """Einfache Slug-Funktion für Dateinamen."""
    keep = []
    for ch in name:
        if ch.isalnum():
            keep.append(ch.lower())
        elif ch in (" ", "-", "_"):
            keep.append("-")
    slug = "".join(keep).strip("-")
    return slug or "appimage"

def detect_source_dirs(base: Path):
    """Finde Quellordner für AppImages und Desktop-Dateien."""
    appimage_dir = None
    desktop_dir = None

    appimage_files_here = list(base.glob("*.AppImage")) + list(base.glob("*.appimage"))
    desktop_files_here = list(base.glob("*.desktop"))

    if appimage_files_here:
        appimage_dir = base
    if desktop_files_here:
        desktop_dir = base

    # Wenn im Basisordner nichts ist, nach Unterordnern suchen
    if appimage_dir is None:
        if (base / "AppImage").is_dir():
            appimage_dir = base / "AppImage"
    if desktop_dir is None:
        if (base / "Desktop").is_dir():
            desktop_dir = base / "Desktop"

    return appimage_dir, desktop_dir

# ======= AppImage-Verarbeitung =======

def process_appimages(appimage_dir: Path):
    headline("AppImages installieren")
    appimages = sorted(list(appimage_dir.glob("*.AppImage")) + list(appimage_dir.glob("*.appimage")))
    if not appimages:
        warn(f"Keine AppImages gefunden in: {appimage_dir}")
        return

    for src in appimages:
        name = src.stem
        slug = slugify_name(name)
        dest_appimage = APPIMAGE_TARGET / src.name

        try:
            shutil.copy2(src, dest_appimage)
        except Exception as e:
            error(f"Konnte AppImage nicht kopieren: {src} → {dest_appimage} ({e})")
            continue

        # Icon suchen: gleiche Basis, .png im selben Ordner
        icon_src = None
        for ext in (".png", ".svg", ".xpm"):
            candidate = src.with_suffix(ext)
            if candidate.is_file():
                icon_src = candidate
                break

        icon_name = None
        if icon_src:
            icon_name = icon_src.stem  # Desktop-File benutzt typischerweise nur den Namen ohne Pfad/Endung
            try:
                shutil.copy2(icon_src, ICON_DIR / icon_src.name)
                shutil.copy2(icon_src, APPIMAGE_TARGET / icon_src.name)
                icon_msg = f"{icon_src.name} (→ {ICON_DIR}, → {APPIMAGE_TARGET})"
            except Exception as e:
                warn(f"Icon konnte nicht kopiert werden: {icon_src} ({e})")
                icon_msg = f"{icon_src.name} (Fehler beim Kopieren)"
        else:
            icon_msg = "kein passendes Icon gefunden"

        # .desktop-Datei erstellen (Wrapper)
        desktop_filename = f"{slug}.desktop"
        desktop_path = APPLICATIONS_DIR / desktop_filename

        desktop_content = [
            "[Desktop Entry]",
            "Type=Application",
            f"Name={name}",
            f"Exec={dest_appimage} %U",
            f"Path={APPIMAGE_TARGET}",
            f"Icon={icon_name or slug}",
            "Terminal=false",
            "Categories=Utility;",
        ]
        try:
            desktop_path.write_text("\n".join(desktop_content), encoding="utf-8")
        except Exception as e:
            error(f".desktop-Datei konnte nicht geschrieben werden: {desktop_path} ({e})")
            continue

        success(f"Integriert: {src.name}")
        print(f"   📦 Quelle:  {src}")
        print(f"   📁 Ziel:    {dest_appimage}")
        print(f"   ⚙️  Exec:   {dest_appimage}")
        print(f"   🧩 Desktop: {desktop_path}")
        print(f"   🖼️ Icon:    {icon_msg}")

# ======= Desktop-Dateien / Icons =======

def process_desktop_files(desktop_dir: Path):
    headline(".desktop & Icons installieren")
    desktop_files = sorted(desktop_dir.glob("*.desktop"))
    png_files = sorted([p for p in desktop_dir.glob("*.png")])

    if not desktop_files and not png_files:
        warn(f"Keine .desktop oder .png-Dateien gefunden in: {desktop_dir}")
        return

    # Icons zuerst kopieren
    if png_files:
        info(f"Icons kopieren aus {desktop_dir} …")
        for icon in png_files:
            try:
                shutil.copy2(icon, ICON_DIR / icon.name)
                shutil.copy2(icon, DESKTOP_TARGET / icon.name)
                success(f"Icon installiert: {icon.name}")
            except Exception as e:
                error(f"Icon konnte nicht kopiert werden: {icon} ({e})")
    else:
        warn("Keine .png-Icons gefunden.")

    # .desktop-Dateien kopieren
    if desktop_files:
        info(f".desktop-Dateien installieren aus {desktop_dir} …")
        for df in desktop_files:
            dest_backup = DESKTOP_TARGET / df.name
            dest_sys = APPLICATIONS_DIR / df.name
            try:
                shutil.copy2(df, dest_backup)
                shutil.copy2(df, dest_sys)
            except Exception as e:
                error(f".desktop-Datei konnte nicht kopiert werden: {df} ({e})")
                continue

            success(f".desktop installiert: {df.name}")
            print(f"   🧩 System:  {dest_sys}")
            print(f"   📁 Backup:  {dest_backup}")
    else:
        warn("Keine .desktop-Dateien gefunden.")

# ======= main =======

def main():
    ensure_directories()

    if len(sys.argv) > 1:
        base = Path(sys.argv[1]).expanduser().resolve()
    else:
        base = Path.cwd()

    headline("PyInstallApp – AppImage & Desktop Installer")
    info(f"Basisordner:       {base}")
    info(f"Dokumentenordner:  {DOCS_DIR}")
    info(f"Apps-Ordner:       {APPS_DIR}")
    info(f"AppImage-Ziel:     {APPIMAGE_TARGET}")
    info(f"Desktop-Ziel:      {DESKTOP_TARGET}")
    info(f"Icon-Ordner:       {ICON_DIR}")
    info(f"Applications-Dir:  {APPLICATIONS_DIR}")
    print()

    if not base.exists():
        error(f"Basisordner existiert nicht: {base}")
        sys.exit(1)

    appimage_dir, desktop_dir = detect_source_dirs(base)

    if not appimage_dir and not desktop_dir:
        warn("Keine AppImages oder .desktop-Dateien gefunden.")
        warn("Lege Dateien entweder direkt in den Basisordner oder in Unterordner 'AppImage' / 'Desktop'.")
        return

    # Wichtig: unabhängig voneinander behandeln
    if appimage_dir:
        info(f"AppImages werden verarbeitet aus: {appimage_dir}")
        process_appimages(appimage_dir)
    else:
        info("Keine AppImages zu verarbeiten.")

    if desktop_dir:
        info(f".desktop / Icons werden verarbeitet aus: {desktop_dir}")
        process_desktop_files(desktop_dir)
    else:
        info("Keine .desktop / Icon-Dateien zu verarbeiten.")

    print()
    success("Fertig 🎉")

if __name__ == "__main__":
    main()
