import os
import time
from PyPDF2 import PdfMerger

# --- Datensätze ---
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

def merge_pdfs(base_folder):
    logfile = os.path.join(base_folder, "StreckenMerge.txt")
    with open(logfile, "w", encoding="utf-8") as log:
        def write(line=""):
            log.write(line + "\n")

        write("📑 StreckenMerge gestartet")
        write("Zeit: " + time.strftime("%Y-%m-%d %H:%M:%S"))
        write("="*60)

        for ds in strecken_daten:
            nr = ds["nr"]
            strecke_folder = os.path.join(base_folder, f"Strecke {nr}")
            merged_file = os.path.join(strecke_folder, f"Strecke_{nr}_Merged.pdf")
            merger = PdfMerger()
            files_added = []

            # Merge in fester Reihenfolge
            candidates = [
                os.path.join(strecke_folder, f"Strecke {nr}.pdf"),
                os.path.join(strecke_folder, ds["aop"] + ".pdf") if ds["aop"] != "NULL" else None,
                os.path.join(strecke_folder, ds["abp_start"] + ".pdf"),
                os.path.join(strecke_folder, ds["fop"] + ".pdf"),
                os.path.join(strecke_folder, ds["abp_ziel"] + ".pdf"),
            ]

            for f in candidates:
                if f and os.path.isfile(f):
                    merger.append(f)
                    files_added.append(os.path.basename(f))

            if files_added:
                merger.write(merged_file)
                merger.close()
                write(f"➡️ Strecke {nr}: Merged {len(files_added)} Dateien → {os.path.basename(merged_file)}")
            else:
                write(f"➡️ Strecke {nr}: ❌ Keine Dateien gefunden, nichts gemerged")

        write("\n=== Merge abgeschlossen ===")

if __name__ == "__main__":
    import os, time
    from PyPDF2 import PdfMerger

    base = os.getcwd()
    merge_pdfs(base)
