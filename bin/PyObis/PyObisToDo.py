import shutil
from pathlib import Path

import yaml  # pip install pyyaml

# Basisordner ist der Ordner, in dem du das Skript im Terminal startest
BASE_DIR = Path.cwd()

# Erlaubte Status-Werte (für Stratus)
ALLOWED_STATUS = {
    "Canceled",
    "Changes",
    "Done",
    "Onhold",
    "Open",
    "Progress",
    "Status",
}


def extract_yaml_front_matter(text: str):
    """
    Extrahiert YAML-Frontmatter zwischen den ersten beiden '---'-Zeilen.
    Gibt (yaml_dict, rest_des_textes) zurück oder (None, text), wenn kein YAML gefunden wurde.
    """
    lines = text.splitlines(keepends=True)
    if not lines:
        return None, text

    if lines[0].strip() != "---":
        return None, text

    yaml_end_index = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            yaml_end_index = i
            break

    if yaml_end_index is None:
        # Kein abschließendes '---' gefunden
        return None, text

    yaml_text = "".join(lines[1:yaml_end_index])
    rest_text = "".join(lines[yaml_end_index + 1 :])

    try:
        data = yaml.safe_load(yaml_text) or {}
    except yaml.YAMLError:
        return None, text

    if not isinstance(data, dict):
        return None, text

    return data, rest_text


def build_target_folder(rank: str, projekt: str, task: str, status: str) -> Path:
    """
    Baut einen verschachtelten Pfad:
    BASE_DIR / Rank / Projekt / Task / Status
    z.B. ./HEIWest/P25Strecken/ToDoList/Open
    """
    rank = (rank or "UnknownRank").strip()
    projekt = (projekt or "UnknownProjekt").strip()
    task = (task or "UnknownTask").strip()
    status = (status or "Status").strip()

    return BASE_DIR / rank / projekt / task / status


def move_file_to_folder(file_path: Path, target_folder: Path):
    target_folder.mkdir(parents=True, exist_ok=True)
    target_path = target_folder / file_path.name

    # Wenn Datei schon mit gleichem Namen existiert, hänge eine Zahl an
    if target_path.exists():
        stem = file_path.stem
        suffix = file_path.suffix
        counter = 1
        while True:
            candidate = target_folder / f"{stem}_{counter}{suffix}"
            if not candidate.exists():
                target_path = candidate
                break
            counter += 1

    shutil.move(str(file_path), str(target_path))
    print(f"Verschoben: {file_path} -> {target_path}")


def main():
    md_files = list(BASE_DIR.rglob("*.md"))
    print(f"Gefundene .md-Dateien insgesamt: {len(md_files)}")

    for md_file in md_files:
        if not md_file.is_file():
            continue

        try:
            text = md_file.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            print(f"Übersprungen (Encoding-Fehler): {md_file}")
            continue

        yaml_data, _ = extract_yaml_front_matter(text)

        if yaml_data is None:
            # keine/kaputte YAML-Frontmatter
            continue

        # Nur Dateien mit Task: ToDoList
        task = str(yaml_data.get("Task", "")).strip()
        if task != "ToDoList":
            continue

        rank = yaml_data.get("Rank")
        projekt = yaml_data.get("Projekt")
        status = yaml_data.get("Stratus")

        if status is None:
            status = "Status"
        else:
            status = str(status).strip()
            if status not in ALLOWED_STATUS:
                print(f"Warnung: Unbekannter Stratus '{status}' in {md_file}, setze auf 'Status'")
                status = "Status"

        target_folder = build_target_folder(rank, projekt, task, status)

        # Wenn die Datei bereits im richtigen Zielordner liegt: nichts tun
        if md_file.parent == target_folder:
            print(f"Bereits korrekt einsortiert: {md_file}")
            continue

        move_file_to_folder(md_file, target_folder)

    print("Fertig.")


if __name__ == "__main__":
    main()
