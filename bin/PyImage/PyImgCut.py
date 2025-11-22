import os
from typing import Optional, Tuple

import numpy as np
from PIL import Image

# =====================================================================================
# EINSTELLUNGEN
# =====================================================================================
SETTINGS = {
    "paths": {
        "input_folder": os.path.abspath(os.getcwd()),  # Automatischer Eingabeordner
        "output_folder": "ImgCut",  # Ausgabeordner für zugeschnittene Bilder
        "supported_formats": (".png", ".jpg", ".jpeg", ".bmp", ".tiff"),
    },
    "processing": {
        "alpha_threshold": 5,        # >5 zählt als sichtbarer Pixel bei transparentem BG
        "color_tolerance": 10,       # Max. erlaubter Farbunterschied zum Hintergrund
        "min_content_pixels": 10,    # Mindestanzahl sichtbarer Pixel für einen Zuschnitt
    },
}


# =====================================================================================
# HILFSFUNKTIONEN
# =====================================================================================
def print_settings() -> None:
    """Gibt die aktiven Einstellungen aus."""
    print("\n" + "=" * 80)
    print(" PYIMG CUT ".center(80, "="))
    print("=" * 80)
    print(f"Eingabeordner : {SETTINGS['paths']['input_folder']}")
    print(
        f"Ausgabeordner : "
        f"{os.path.join(SETTINGS['paths']['input_folder'], SETTINGS['paths']['output_folder'])}"
    )
    print(f"Formate       : {', '.join(SETTINGS['paths']['supported_formats'])}")
    print(
        f"Alpha-Schwelle: {SETTINGS['processing']['alpha_threshold']} | "
        f"Farb-Toleranz: {SETTINGS['processing']['color_tolerance']}"
    )
    print("=" * 80 + "\n")


def estimate_background_color(rgb_img: np.ndarray) -> np.ndarray:
    """Schätzt den einheitlichen Hintergrund anhand der vier Bildecken."""
    h, w, _ = rgb_img.shape
    samples = np.stack(
        [
            rgb_img[0, 0],
            rgb_img[0, w - 1],
            rgb_img[h - 1, 0],
            rgb_img[h - 1, w - 1],
        ],
        axis=0,
    )
    return samples.mean(axis=0).astype(np.uint8)


def build_content_mask(np_img: np.ndarray) -> np.ndarray:
    """
    Erstellt eine Maske aller sichtbaren Pixel.

    1) Transparente Hintergründe: nutzt den Alphakanal.
    2) Einheitliche Hintergründe: vergleicht RGB mit dem geschätzten Hintergrund.
    """
    alpha_channel = np_img[:, :, 3]
    alpha_mask = alpha_channel > SETTINGS["processing"]["alpha_threshold"]

    if np.any(alpha_mask):
        return alpha_mask

    bg_color = estimate_background_color(np_img[:, :, :3]).astype(np.int16)
    diff = np.abs(np_img[:, :, :3].astype(np.int16) - bg_color)
    max_channel_diff = diff.max(axis=2)
    return max_channel_diff > SETTINGS["processing"]["color_tolerance"]


def crop_to_content(img: Image.Image) -> Optional[Image.Image]:
    """Schneidet das Bild auf den sichtbaren Inhalt zu."""
    np_img = np.array(img.convert("RGBA"))
    mask = build_content_mask(np_img)

    coords = np.argwhere(mask)
    if coords.size < SETTINGS["processing"]["min_content_pixels"]:
        return None

    y_min, x_min = coords.min(axis=0)
    y_max, x_max = coords.max(axis=0)
    bbox: Tuple[int, int, int, int] = (x_min, y_min, x_max + 1, y_max + 1)
    return img.crop(bbox)


def process_image(src_path: str, dst_path: str) -> bool:
    """Verarbeitet eine einzelne Datei."""
    try:
        with Image.open(src_path) as img:
            cropped = crop_to_content(img)
            if cropped is None:
                print(f"Übersprungen (kein Inhalt erkannt): {os.path.basename(src_path)}")
                return False

            os.makedirs(os.path.dirname(dst_path), exist_ok=True)
            cropped.save(dst_path)
            print(f"Geschnitten: {os.path.basename(src_path)} -> {dst_path}")
            return True
    except Exception as exc:  # noqa: BLE001
        print(f"Fehler bei {src_path}: {exc}")
        return False


# =====================================================================================
# STARTPUNKT
# =====================================================================================
if __name__ == "__main__":
    print_settings()

    input_dir = SETTINGS["paths"]["input_folder"]
    output_dir = os.path.join(input_dir, SETTINGS["paths"]["output_folder"])
    os.makedirs(output_dir, exist_ok=True)

    processed = 0
    for filename in os.listdir(input_dir):
        if not filename.lower().endswith(SETTINGS["paths"]["supported_formats"]):
            continue

        src = os.path.join(input_dir, filename)
        dst = os.path.join(output_dir, filename)

        if process_image(src, dst):
            processed += 1

    print(f"\nFertig! {processed} Bilder zugeschnitten.")
    print(f"Ausgabe: {output_dir}")
