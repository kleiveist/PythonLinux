---
Cover: '[[README-01.png]]'
Section: Blobbite
Rank: Python
Projekt: PythonLinux
Task: workspace
tags:
- README
- Blobbite
- Python
- PythonLinux
- workspace
link1: '[[README]]'
---

# PythonLinux – Installer & Workspace

Ein leichtgewichtiger Installer, der Python‑Module aus diesem Repository lokal spiegelt, je Modul eine eigene venv anlegt und ausführbare Wrapper bereitstellt. Du kannst das Repo an jeden Ort klonen – der Installer arbeitet immer relativ zu deinem aktuellen Projektordner.

---

## 🔎 Schnellnavigation

| 🚀 | Thema | Kurzbeschreibung |
|---|---|---|
| 🔧 | [Installation](#installation) | Repo klonen, Zeilenenden prüfen, install.sh starten |
| 🎯 | [Zweck der install.sh](#zweck-der-installsh) | Was die .sh macht und warum sie existiert |
| ➕ | [Eigene Python‑Skripte integrieren](#eigene-python-skripte-integrieren) | Ordnerstruktur, Einstiegsskript, Wrapper, venv.txt |
| 📦 | [venv & Abhängigkeiten](#venv--abhängigkeiten) | pyyaml statt yaml, Version-Pins, Neuaufbau |
| 🩹 | [Häufige Fehler & Fixes](#häufige-fehler--fixes) | CRLF „bash\r“, pip „yaml“, PATH, Rechte |
| ✅ | [Verifizieren & Update](#verifizieren--update) | Funktion prüfen, später erneut installieren |
| 🗑️ | [Deinstallation](#deinstallation) | Module und Wrapper entfernen |
| 📄 | [Lizenz](#lizenz) | Lizenzhinweis |

---

## 🔧 Installation

# O) System vorberiten 

```bash
apt update
apt install curl unzip -y
apt install -y python3-venv


curl --version
```

```bash
cd /opt

# ZIP vom GitHub-Repo laden
curl -L -o PythonLinux.zip \
  https://github.com/kleiveist/PythonLinux/archive/refs/heads/main.zip

# entpacken
unzip PythonLinux.zip

# entstehender Ordner heißt meist PythonLinux-main → umbenennen:
mv PythonLinux-main PythonLinux

./install.sh
```

```bash
cd /opt/PythonLinux
ls
python3 install.py
```

Voraussetzungen:
- Linux oder macOS (Windows via WSL möglich)
- Python 3.9+ mit pip und venv
- bash
- Schreibrechte für:
  - Zielbasis: Standard $HOME/Dokumente/Python
  - Wrapper-Verzeichnis: Standard /usr/local/bin (ggf. sudo nötig)
---

## 🎯 Zweck der install.sh

Die install.sh ist ein idempotenter Projekt‑Installer. Sie sorgt dafür, dass deine Skripte jederzeit konsistent und lauffähig sind – unabhängig davon, wo das Repo liegt.

Was genau passiert:
1) Modul‑Suche: durchsucht den Startordner (Standard: aktuelles Verzeichnis) unterhalb von z. B. bin/ und game/.  
2) Spiegeln: kopiert die .py‑Dateien modular nach DEST_BASE, inkl. originaler Ordnerstruktur.  
3) Isolierte Umgebungen: erzeugt je Modul eine eigene Python‑venv (.venv).  
4) Abhängigkeiten: installiert Pakete aus venv.txt (falls vorhanden).  
5) Wrapper: erstellt ausführbare Starter im WRAPPER_DIR, sodass du Module als Kommandos starten kannst (z. B. PyObis).  
6) Wiederholbar: Ein erneuter Lauf aktualisiert Dateien und Pakete, ohne dass du Pfade anpassen musst.

Konfigurierbar via Umgebungsvariablen:
- START_DIR (Default: $PWD)  
- DEST_BASE (Default: $HOME/Dokumente/Python)  
- WRAPPER_DIR (Default: /usr/local/bin)

---

## ➕ Eigene Python‑Skripte integrieren

So bringst du dein eigenes Tool in den Installer‑Flow:

1) Ordner anlegen  
   - Lege dein Modul unterhalb von bin/ oder game/ ab.  
   - Beispiel: bin/MyTool/

2) Einstiegsskript festlegen (Konvention)  
   - Benenne dein Einstiegsskript wie den Ordner: MyTool.py  
   - Alternativ: definiere genau EIN Hauptskript im Modulordner.

3) Abhängigkeiten deklarieren (optional)  
   - Erstelle eine venv.txt in bin/MyTool/.  
   - Ein Eintrag pro Zeile, z. B.:
     ```
     pyyaml
     rich>=13
     ```

4) Installer ausführen  
   ```bash
   ./install.sh
   ```
   - Der Installer erzeugt eine venv unter: DEST_BASE/bin/MyTool/.venv  
   - Er erstellt einen Wrapper: MyTool (im WRAPPER_DIR)

5) Starten  
   ```bash
   MyTool --help
   ```
   oder direkt in der venv:
   ```bash
   source "$HOME/Dokumente/Python/bin/MyTool/.venv/bin/activate"
   python MyTool.py
   deactivate
   ```

Tipps:
- CLI‑Parsing (argparse/typer) ins Einstiegsskript legen.  
- Für zusätzliche Daten/Assets: innerhalb des Modulordners ablegen; der Installer spiegelt sie mit.  
- Wenn du den Wrapper‑Namen explizit steuern willst, halte dich an die Ordner‑=‑Skript‑Namenskonvention (MyTool/ → MyTool.py → Wrapper MyTool).

---

## 📦 venv & Abhängigkeiten

- Pro Modul eigene venv (.venv) → isolierte, konfliktfreie Abhängigkeiten.  
- venv.txt steuert die Installation beim ersten Lauf und bei Updates:
  - Paketnamen so, wie sie bei pip heißen (z. B. pyyaml statt yaml).  
  - Optional Versionen pinnen: requests==2.32.3 oder Bereiche: rich>=13,<14.  
- Neuaufbau erzwingen:
  ```bash
  # venv löschen und sauber neu aufbauen
  rm -rf "$HOME/Dokumente/Python/bin/MyTool/.venv"
  ./install.sh
  ```
- Systempakete (apt/dnf/pacman) nur verwenden, wenn Bibliotheken auf OS‑Ebene nötig sind (z. B. Tk/GUI, ImageMagick). Bevorzugt in der venv mit pip arbeiten.

---

## 🩹 Häufige Fehler & Fixes

1) CRLF‑Zeilenenden in install.sh  
   Symptom:
   ```
   ./install.sh
   env: »bash\r«: Datei oder Verzeichnis nicht gefunden
   env: Verwenden Sie -[v]S, um Optionen in #!-Zeichen zu übergeben
   ```
   Ursache: Datei hat Windows‑Zeilenenden (CRLF).  
   Fix:
   - In VS Code unten rechts „CRLF“ → „LF“ wählen, speichern.  
   - Oder im Terminal:
     ```bash
     sed -i 's/\r$//' install.sh
     # optional:
     # dos2unix install.sh
     ```
   Empfehlung fürs Repo:
   ```
   # .gitattributes
   *.sh text eol=lf
   ```

2) pip findet „yaml“ nicht  
   Symptom:
   ```
   ERROR: Could not find a version that satisfies the requirement yaml
   ```
   Ursache: Das Paket heißt auf PyPI „PyYAML“ (pip‑Name: pyyaml), nicht „yaml“.  
   Fix:
   ```bash
   sed -i 's/^\s*yaml\s*$/pyyaml/I' bin/PyObis/venv.txt
   ./install.sh
   ```
   Test:
   ```bash
   "$HOME/Dokumente/Python/bin/PyObis/.venv/bin/python" -c \
     "import yaml,sys; print('PyYAML', yaml.__version__); print(sys.executable)"
   ```

3) Wrapper nicht im PATH / fehlende Rechte  
   - Prüfen:
     ```bash
     command -v MyTool
     ```
   - Lösung: Benutzerpfad verwenden und in PATH aufnehmen:
     ```bash
     DEST_BASE="$HOME/Apps/Python" WRAPPER_DIR="$HOME/.local/bin" ./install.sh
     echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
     source ~/.bashrc
     ```

4) INI/Root wird nicht gefunden (z. B. ObisDatabase)  
   - Lege die INI in den Arbeits‑Root (z. B. /run/media/…/workspace/ObisDatabase.ini).  
   - Starte im Root oder gib ihn an:
     ```bash
     ObisDatabase --root /run/media/kleif/9CB3-A9F8/workspace
     ```

---

## ✅ Verifizieren & Update

- Wrapper vorhanden?
  ```bash
  command -v PyObis
  command -v ObisDatabase
  ```
- Module am Ziel?
  ```bash
  ls -la "$HOME/Dokumente/Python/bin/PyObis"
  ```
- Starttest:
  ```bash
  PyObis --help
  ```

Später aktualisieren:
```bash
git pull
./install.sh
```
Der Installer ist wiederholbar: Neue/aktualisierte Dateien werden übernommen, venv‑Pakete aus venv.txt werden nachinstalliert/aktualisiert.

---

## 🗑️ Deinstallation

- Modulordner entfernen:
```bash
rm -rf "$HOME/Dokumente/Python/bin/PyObis"
```
- Wrapper löschen:
```bash
sudo rm -f /usr/local/bin/PyObis
# oder (bei Benutzerpfad)
rm -f "$HOME/.local/bin/PyObis"
```

---

## 📄 Lizenz



---
