#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SCopy.py – Check & Copy in einem Skript kombiniert.

Neu: Fallback-Suche im Basisordner + Strecke-{nr}.pdf Handling
--------------------------------------------------------------
- Wenn eine erwartete PDF in den Quell-Unterordnern (FOP/SR/SK) *nicht* gefunden wird,
  wird zusätzlich im Basisordner selbst gesucht (Basis/{name}.pdf). Logs zeigen die Quelle an.
- Zusätzlich werden nun pro Strecke die Übersicht-PDFs "Strecke {nr}.pdf" geprüft und kopiert.
  Gesucht wird im Basisordner und im Ordner "Strecke" (Root), kopiert wird in
  "Strecke/Strecke {nr}/Strecke {nr}.pdf".

Funktionen:
- --check : Prüft, ob für jede Strecke die benötigten PDFs vorhanden sind (FOP/SR/SK oder Basis)
            und ob "Strecke {nr}.pdf" bereits im Ziel liegt bzw. als Quelle vorhanden ist.
- --copy  : Kopiert die vorhandenen PDFs in den jeweiligen Streckenordner, inkl. "Strecke {nr}.pdf".
- Ohne Flags: Erst Check, danach Nachfrage "Kopieren? (J/N)" und ggf. Kopieren.

Ordner-Zuordnung (unterhalb des Basisordners):
- FOP_FOLDER = "FOP"
- SR_FOLDER  = "SR"
- SK_FOLDER  = "SK"
- ST_FOLDER  = "Strecke"   → Zielbasis für Unterordner "Strecke {nr}"

Hinweis:
- Es werden Dateinamen aus den Feldern 'fop', 'aop', 'abp_start', 'abp_ziel' erwartet (mit .pdf).
- Der Basisordner ist standardmäßig das aktuelle Arbeitsverzeichnis, kann aber mit --base gesetzt werden.
"""

import os
import sys
import shutil
import time
import argparse
from collections import defaultdict

# =========================
#   Datenbasis
# =========================

strecken_daten = [
    {"nr": 3,  "fop": "G701R404SK04E15FOP1", "aop": "=G701+R404",    "abp_start": "=G701+R404SK04", "abp_ziel": "=G809+EGSK99"},
    {"nr": 4,  "fop": "G809EGSK99E8FOP1",    "aop": "NULL",          "abp_start": "=G809+EGSK99",   "abp_ziel": "=G805+SR00SK99"},
    {"nr": 5,  "fop": "G701R404SK04E11FOP1", "aop": "=G701+R404",    "abp_start": "=G701+R404SK04", "abp_ziel": "=G602+R215SK99"},
    {"nr": 6,  "fop": "G701R404SK04E17FOP1", "aop": "=G701+R404",    "abp_start": "=G701+R404SK04", "abp_ziel": "=G401+OG1SK99"},
    {"nr": 7,  "fop": "G701R404SK04E18FOP1", "aop": "=G701+R404",    "abp_start": "=G701+R404SK04", "abp_ziel": "=G702+R18SK99"},
    {"nr": 8,  "fop": "G701R404SK04E14FOP1", "aop": "=G701+R404",    "abp_start": "=G701+R404SK04", "abp_ziel": "=G705+EGSK99"},
    {"nr": 9,  "fop": "G701R404SK04E12FOP1", "aop": "=G701+R404",    "abp_start": "=G701+R404SK04", "abp_ziel": "=G618+R1203SK99"},
    {"nr": 10, "fop": "SR21SK03E8FOP1",      "aop": "=SR21",         "abp_start": "=SR21+SK03",     "abp_ziel": "=G615.MW1+SK99"},
    {"nr": 11, "fop": "SR21SK03E9FOP1",      "aop": "=SR21",         "abp_start": "=SR21+SK03",     "abp_ziel": "=G515+R5008SK11"},
    {"nr": 12, "fop": "SR36SK07E19FOP1",     "aop": "=SR36",         "abp_start": "=SR36+SK07",     "abp_ziel": "=G718+KGSK99"},
    {"nr": 13, "fop": "SR36SK07E17FOP1",     "aop": "=SR36",         "abp_start": "=SR36+SK07",     "abp_ziel": "=G727+R9002SK99"},
    {"nr": 14, "fop": "SR21SK03E3FOP1",      "aop": "=SR21",         "abp_start": "=SR21+SK03",     "abp_ziel": "=G632+R6324SK99"},
    {"nr": 15, "fop": "SR21SK03E4FOP1",      "aop": "=SR21",         "abp_start": "=SR21+SK03",     "abp_ziel": "=SR41+SK99"},
    {"nr": 16, "fop": "SR21SK03E15FOP1",     "aop": "=SR21",         "abp_start": "=SR21+SK03",     "abp_ziel": "=G143+R168SK99"},
    {"nr": 17, "fop": "SR21SK03E14FOP1",     "aop": "=SR21",         "abp_start": "=SR21+SK03",     "abp_ziel": "=G213+R2SK99"},
    {"nr": 18, "fop": "SR21SK03E6FOP1",      "aop": "=SR21",         "abp_start": "=SR21+SK03",     "abp_ziel": "=G618+R1203SK99"},
    {"nr": 19, "fop": "SR21SK03E12FOP1",     "aop": "=SR21",         "abp_start": "=SR21+SK03",     "abp_ziel": "=G414+R6302SK99"},
    {"nr": 20, "fop": "G414R6302SK99E21FOP1","aop": "NULL",          "abp_start": "=G414+R6302SK99","abp_ziel": "=G414+R6037SK99"},
    {"nr": 24, "fop": "G143R1680SK99E13FOP1","aop": "NULL",          "abp_start": "=G143+R168SK99", "abp_ziel": "=G144+EGSK99"},
    {"nr": 25, "fop": "G702R18SK99E6FOP1",   "aop": "NULL",          "abp_start": "=G702+R18SK99",  "abp_ziel": "=G702+OG1SK99"},
    {"nr": 26, "fop": "SR36SK07E22FOP1",     "aop": "=SR36",         "abp_start": "=SR36+SK07",     "abp_ziel": "=G622+R4107SK99"},
    {"nr": 27, "fop": "SR36SK07E23FOP1",     "aop": "=SR36",         "abp_start": "=SR36+SK07",     "abp_ziel": "=G622+R3004SK99"},
    {"nr": 28, "fop": "SR36SK07E25FOP1",     "aop": "=SR36",         "abp_start": "=SR36+SK07",     "abp_ziel": "=G622+R401SK99"},
    {"nr": 29, "fop": "SR36SK07E26FOP1",     "aop": "=SR36",         "abp_start": "=SR36+SK07",     "abp_ziel": "=G622.MW1+SK99"},
    {"nr": 30, "fop": "SR36SK07E28FOP1",     "aop": "=SR36",         "abp_start": "=SR36+SK07",     "abp_ziel": "=SR30+SK99"},
    {"nr": 31, "fop": "SR36SK07E20FOP1",     "aop": "=SR36",         "abp_start": "=SR36+SK07",     "abp_ziel": "=G+"},
    {"nr": 33, "fop": "SR21SK03E2FOP1",      "aop": "=SR21",         "abp_start": "=SR21+SK03",     "abp_ziel": "=SR36+SK07"},
]

# =========================
#   Ordner-Zuordnung
# =========================

FOP_FOLDER = "FOP"
SR_FOLDER  = "SR"
SK_FOLDER  = "SK"
ST_FOLDER  = "Strecke"   # Zielbasis: hier werden "Strecke {nr}"-Ordner angelegt


# =========================
#   Hilfsfunktionen
# =========================

def _pdf_path(base_folder: str, subfolder: str, name: str) -> str:
    """Erzeugt einen erwarteten PDF-Pfad im Unterordner."""
    return os.path.join(base_folder, subfolder, f"{name}.pdf")

def _pdf_base_path(base_folder: str, name: str) -> str:
    """Erzeugt den erwarteten PDF-Pfad direkt im Basisordner."""
    return os.path.join(base_folder, f"{name}.pdf")

def find_pdf(base_folder: str, subfolder: str, name: str):
    """
    Sucht die PDF zuerst im Unterordner (base/subfolder/name.pdf),
    ansonsten im Basisordner (base/name.pdf).
    Rückgabe: (pfad_oder_None, quelle_str) mit quelle_str in {"SUBFOLDER", "BASIS", None}
    """
    path_sub = _pdf_path(base_folder, subfolder, name)
    if os.path.isfile(path_sub):
        return path_sub, "SUBFOLDER"
    path_base = _pdf_base_path(base_folder, name)
    if os.path.isfile(path_base):
        return path_base, "BASIS"
    return None, None

def file_exists(base_folder: str, subfolder: str, name: str):
    """Wie find_pdf, aber nur Bool + Quelle."""
    p, src = find_pdf(base_folder, subfolder, name)
    return (p is not None), src

def ensure_strecke_folder(base_folder: str, nr: int) -> str:
    """Stellt sicher, dass der Zielordner 'Strecke/{"Strecke {nr}"}' existiert und gibt ihn zurück."""
    target = os.path.join(base_folder, ST_FOLDER, f"Strecke {nr}")
    os.makedirs(target, exist_ok=True)
    return target

def copy_pdf(base_folder: str, src_subfolder: str, name: str, dest_folder: str) -> (bool, str):
    """
    Kopiert eine PDF vom Quell-Unterordner ODER (Fallback) vom Basisordner in den Zielordner.
    Rückgabe: (erfolg_bool, quelle_str)
    """
    src_file, src = find_pdf(base_folder, src_subfolder, name)
    if src_file:
        os.makedirs(dest_folder, exist_ok=True)
        shutil.copy2(src_file, os.path.join(dest_folder, f"{name}.pdf"))
        return True, src
    return False, None

# ----- Strecke-{nr}.pdf Handling -----

def strecke_pdf_name(nr: int) -> str:
    return f"Strecke {nr}.pdf"

def find_strecke_pdf_source(base_folder: str, nr: int):
    """
    Sucht 'Strecke {nr}.pdf' zuerst im Basisordner,
    dann im Root 'Strecke' (nicht im Unterordner 'Strecke {nr}').
    Rückgabe: (pfad_oder_None, quelle_label: 'Basis'|'Strecke-Root'|None)
    """
    name = strecke_pdf_name(nr)
    path_base = os.path.join(base_folder, name)
    if os.path.isfile(path_base):
        return path_base, "Basis"
    path_st_root = os.path.join(base_folder, ST_FOLDER, name)
    if os.path.isfile(path_st_root):
        return path_st_root, "Strecke-Root"
    return None, None

def strecke_pdf_dest_path(base_folder: str, nr: int) -> str:
    return os.path.join(base_folder, ST_FOLDER, f"Strecke {nr}", strecke_pdf_name(nr))


# =========================
#   Kernfunktionen
# =========================

def strecken_check(base_folder: str) -> dict:
    """
    Prüft für jede Strecke:
    - Ordner 'Strecke/Strecke {nr}' existiert
    - FOP-File vorhanden (Quelle: Unterordner oder Basis)
    - AOP-File (falls nicht 'NULL') vorhanden (Quelle: Unterordner oder Basis)
    - ABP-Start vorhanden (Quelle: Unterordner oder Basis)
    - ABP-Ziel vorhanden (Quelle: Unterordner oder Basis)
    - 'Strecke {nr}.pdf' im Ziel vorhanden oder als Quelle auffindbar

    Schreibt ein Logfile 'StreckenCheck.txt' ins Basisverzeichnis.
    Gibt ein Fehler-Dict zurück (für interaktiven Modus).
    """
    logfile = os.path.join(base_folder, "StreckenCheck.txt")
    errors = defaultdict(list)

    with open(logfile, "w", encoding="utf-8") as log:
        def write(line: str = ""):
            log.write(line + "\n")

        write("🚦 StreckenCheck gestartet (mit Fallback in den Basisordner)")
        write("Zeit: " + time.strftime("%Y-%m-%d %H:%M:%S"))
        write("=" * 60)

        for ds in strecken_daten:
            nr = ds["nr"]
            write(f"\n➡️  Strecke {nr}")
            ordner = os.path.join(base_folder, ST_FOLDER, f"Strecke {nr}")
            if os.path.isdir(ordner):
                write("   📂 Ordner: ✅ vorhanden")
            else:
                write("   📂 Ordner: ❌ fehlt")
                errors["Ordner fehlt"].append(f"Strecke {nr}")

            # Übersicht 'Strecke {nr}.pdf' direkt unter Ordnerzeile
            dest_pdf = strecke_pdf_dest_path(base_folder, nr)
            if os.path.isfile(dest_pdf):
                write(f"   📄 Strecke {nr}: ✅ (im Zielordner)")
            else:
                src_pdf, src_label = find_strecke_pdf_source(base_folder, nr)
                if src_pdf:
                    write(f"   📄 Strecke {nr}: 📦 Quelle gefunden ({src_label})")
                else:
                    write(f"   📄 Strecke {nr}: ❌ fehlt")
                    errors["Strecke-PDF fehlt"].append(f"Strecke {nr}")

            # Funktion-FOP
            ok, src = file_exists(base_folder, FOP_FOLDER, ds["fop"])
            if ok:
                where = "Quelle: FOP" if src == "SUBFOLDER" else "Quelle: Basis"
                write(f"   📑 Funktion-FOP: {ds['fop']} ✅ ({where})")
            else:
                write(f"   📑 Funktion-FOP: {ds['fop']} ❌ fehlt")
                errors["Funktion-FOP fehlt"].append(f"Strecke {nr}")

            # AOP-Start
            if ds["aop"] != "NULL":
                ok, src = file_exists(base_folder, SR_FOLDER, ds["aop"])
                if ok:
                    where = "Quelle: SR" if src == "SUBFOLDER" else "Quelle: Basis"
                    write(f"   🔌 AOP-Start: {ds['aop']} ✅ ({where})")
                else:
                    write(f"   🔌 AOP-Start: {ds['aop']} ❌ fehlt")
                    errors["AOP fehlt"].append(f"Strecke {nr}")

            # ABP-Start
            ok, src = file_exists(base_folder, SK_FOLDER, ds["abp_start"])
            if ok:
                where = "Quelle: SK" if src == "SUBFOLDER" else "Quelle: Basis"
                write(f"   ▶️  ABP-Start: {ds['abp_start']} ✅ ({where})")
            else:
                write(f"   ▶️  ABP-Start: {ds['abp_start']} ❌ fehlt")
                errors["ABP-Start fehlt"].append(f"Strecke {nr}")

            # ABP-Ziel
            ok, src = file_exists(base_folder, SK_FOLDER, ds["abp_ziel"])
            if ok:
                where = "Quelle: SK" if src == "SUBFOLDER" else "Quelle: Basis"
                write(f"   🎯 ABP-Ziel: {ds['abp_ziel']} ✅ ({where})")
            else:
                write(f"   🎯 ABP-Ziel: {ds['abp_ziel']} ❌ fehlt")
                errors["ABP-Ziel fehlt"].append(f"Strecke {nr}")

        # Zusammenfassung
        write("\n" + "=" * 60)
        write("📊 Zusammenfassung")
        if not errors:
            write("✅ Alle Prüfungen bestanden, keine Fehler gefunden.")
        else:
            for typ, strecken in errors.items():
                write(f"❌ {typ}: {len(strecken)} Fehler")
                write("   Betroffen: " + ", ".join(strecken))

        write("\n=== Prüfung abgeschlossen ===")

    return errors


def strecken_copy(base_folder: str) -> None:
    """
    Kopiert alle vorhandenen Quelle-PDFs (Unterordner oder Basis) in die Zielordner
    unter 'Strecke/Strecke {nr}', inkl. 'Strecke {nr}.pdf' (Quelle: Basis oder Strecke-Root).
    Schreibt ein Logfile 'StreckenCopy.txt' ins Basisverzeichnis.
    """
    logfile = os.path.join(base_folder, "StreckenCopy.txt")
    with open(logfile, "w", encoding="utf-8") as log:
        def write(line: str = ""):
            log.write(line + "\n")

        write("📂 StreckenCopy gestartet (mit Fallback in den Basisordner)")
        write("Zeit: " + time.strftime("%Y-%m-%d %H:%M:%S"))
        write("=" * 60)

        for ds in strecken_daten:
            nr = ds["nr"]
            strecke_folder = ensure_strecke_folder(base_folder, nr)
            write(f"\n➡️ Strecke {nr} → Ziel: {os.path.relpath(strecke_folder, base_folder)}")

            # 'Strecke {nr}.pdf' zuerst handhaben
            src_pdf, src_label = find_strecke_pdf_source(base_folder, nr)
            if src_pdf:
                dest_pdf = strecke_pdf_dest_path(base_folder, nr)
                os.makedirs(os.path.dirname(dest_pdf), exist_ok=True)
                shutil.copy2(src_pdf, dest_pdf)
                write(f"   📄 Strecke-PDF: {os.path.basename(dest_pdf)} ✅ kopiert ({src_label})")
            else:
                write(f"   📄 Strecke-PDF: {strecke_pdf_name(nr)} ❌ fehlt")

            # Funktion-FOP
            ok, src = copy_pdf(base_folder, FOP_FOLDER, ds["fop"], strecke_folder)
            where = {"SUBFOLDER": "FOP", "BASIS": "Basis"}.get(src, "—")
            write(f"   📑 FOP: {ds['fop']} {'✅ kopiert' if ok else '❌ fehlt'}{(' (' + where + ')') if ok else ''}")

            # AOP (falls vorhanden)
            if ds["aop"] != "NULL":
                ok, src = copy_pdf(base_folder, SR_FOLDER, ds["aop"], strecke_folder)
                where = {"SUBFOLDER": "SR", "BASIS": "Basis"}.get(src, "—")
                write(f"   🔌 AOP: {ds['aop']} {'✅ kopiert' if ok else '❌ fehlt'}{(' (' + where + ')') if ok else ''}")

            # ABP-Start
            ok, src = copy_pdf(base_folder, SK_FOLDER, ds["abp_start"], strecke_folder)
            where = {"SUBFOLDER": "SK", "BASIS": "Basis"}.get(src, "—")
            write(f"   ▶️ ABP-Start: {ds['abp_start']} {'✅ kopiert' if ok else '❌ fehlt'}{(' (' + where + ')') if ok else ''}")

            # ABP-Ziel
            ok, src = copy_pdf(base_folder, SK_FOLDER, ds["abp_ziel"], strecke_folder)
            where = {"SUBFOLDER": "SK", "BASIS": "Basis"}.get(src, "—")
            write(f"   🎯 ABP-Ziel: {ds['abp_ziel']} {'✅ kopiert' if ok else '❌ fehlt'}{(' (' + where + ')') if ok else ''}")

        write("\n=== Kopiervorgang abgeschlossen ===")


# =========================
#   CLI
# =========================

def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="SCopy – Prüfen und/oder Kopieren von Strecken-PDFs (mit Fallback-Suche im Basisordner & Strecke-{nr}.pdf).",
        epilog="Beispiele:\n"
               "  python SCopy.py --check\n"
               "  python SCopy.py --copy\n"
               "  python SCopy.py               (erst Check, dann Nachfrage)\n"
               "  python SCopy.py --base C:\\\\Pfad\\\\zum\\\\Projekt --copy",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--check", action="store_true", help="Nur prüfen")
    parser.add_argument("--copy",  action="store_true", help="Nur kopieren")
    parser.add_argument("--base",  type=str, default=os.getcwd(), help="Basispfad (Default: aktuelles Verzeichnis)")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    base = os.path.abspath(args.base)
    print(f"🏁 Basisordner: {base}")
    print(f"📁 Erwartete Quellordner: {FOP_FOLDER}/, {SR_FOLDER}/, {SK_FOLDER}/  (Fallback: Basis)")
    print(f"📦 Zielbasis: {ST_FOLDER}/Strecke {{nr}}/")
    print("=" * 60)

    if args.check and args.copy:
        # Reihenfolge: erst prüfen, dann kopieren
        print("🔎 Starte CHECK ...")
        errors = strecken_check(base)
        print("✅ Check abgeschlossen – Log: StreckenCheck.txt")
        print()
        print("📥 Starte COPY ...")
        strecken_copy(base)
        print("✅ Kopieren abgeschlossen – Log: StreckenCopy.txt")
        return 0

    if args.check:
        print("🔎 Starte CHECK ...")
        errors = strecken_check(base)
        print("✅ Check abgeschlossen – Log: StreckenCheck.txt")
        if errors:
            print("⚠️  Es wurden Probleme gefunden. Details in StreckenCheck.txt.")
        else:
            print("🎉 Keine Probleme gefunden.")
        return 0

    if args.copy:
        print("📥 Starte COPY ...")
        strecken_copy(base)
        print("✅ Kopieren abgeschlossen – Log: StreckenCopy.txt")
        return 0

    # Kein Flag → interaktiver Modus: erst check, dann Nachfrage
    print("🔎 Starte CHECK ...")
    errors = strecken_check(base)
    print("✅ Check abgeschlossen – Log: StreckenCheck.txt")
    if errors:
        print("⚠️  Es wurden Probleme gefunden. Details in StreckenCheck.txt.")
    else:
        print("🎉 Keine Probleme gefunden.")

    try:
        answer = input("👉 Jetzt kopieren? (J/N): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\n⏹️  Abgebrochen.")
        return 1

    if answer in ("j", "y", "ja", "yes"):
        print("📥 Starte COPY ...")
        strecken_copy(base)
        print("✅ Kopieren abgeschlossen – Log: StreckenCopy.txt")
        return 0
    else:
        print("⏹️  Keine Kopie durchgeführt.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
