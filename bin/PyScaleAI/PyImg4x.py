"""
Einfaches Beispielskript zum Hochskalieren mit Real-ESRGAN und anschließender
Nachschärfung per Unsharp-Mask.

Verhalten:
- Standard: Alle Bilder im aktuellen Ordner verarbeiten, Ausgabe in img4x.
- --all:    Rekursiv auch Unterordner, Ausgabe in img{scale}x (relativer Pfad bleibt).
- --2x / --4x / --8x steuern den Skalierungsfaktor (Standard 4x). Passende Gewichte
  müssen bereitliegen.
"""

import argparse
import os
from pathlib import Path
from typing import List
import cv2
import numpy as np
from realesrgan import RealESRGANer
from basicsr.archs.rrdbnet_arch import RRDBNet

SUPPORTED_FORMATS = (".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp")
MODEL_PATH = os.path.join(os.path.dirname(__file__), "weights", "RealESRGAN_x4plus.pth")


def build_upsampler(model_path: str, scale: int, half: bool = True, tile: int = 0) -> RealESRGANer:
    """Erzeugt den RealESRGAN-Upsampler mit RRDBNet-Architektur."""
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Modell nicht gefunden: {model_path}")

    model = RRDBNet(
        num_in_ch=3,
        num_out_ch=3,
        num_feat=64,
        num_block=23,
        num_grow_ch=32,
        scale=scale,
    )

    return RealESRGANer(
        scale=scale,
        model_path=model_path,
        model=model,
        tile=tile,       # 0 = kein Tiling; bei wenig VRAM ggf. 128 oder 256
        tile_pad=10,
        pre_pad=0,
        half=half,       # False setzen, wenn keine FP16-Unterstützung vorhanden
    )


def upscale_and_sharpen_file(
    upsampler: RealESRGANer,
    input_path: Path,
    output_path: Path,
    outscale: int,
    sigma: float = 1.0,
    amount: float = 1.5,
) -> None:
    """Lädt ein Bild, skaliert es hoch und schärft es leicht nach."""
    img = cv2.imread(str(input_path), cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(f"Bild konnte nicht geladen werden: {input_path}")

    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    output, _ = upsampler.enhance(img, outscale=outscale)

    gaussian = cv2.GaussianBlur(output, (0, 0), sigmaX=sigma, sigmaY=sigma)
    sharp = cv2.addWeighted(output, amount, gaussian, -(amount - 1), 0)

    sharp_bgr = cv2.cvtColor(sharp, cv2.COLOR_RGB2BGR)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), sharp_bgr)


def iter_images(base: Path, recursive: bool, skip_dir: Path) -> List[Path]:
    """Sammelt Bilddateien im Basisordner (optional rekursiv)."""
    images: list[Path] = []
    for root, dirs, files in os.walk(base):
        root_path = Path(root)
        if skip_dir in root_path.parents or root_path == skip_dir:
            dirs[:] = []
            continue
        if not recursive:
            dirs[:] = []  # nicht in Unterordner absteigen
        for name in files:
            if name.lower().endswith(SUPPORTED_FORMATS):
                images.append(root_path / name)
    return images


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Real-ESRGAN Upscaling mit Nachschärfung")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--2x", dest="scale", action="store_const", const=2, help="2x Upscaling")
    group.add_argument("--4x", dest="scale", action="store_const", const=4, help="4x Upscaling (Standard)")
    group.add_argument("--8x", dest="scale", action="store_const", const=8, help="8x Upscaling")
    parser.add_argument("--all", action="store_true", help="Alle Bilder rekursiv auch in Unterordnern verarbeiten")
    parser.add_argument("--model-path", default=MODEL_PATH, help="Pfad zum Real-ESRGAN Modell (.pth)")
    parser.set_defaults(scale=4)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    base_dir = Path.cwd()
    output_dir = base_dir / f"img{args.scale}x"

    images = iter_images(base_dir, recursive=args.all, skip_dir=output_dir)
    if not images:
        print("Keine passenden Bilddateien gefunden.")
        return

    upsampler = build_upsampler(args.model_path, scale=args.scale)
    processed = 0
    for src in images:
        rel = src.relative_to(base_dir)
        target = output_dir / rel
        upscale_and_sharpen_file(upsampler, src, target, outscale=args.scale)
        processed += 1

    print(f"Fertig! {processed} Dateien -> {output_dir}")


if __name__ == "__main__":
    main()
