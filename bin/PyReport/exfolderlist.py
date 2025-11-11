import os

# Funktion zum Parsen der Ordnerstruktur aus den Zeilen
def parse_structure(lines):
    structure = []
    stack = []

    for line in lines:
        # Tiefe anhand der Baumzeichen bestimmen
        depth = line.count('│') + line.count('├') + line.count('└')
        folder_name = line.split('📁')[-1].strip()

        # Stack entsprechend der Tiefe anpassen
        stack = stack[:depth]
        stack.append(folder_name)

        # Vollständigen Pfad erstellen
        full_path = os.path.join(*stack)
        structure.append(full_path)

    return structure

# Basisverzeichnis definieren
base_dir = "folder_list"

# Alle passenden Dateien einlesen
all_lines = []
for i in range(10):
    filename = f"{i}-FolderList.txt" if i > 0 else "FolderList.txt"
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            all_lines.extend(f.readlines())

# Struktur analysieren
folder_paths = parse_structure(all_lines)

# Ordner erstellen
for path in folder_paths:
    full_path = os.path.join(base_dir, path)
    os.makedirs(full_path, exist_ok=True)

print(f"Es wurden {len(folder_paths)} Ordnerpfade unter '{base_dir}' erfolgreich erstellt.")
