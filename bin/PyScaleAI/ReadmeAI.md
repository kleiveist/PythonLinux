# README – Install-AI & venvAI.txt

Diese Datei beschreibt die **AI-Erweiterung** zu deiner bestehenden PuPy-Installation.

Ziel:  
- `install.py` (= **Install-PuPy**) kümmert sich **nur** um:
  - Kopieren der `.py`-Skripte ins Ziel
  - Anlegen der `.venv`
  - Installation der **Basis-Pakete** aus `venv.txt`
  - Erzeugen der Wrapper in `/usr/local/bin`
- `InstallAI.py` (= **Install-AI**) kümmert sich **nur** um:
  - zusätzliche **AI-Pakete** in einer bestehenden `.venv`
  - Download und Ablage der **Modelldateien**
  - gesteuert über **`venvAI.txt`** pro Projekt

So bleiben Basis-Installation und AI-spezifische Erweiterung sauber getrennt.

---

## 1. Dateien im Überblick

Im Repo / Projekt gibt es (mindestens) die folgenden Dateien:

- `install.py`  
  Globale Installer-Logik (PuPy).  
  Sucht alle `.py` und `venv.txt` im Quellbaum und installiert sie nach `DEST_BASE`  
  (Standard: `~/Dokumente/Python`).

- `venv.txt`  
  Basis-Abhängigkeiten, die für alle Skripte deiner Sammlung gelten sollen  
  (Standard-Python-Pakete, keine AI-Spezialfälle).

- `InstallAI.py`  
  AI-spezifischer Installer.  
  Wird **im Zielordner** ausgeführt (dort, wo auch dein AI-Skript liegt) und erweitert
  die dortige `.venv` um AI-Pakete und Modelle gemäß `venvAI.txt`.

- `venvAI.txt`  
  AI-spezifische Konfigurationsdatei pro Projekt.  
  Enthält:
  - Pip-Pakete (`pkg ...`)
  - Modelldateien (`model ...`)

- `PyImg4x.py` (Beispiel)  
  AI-Skript, das z.B. Real-ESRGAN verwendet und ein Modell unter  
  `weights/RealESRGAN_x4plus.pth` erwartet.

---

## 2. Gesamtablauf – Zusammenspiel der Teile

### 2.1 PuPy-Installation (Basis)

1. **Im Repo-Root** aufrufen:

   ```bash
   cd /pfad/zum/repo
   ./install.py          # oder: python3 install.py
