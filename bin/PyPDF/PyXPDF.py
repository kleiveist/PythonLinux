#!/usr/bin/env python3
import os
import glob
from PyPDF2 import PdfReader, PdfWriter

# ----------------------------
# SETTINGS
START_NUM = 10   # Ab welcher Zahl soll gezählt werden?
# ----------------------------

def extract_pdf_pages():
    # Aktueller Arbeitsordner
    folder = os.getcwd()
    
    # Alle PDF-Dateien im aktuellen Ordner ermitteln und sortieren
    pdf_files = sorted(glob.glob(os.path.join(folder, "*.pdf")))
    
    if not pdf_files:
        print("Keine PDF-Dateien im aktuellen Ordner gefunden.")
        return

    for pdf_file in pdf_files:
        print(f"Bearbeite: {pdf_file}")
        
        # PDF-Reader erstellen
        reader = PdfReader(pdf_file)
        
        # Basis-Namen für die Ausgabedateien erstellen
        base_name = os.path.splitext(os.path.basename(pdf_file))[0]
        
        # Ordner für extrahierte Seiten erstellen (ohne 'pages'-Suffix)
        output_folder = os.path.join(folder, base_name)
        os.makedirs(output_folder, exist_ok=True)
        
        # Jede Seite als separate PDF speichern
        for i, page in enumerate(reader.pages, start=START_NUM):
            writer = PdfWriter()
            writer.add_page(page)
            
            # Neuer Dateiname im gewünschten Format
            output_file = os.path.join(output_folder, f"{i}.{base_name}.pdf")
            
            # Einzelne Seite als PDF speichern
            with open(output_file, 'wb') as output_pdf:
                writer.write(output_pdf)
            
            print(f"  Seite {i} extrahiert: {output_file}")
        
        print(f"PDF '{pdf_file}' wurde in {len(reader.pages)} Einzelseiten aufgeteilt.")
        print(f"Ausgabeordner: {output_folder}")
        print()

if __name__ == '__main__':
    extract_pdf_pages()
