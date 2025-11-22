import argparse
import os
import shutil
import sys
import tempfile

import PyImgH
import PyImgCut


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="PyIMagic – Kombiniert PyImgH (Hintergrund) und PyImgCut (Zuschnitt).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--h",
        dest="do_h",
        action="store_true",
        help="PyImgH ausführen (Maskierung/Transparenz).",
    )
    parser.add_argument(
        "--cut",
        dest="do_cut",
        action="store_true",
        help="PyImgCut ausführen (auf Inhalt zuschneiden).",
    )
    parser.add_argument(
        "-i",
        "--input",
        default=os.path.abspath(os.getcwd()),
        help="Eingabeordner mit Bildern.",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Zielordner für das Endergebnis. Wird abhängig von den Schritten vorbelegt.",
    )
    parser.add_argument(
        "--keep-intermediate",
        action="store_true",
        help="Zwischenordner nach Mehrfach-Schritten behalten.",
    )
    parser.add_argument(
        "--silent",
        action="store_true",
        help="Nur minimale Ausgaben anzeigen.",
    )
    args = parser.parse_args()

    if not args.do_h and not args.do_cut:
        parser.print_help()
        sys.exit(1)
    return args


def determine_output_dir(steps, input_dir, provided_output):
    """Bestimmt den endgültigen Ausgabeordner."""
    if provided_output:
        return os.path.abspath(provided_output)

    if steps == ["h"]:
        return os.path.join(input_dir, "Img")
    if steps == ["cut"]:
        return os.path.join(input_dir, "ImgCut")
    # Kombination: nur ein finales Verzeichnis
    return os.path.join(input_dir, "Img")


def main():
    args = parse_args()

    steps = []
    if args.do_h:
        steps.append("h")
    if args.do_cut:
        steps.append("cut")

    input_dir = os.path.abspath(args.input)
    final_output = determine_output_dir(steps, input_dir, args.output)

    if not os.path.isdir(input_dir):
        print(f"Eingabeordner existiert nicht: {input_dir}")
        sys.exit(1)

    if not args.silent:
        print(f"Schritte: {' -> '.join(steps)}")
        print(f"Eingabe: {input_dir}")
        print(f"Endausgabe: {final_output}")

    current_input = input_dir
    temp_dirs = []

    for idx, step in enumerate(steps):
        is_last = idx == len(steps) - 1
        target_output = final_output if is_last else tempfile.mkdtemp(
            dir=input_dir, prefix="pyimagic_tmp_"
        )
        if not is_last:
            temp_dirs.append(target_output)

        if step == "h":
            processed = PyImgH.run_from_magic(current_input, target_output, silent=args.silent)
        elif step == "cut":
            processed = PyImgCut.run_from_magic(current_input, target_output, silent=args.silent)
        else:
            print(f"Unbekannter Schritt: {step}")
            sys.exit(1)

        if processed == 0:
            print("Warnung: Keine passenden Dateien gefunden.")

        current_input = target_output

    if temp_dirs and not args.keep_intermediate:
        for temp in temp_dirs:
            shutil.rmtree(temp, ignore_errors=True)

    if not args.silent:
        print("Fertig.")


if __name__ == "__main__":
    main()
