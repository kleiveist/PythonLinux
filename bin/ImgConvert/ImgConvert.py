#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Einfacher Bild-Converter für das Terminal.

Beispiele:
  - Nur im aktuellen Ordner:
      python img_convert.py --png --ico
      python img_convert.py --jpg --webp
  - Alternativ explizit:
      python img_convert.py --from png --to ico
  - Rekursiv (alle Unterordner):
      python img_convert.py --png --ico --all
  - ICO mit festen Größen:
      python img_convert.py --png --ico --ico-sizes 16,32,48,64,128,256
  - JPEG ohne Alpha (Hintergrundfarbe setzen):
      python img_convert.py --png --jpg --bg "#1e1e1e" --quality 90
  - Nur zeigen, was passieren würde:
      python img_convert.py --png --webp --dry-run
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Iterable, List, Tuple, Optional

from PIL import Image

SUPPORTED = {
    "png": "PNG",
    "jpg": "JPEG",
    "jpeg": "JPEG",
    "webp": "WEBP",
    "wbp": "WEBP",   # Tippfehler-Toleranz
    "bmp": "BMP",
    "tif": "TIFF",
    "tiff": "TIFF",
    "ico": "ICO",
}

LOSSY_QUALITY_DEFAULT = 85
DEFAULT_ICO_SIZES = [16, 32, 48, 64, 128, 256]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Konvertiert Bilder im aktuellen Ordner (oder rekursiv mit --all)."
    )
    # generische Variante
    p.add_argument("--from", dest="from_fmt", help="Quellformat, z. B. png, jpg, webp, tiff, ico")
    p.add_argument("--to", dest="to_fmt", help="Zielformat, z. B. ico, webp, jpg, png")

    # Kurzschreibweise in Reihenfolge der Angabe: --png --ico
    # Wir sammeln sie in 'fmts' und interpretieren fmts[0] -> from, fmts[1] -> to
    for f in ["png", "jpg", "jpeg", "webp", "wbp", "bmp", "tif", "tiff", "ico"]:
        p.add_argument(f"--{f}", dest="fmts", action="append_const", const=f,
                       help=f"{f.upper()} als Quelle/Ziel (Position entscheidet)")

    p.add_argument("--all", action="store_true",
                   help="Alle Unterordner rekursiv verarbeiten")
    p.add_argument("--outdir", default=None,
                   help="Zielbasisordner (Standard: <Zielformat> im aktuellen Verzeichnis)")
    p.add_argument("--overwrite", action="store_true",
                   help="Existierende Zieldateien überschreiben")
    p.add_argument("--quality", type=int, default=LOSSY_QUALITY_DEFAULT,
                   help=f"Qualität für verlustbehaftete Formate (JPEG/WEBP). Standard: {LOSSY_QUALITY_DEFAULT}")
    p.add_argument("--lossless", action="store_true",
                   help="WEBP verlustfrei speichern (ignoriert Qualität)")
    p.add_argument("--bg", default="#000000",
                   help='Hintergrundfarbe zum Flachrechnen von Alpha (bei JPEG), z. B. "#000000" oder "white"')
    p.add_argument("--ico-sizes", default=",".join(map(str, DEFAULT_ICO_SIZES)),
                   help="Kommagetrennte Größen für ICO (z. B. 16,32,48,64,128,256)")
    p.add_argument("--dry-run", action="store_true",
                   help="Nur anzeigen, was konvertiert würde")
    return p.parse_args()


def normalize_fmt(fmt: str) -> str:
    fmt = fmt.lower()
    if fmt == "wbp":
        fmt = "webp"
    if fmt == "jpg":
        fmt = "jpeg"
    if fmt == "tif":
        fmt = "tiff"
    return fmt


def parse_color(col: str):
    # Pillow akzeptiert Farbnamen und #RRGGBB direkt; wir reichen einfach durch
    return col


def parse_sizes(s: str) -> List[Tuple[int, int]]:
    out: List[Tuple[int, int]] = []
    for part in s.split(","):
        part = part.strip()
        if not part:
            continue
        v = int(part)
        out.append((v, v))
    return out


def is_supported_ext(ext: str) -> bool:
    return ext.lower().lstrip(".") in SUPPORTED


def iter_files(root: Path, ext: str, recursive: bool) -> Iterable[Path]:
    ext = ext.lower().lstrip(".")
    if not recursive:
        for p in root.iterdir():
            if p.is_file() and p.suffix.lower().lstrip(".") == ext:
                yield p
    else:
        for dirpath, _, filenames in os.walk(root):
            d = Path(dirpath)
            for name in filenames:
                if name.lower().endswith("." + ext):
                    yield d / name


def ensure_parent(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)


def flatten_alpha_for_jpeg(img: Image.Image, bg_color) -> Image.Image:
    # Wenn Alpha vorhanden, auf Hintergrundfarbe compositen
    if img.mode in ("RGBA", "LA") or ("transparency" in img.info):
        base = Image.new("RGB", img.size, bg_color)
        if img.mode in ("RGBA", "LA"):
            alpha = img.getchannel("A") if "A" in img.getbands() else None
            base.paste(img.convert("RGBA"), mask=alpha)
        else:
            # palettiertes Bild mit Transparenz
            base.paste(img.convert("RGBA"), mask=img.convert("RGBA").split()[-1])
        return base
    # Sicherstellen, dass JPEG ein RGB-Bild bekommt
    return img.convert("RGB")


def save_image(img: Image.Image, out_path: Path, to_fmt: str,
               quality: int, lossless: bool, bg_color, ico_sizes: List[Tuple[int, int]]):
    pil_fmt = SUPPORTED[to_fmt]

    save_kwargs = {}
    if pil_fmt == "JPEG":
        img = flatten_alpha_for_jpeg(img, bg_color)
        save_kwargs.update(dict(quality=quality, optimize=True, progressive=True))
    elif pil_fmt == "WEBP":
        if lossless:
            save_kwargs.update(dict(lossless=True, method=6))
        else:
            save_kwargs.update(dict(quality=quality, method=6))
    elif pil_fmt == "PNG":
        save_kwargs.update(dict(optimize=True))
    elif pil_fmt == "TIFF":
        save_kwargs.update(dict(compression="tiff_lzw"))
    elif pil_fmt == "ICO":
        # Pillow skaliert automatisch bei Übergabe von sizes
        save_kwargs.update(dict(sizes=ico_sizes))

    img.save(out_path, format=pil_fmt, **save_kwargs)


def main():
    args = parse_args()

    # Quelle/Ziel auswerten
    from_fmt = args.from_fmt
    to_fmt = args.to_fmt

    if (from_fmt is None or to_fmt is None) and args.fmts:
        # Reihenfolge der Flags entscheidet: erstes = from, zweites = to
        if len(args.fmts) >= 1 and from_fmt is None:
            from_fmt = args.fmts[0]
        if len(args.fmts) >= 2 and to_fmt is None:
            to_fmt = args.fmts[1]

    if not from_fmt or not to_fmt:
        print("Fehler: Bitte Quell- und Zielformat angeben, z. B. '--png --ico' oder '--from png --to ico'.")
        sys.exit(2)

    from_fmt = normalize_fmt(from_fmt)
    to_fmt = normalize_fmt(to_fmt)

    if from_fmt not in SUPPORTED or to_fmt not in SUPPORTED:
        print(f"Fehler: Nicht unterstütztes Format. Unterstützt: {', '.join(sorted(set(SUPPORTED.keys())))}")
        sys.exit(2)

    if from_fmt == to_fmt:
        print("Hinweis: Quell- und Zielformat sind identisch – nichts zu tun.")
        sys.exit(0)

    root = Path.cwd()
    out_base = Path(args.outdir) if args.outdir else (root / to_fmt.lower())

    bg_color = parse_color(args.bg)
    ico_sizes = parse_sizes(args.ico_sizes)

    files = list(iter_files(root, from_fmt, args.all))
    if not files:
        scope = "rekursiv" if args.all else "im aktuellen Ordner"
        print(f"Keine Dateien mit .{from_fmt} {scope} gefunden.")
        sys.exit(0)

    # Nicht in bereits existierenden Zielordnern nach Ziel-Dateien greifen
    total = 0
    converted = 0
    skipped = 0
    errors = 0

    for src in files:
        # relative Ablage in out_base (Struktur spiegeln)
        rel = src.relative_to(root)
        rel_dir = rel.parent
        dst_name = src.stem + "." + ( "jpg" if to_fmt == "jpeg" else to_fmt )
        dst = out_base / rel_dir / dst_name

        # Quelle darf nicht bereits im Zielordner liegen
        if out_base in src.parents:
            continue

        total += 1

        if dst.exists() and not args.overwrite:
            print(f"Übersprungen (existiert): {dst}")
            skipped += 1
            continue

        if args.dry_run:
            print(f"[DRY] {src} -> {dst}")
            converted += 1
            continue

        try:
            ensure_parent(dst)
            with Image.open(src) as img:
                save_image(img, dst, to_fmt, args.quality, args.lossless, bg_color, ico_sizes)
            print(f"OK: {src} -> {dst}")
            converted += 1
        except Exception as e:
            print(f"FEHLER: {src} -> {dst}: {e}")
            errors += 1

    print(f"Fertig. Gesamt: {total}, konvertiert: {converted}, übersprungen: {skipped}, Fehler: {errors}")
    if not args.all:
        print(f"Ausgabeordner: {out_base}")
    else:
        print(f"Ausgabe-Basisordner (mit gespiegelt. Struktur): {out_base}")


if __name__ == "__main__":
    main()
