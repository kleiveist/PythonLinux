#!/usr/bin/env python3
import importlib.util
import os

BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"
GREEN = "\033[32m"
BLUE = "\033[34m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
RED = "\033[31m"


def line() -> None:
    print(f"{DIM}────────────────────────────────────────────────────────────{RESET}")


def title() -> None:
    os.system("clear")
    print(f"\n{BOLD}🖼️ PyImage Leitfaden (PyImgH / PyImgD / PyImgCut / PyIMagic){RESET}")
    line()
    print(f"{DIM}Dieses Skript führt keine Bildverarbeitung aus,")
    print("sondern erklärt dir die empfohlenen Schritte und Befehle." + RESET)


def step(nr: int, text: str) -> None:
    print(f"\n{BOLD}{BLUE}➤ Schritt {nr}:{RESET} {text}")


def cmd(text: str) -> None:
    print(f"   {CYAN}⮡ Befehl:{RESET} {text}")


def info(text: str) -> None:
    print(f"   {YELLOW}ℹ{RESET} {text}")


def warn(text: str) -> None:
    print(f"   {RED}⚠{RESET} {text}")


def good(text: str) -> None:
    print(f"   {GREEN}✔{RESET} {text}")


def overview() -> None:
    print(f"\n{BOLD}📂 Ordner bin/PyImage im Überblick{RESET}")
    line()
    info("PyImgH: Freistellt dunklere Motive, macht den Rest transparent. Ausgabe: Img/")
    info("PyImgD: Gleiche Maske, aber invertiert – Motive transparent, Hintergrund bleibt.")
    info("PyImgCut: Schneidet Bilder auf sichtbare Pixel zu. Ausgabe: ImgCut/")
    info("PyIMagic: Orchestrator, führt --h/--cut nacheinander aus, Input per -i, Output per -o.")
    info("Unterstützte Formate: .png, .jpg, .jpeg, .bmp, .tiff")


def check_dependencies() -> None:
    print(f"\n{BOLD}🧰 Voraussetzungen prüfen{RESET}")
    line()
    packages = {"Pillow": "PIL", "NumPy": "numpy", "OpenCV": "cv2"}
    for name, module in packages.items():
        if importlib.util.find_spec(module):
            good(f"{name} ({module}) ist verfügbar.")
        else:
            warn(f"{name} ({module}) fehlt noch.")
    info("Installiere sie am besten in einer venv (siehe Schritt 1).")
    cmd("pip install pillow numpy opencv-python")


def show_steps() -> None:
    step(1, "Umgebung vorbereiten 🧱")
    info("Optionale venv, damit Pillow/NumPy/OpenCV isoliert bleiben.")
    cmd("python3 -m venv .venv && source .venv/bin/activate")
    cmd("pip install pillow numpy opencv-python")
    info("Alternativ: pip install -r bin/PyImage/venv.txt")

    step(2, "Schneller Freisteller: PyImgH (Motive behalten)")
    info("Arbeitet immer auf dem aktuellen Arbeitsverzeichnis und legt Img/ an.")
    cmd("cd <bilderordner> && python3 <repo>/bin/PyImage/PyImgH.py")
    info("Ideal, wenn dein Motiv dunkler als der Hintergrund ist.")

    step(3, "Inverse Maske: PyImgD (Motive entfernen)")
    info("Gleiche Parameter wie PyImgH, aber setzt erkannte Objekte transparent.")
    cmd("cd <bilderordner> && python3 <repo>/bin/PyImage/PyImgD.py")

    step(4, "Auf Inhalt zuschneiden: PyImgCut")
    info("Findet sichtbare Pixel (Alpha oder einheitlicher Hintergrund) und schneidet eng zu.")
    info("Ausgabe: ImgCut/ neben deinen Originalen.")
    cmd("cd <bilderordner> && python3 <repo>/bin/PyImage/PyImgCut.py")

    step(5, "Workflows kombinieren mit PyIMagic")
    info("Flags wählen: --h (Freistellen), --cut (Zuschneiden), oder beides.")
    cmd("python3 bin/PyImage/PyIMagic.py --h --cut -i <bilder> -o <ziel>")
    cmd("python3 bin/PyImage/PyIMagic.py --cut -i <bilder>")
    info("Ohne -o landen Ergebnisse bei --h/--h --cut in <input>/Img, bei nur --cut in ImgCut/.")
    info("--keep-intermediate behält Zwischenordner, sonst werden sie entfernt.")

    step(6, "Parameter feinjustieren")
    info("PyImgH/PyImgD: SETTINGS['processing'] (tolerance, min_icon_size, kernel_size,")
    info("iterations, weight_factor, dark_threshold_offset, canny.threshold1/2).")
    info("PyImgCut: alpha_threshold, color_tolerance, min_content_pixels.")
    info("Logging aktivieren: SETTINGS['logging']['log_enabled'] = True schreibt extraction_log.txt.")
    info("Eingabe-/Ausgabeordner kannst du in SETTINGS['paths'] pro Skript anpassen.")


def summary() -> None:
    line()
    print(f"{BOLD}📋 Kurzablauf{RESET}")
    print(f"  {GREEN}1.{RESET} Pakete (Pillow, NumPy, OpenCV) installieren – gern in einer venv.")
    print(f"  {GREEN}2.{RESET} PyImgH/PyImgD/PyImgCut im Bilderordner ausführen oder PyIMagic mit -i/-o nutzen.")
    print(f"  {GREEN}3.{RESET} Ergebnisse liegen in Img/ oder ImgCut/; Parameter bei Bedarf in den Skripten anpassen.\n")
    print(f"{DIM}Hinweis: Dieses Skript ist nur eine Anleitung. Nichts wird automatisch ausgeführt.{RESET}")
    line()


def main() -> None:
    title()
    overview()
    check_dependencies()
    show_steps()
    summary()


if __name__ == "__main__":
    main()
