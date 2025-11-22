#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence
from urllib.request import urlopen

# Logging mit Icons, abschaltbar via PLAIN_LOGS=1
USE_ICONS = os.environ.get("PLAIN_LOGS") is None
ICON_INFO = "ℹ️" if USE_ICONS else "[INFO]"
ICON_WARN = "⚠️" if USE_ICONS else "[WARN]"
ICON_ERR = "❌" if USE_ICONS else "[ERROR]"
ICON_SUM = "📊" if USE_ICONS else "[SUM]"
ICON_MODE = "⚙️" if USE_ICONS else "[MODE]"
ICON_PKGS = "📦" if USE_ICONS else "[PKG]"
ICON_VENV = "🐍" if USE_ICONS else "[VENV]"
ICON_MODEL = "🧠" if USE_ICONS else "[MODEL]"

# Standard-Paketliste für AI-Usecases (wird nur benutzt, wenn venvAI.txt nichts vorgibt)
DEFAULT_AI_PACKAGES = [
    # Pflicht für AI / PyTorch-Modelle
    "torch",
    "torchvision",
    # Real-ESRGAN / ESRGAN-Umfeld
    "realesrgan",
    "basicsr",
    "facexlib",
    "gfpgan",
    # Bild / Video / I/O
    "opencv-python",
    "Pillow",
    "numpy",
    # Sonstiges
    "scipy",
    "requests",
    "tqdm",
    "pyyaml",
]

# Offizielle Download-URL für das Standard-Real-ESRGAN-4x-Modell
REAL_ESRGAN_URL = (
    "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/"
    "RealESRGAN_x4plus.pth"
)


@dataclass
class ModelSpec:
    rel_path: Path
    url: str
    sha256: str | None = None


def log(msg: str) -> None:
    print(f"{ICON_INFO} {msg}")


def warn(msg: str) -> None:
    print(f"{ICON_WARN} {msg}", file=sys.stderr)


def err(msg: str) -> None:
    print(f"{ICON_ERR} {msg}", file=sys.stderr)


def in_venv() -> bool:
    # True, wenn das Script schon in einer venv läuft (z.B. via Wrapper aus install.py)
    return sys.prefix != sys.base_prefix


def find_existing_venv(start_dir: Path) -> Path | None:
    # Sucht von start_dir nach oben die nächste .venv/bin/python.
    cur = start_dir
    while True:
        cand = cur / ".venv" / "bin" / "python"
        if cand.exists():
            return cand
        if cur.parent == cur:
            break
        cur = cur.parent
    return None


def pip_install(python: Path, packages: Sequence[str], dry_run: bool) -> bool:
    if not packages:
        log("Keine AI-Pakete in venvAI.txt definiert – überspringe pip install.")
        return True

    if dry_run:
        log(f"[dry-run] \"{python}\" -m pip install --upgrade pip")
        log(
            "[dry-run] \"{py}\" -m pip install {pkgs}".format(
                py=python, pkgs=" ".join(shlex.quote(p) for p in packages)
            )
        )
        return True

    try:
        subprocess.run(
            [str(python), "-m", "pip", "install", "--upgrade", "pip"],
            check=True,
            stdout=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError as exc:
        warn(f"pip konnte nicht aktualisiert werden: {exc}")

    try:
        subprocess.run([str(python), "-m", "pip", "install", *packages], check=True)
        return True
    except subprocess.CalledProcessError as exc:
        err(f"pip install fehlgeschlagen: {exc}")
        return False


def parse_venv_ai_lines(lines: list[str], cfg_path: Path) -> tuple[list[str], list[ModelSpec]]:
    # Syntax von venvAI.txt:
    #   # Kommentar
    #   pkg torch
    #   pkg realesrgan
    #   model weights/RealESRGAN_x4plus.pth https://.../RealESRGAN_x4plus.pth [sha256]
    #
    # - Zeilen, die mit 'pkg' anfangen, werden als pip-Paket interpretiert.
    # - Zeilen, die mit 'model' anfangen, erzeugen einen Download-Eintrag.
    # - Alle anderen nicht-leeren Zeilen werden als Paketname (pip) behandelt.
    packages: list[str] = []
    models: list[ModelSpec] = []

    for lineno, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        if line.startswith("pkg:") or line.startswith("pkg "):
            _, rest = line.split(None, 1)
            pkg = rest.strip()
            if pkg:
                packages.append(pkg)
            else:
                warn(f"{cfg_path}:{lineno}: 'pkg' ohne Paketnamen – Zeile ignoriert.")
            continue

        if line.startswith("model:") or line.startswith("model "):
            tmp = line.replace("model:", "model ", 1)
            parts = tmp.split()
            if len(parts) < 3:
                warn(
                    f"{cfg_path}:{lineno}: 'model'-Zeile erwartet "
                    "'model <rel_pfad> <url> [sha256]' – Zeile ignoriert."
                )
                continue
            _, rel, url, *rest = parts
            sha = rest[0] if rest else None
            models.append(ModelSpec(rel_path=Path(rel), url=url, sha256=sha))
            continue

        # Fallback: nackter Paketname
        packages.append(line)

    if not packages:
        warn(
            f"{cfg_path}: keine Pakete definiert – verwende Standard-AI-Paketliste "
            "(DEFAULT_AI_PACKAGES)."
        )
        packages = list(DEFAULT_AI_PACKAGES)

    return packages, models


def load_venv_ai(cfg_path: Path, dry_run: bool) -> tuple[list[str], list[ModelSpec]]:
    # Lädt venvAI.txt. Falls sie fehlt, wird (außer im Dry-Run) eine
    # sinnvolle Standarddatei angelegt und die Defaults zurückgegeben.
    if cfg_path.exists():
        try:
            lines = cfg_path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            warn(f"Paket-/Modell-Liste konnte nicht gelesen werden ({exc}).")
            return list(DEFAULT_AI_PACKAGES), [
                ModelSpec(
                    rel_path=Path("weights") / "RealESRGAN_x4plus.pth",
                    url=REAL_ESRGAN_URL,
                )
            ]
        return parse_venv_ai_lines(lines, cfg_path)

    # Datei existiert noch nicht → mit sinnvollem Inhalt erzeugen
    log(f"{cfg_path} fehlt – lege Standard-venvAI.txt an.")

    default_text = (
        "# venvAI.txt – AI-spezifische Pakete und Modelle\n"
        "#\n"
        "# Syntax:\n"
        "#   pkg <pip-name oder Spec>\n"
        "#   model <relativer/pfad/zur/datei> <download-url> [sha256]\n"
        "#\n"
        "# Beispiele:\n"
        "#   pkg torch\n"
        "#   pkg torchvision\n"
        "#   pkg realesrgan\n"
        "#   model weights/RealESRGAN_x4plus.pth {url}\n"
        "#\n"
        "# Du kannst weitere Pakete/Modelle einfach unten anhängen.\n"
        "#\n"
        "pkg torch\n"
        "pkg torchvision\n"
        "pkg realesrgan\n"
        "pkg basicsr\n"
        "pkg facexlib\n"
        "pkg gfpgan\n"
        "pkg opencv-python\n"
        "pkg Pillow\n"
        "pkg numpy\n"
        "pkg scipy\n"
        "pkg requests\n"
        "pkg tqdm\n"
        "pkg pyyaml\n"
        "\n"
        "model weights/RealESRGAN_x4plus.pth {url}\n"
    ).format(url=REAL_ESRGAN_URL)

    if not dry_run:
        try:
            cfg_path.write_text(default_text, encoding="utf-8")
            log(f"Standard-venvAI.txt geschrieben: {cfg_path}")
        except OSError as exc:
            warn(
                f"venvAI.txt konnte nicht geschrieben werden ({exc}). "
                "Verwende Standardwerte nur im Speicher."
            )

    packages = list(DEFAULT_AI_PACKAGES)
    models = [
        ModelSpec(
            rel_path=Path("weights") / "RealESRGAN_x4plus.pth",
            url=REAL_ESRGAN_URL,
        )
    ]
    return packages, models


def download_model_file(target: Path, url: str, sha256: str | None, dry_run: bool) -> bool:
    if target.exists():
        log(f"Modell bereits vorhanden: {target}")
        return True

    if dry_run:
        log(f"[dry-run] Download {url} -> {target}")
        return True

    target.parent.mkdir(parents=True, exist_ok=True)
    log(f"Lade Modell herunter: {url}")

    try:
        with urlopen(url) as resp, open(target, "wb") as f:
            hasher = hashlib.sha256() if sha256 else None
            while True:
                chunk = resp.read(8192)
                if not chunk:
                    break
                f.write(chunk)
                if hasher:
                    hasher.update(chunk)
    except Exception as exc:  # noqa: BLE001
        err(f"Download fehlgeschlagen ({url}): {exc}")
        try:
            if target.exists():
                target.unlink()
        except OSError:
            pass
        return False

    if sha256:
        digest = hasher.hexdigest()  # type: ignore[union-attr]
        if digest.lower() != sha256.lower():
            warn(
                f"SHA256-Prüfsumme stimmt nicht! Erwartet {sha256}, erhalten {digest}. "
                f"Datei: {target}"
            )
        else:
            log(f"SHA256-Prüfsumme OK für {target}")

    return True


def download_models(base_dir: Path, models: Sequence[ModelSpec], dry_run: bool) -> bool:
    if not models:
        log("Keine Modelle in venvAI.txt definiert – überspringe Downloads.")
        return True

    ok = True
    for spec in models:
        target = base_dir / spec.rel_path
        if not download_model_file(target, spec.url, spec.sha256, dry_run):
            ok = False
    return ok


def main(argv: Sequence[str]) -> int:
    dry_run = "--dry-run" in argv or "--check" in argv

    script_dir = Path(__file__).resolve().parent
    cfg_path = script_dir / "venvAI.txt"

    if dry_run:
        log("Modus: --dry-run (es werden keine Änderungen vorgenommen).")

    # 1. venv bestimmen
    if in_venv():
        python_bin = Path(sys.executable)
        venv_root = Path(sys.prefix)
        log(f"{ICON_VENV} Aktive venv erkannt: {venv_root}")
    else:
        found = find_existing_venv(script_dir)
        if not found:
            err(
                "Keine bestehende .venv gefunden.\n"
                "Bitte zuerst die Basis-Installation (install.py / Install-PuPy) "
                "laufen lassen, damit die venv angelegt wird."
            )
            return 1
        python_bin = found
        venv_root = found.parent.parent
        log(f"{ICON_VENV} Verwende bestehende venv: {venv_root}")

    # 2. venvAI.txt laden (oder mit Defaults anlegen)
    packages, models = load_venv_ai(cfg_path, dry_run)

    # 3. Pakete installieren
    ok_pkgs = pip_install(python_bin, packages, dry_run)

    # 4. Modelle herunterladen
    ok_models = download_models(script_dir, models, dry_run)

    # 5. Zusammenfassung
    print(f"{ICON_SUM} Übersicht:")
    print(f"  {ICON_MODE} Modus: {'Dry-Run (keine Änderungen)' if dry_run else 'Ausgeführt'}")
    print(f"  {ICON_VENV} venv:  {venv_root}")
    source_label = cfg_path if cfg_path.exists() else "Defaults (im Script)"
    print(f"  {ICON_PKGS} Pakete: {len(packages)} (Quelle: {source_label})")
    print(f"  {ICON_MODEL} Modelle: {len(models)} aus venvAI.txt")

    return 0 if (ok_pkgs and ok_models) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
