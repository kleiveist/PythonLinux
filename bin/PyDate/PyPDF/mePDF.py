#!/usr/bin/env python3
import os
import glob
from PyPDF2 import PdfMerger

def merge_pdfs_in_current_folder():
    # Aktueller Arbeitsordner
    folder = os.getcwd()
    
    # Alle PDF-Dateien im aktuellen Ordner ermitteln und sortieren
    pdf_files = sorted(glob.glob(os.path.join(folder, "*.pdf")))
    
    if not pdf_files:
        print("Keine PDF-Dateien im aktuellen Ordner gefunden.")
        return

    merger = PdfMerger()

    # Jede PDF zur Merger-Instanz hinzufügen
    for pdf in pdf_files:
        print(f"Füge hinzu: {pdf}")
        merger.append(pdf)

    # Name der zusammengeführten PDF
    output_pdf = os.path.join(folder, "zusammengefuehrte_PDF.pdf")
    
    # Zusammengeführte PDF speichern
    merger.write(output_pdf)
    merger.close()
    print(f"Die zusammengeführte PDF wurde erstellt: {output_pdf}")

if __name__ == '__main__':
    merge_pdfs_in_current_folder()
