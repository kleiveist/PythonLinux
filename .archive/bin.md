---
Cover: '[[bin-01.png]]'
Section: MyHub
Rank: Python
Projekt: PythonLinux
Task: bin
tags:
- bin
- MyHub
- Python
- PythonLinux
- bin
link1: '[[bin]]'
---

---


### 1. Virtuelle Umgebung erstellen
```bash
python3 -m venv vmve 
```
---
### 2. Virtuelle Umgebung Starten
```bash
source vmve/bin/activate.fish
```
---
### 2. Abhängigkeiten installieren
`pymupdf4llm` basiert auf **PyMuPDF**. Installation über `pip`:
```bash
pip install pymupdf4llm
pip install PyPDF2
pip install PyMuPDF
```
Optionale Ergänzungen (falls du PDFs verarbeiten oder exportieren willst):
```bash
pip install rich tqdm
```
---
---

### 2. Wrapper-Skripte in `/usr/local/bin`

Du kopierst deine eigentlichen Python-Skripte **nicht** nach `/usr/local/bin/`.  
Stattdessen legst du dort kleine **Starter-Skripte** ab, die die VMVE aktivieren und dein Skript starten.

- Beispiel: `/usr/local/bin/pdf2md`
```bash
cd /usr/local/bin
sudo nano pdf2md
```

```bash
#!/bin/bash
PROJECT_DIR="/home/kleif/Dokumente/Pytohn/P24PyPDF"
VENV_DIR="$PROJECT_DIR/vmve"
"$VENV_DIR/bin/python" "$PROJECT_DIR/pdf2md.py" "$@"
```
- `"$@"` sorgt dafür, dass alle übergebenen Argumente weitergereicht werden.
- Setze die Rechte:
```bash
sudo chmod +x /usr/local/bin/pdf2md
```
Jetzt kannst du global starten:
```bash
pdf2md beispiel.pdf
```
---
### 3. Alle Skripte verfügbar machen
Analog für `exPDF.py`, `mePDF.py`, `folder-list.py`:
```bash
sudo nano /usr/local/bin/expdf 
```

```bash
#!/bin/bash
PROJECT_DIR="/home/kleif/Dokumente/Pytohn/P24PyPDF"
VENV_DIR="$PROJECT_DIR/vmve"
source "$VENV_DIR/bin/activate"
python "$PROJECT_DIR/exPDF.py" "$@"
```

```bash
sudo chmod +x /usr/local/bin/expdf
```

---

```bash
sudo nano /usr/local/bin/mepdf 
```

```bash
#!/bin/bash
PROJECT_DIR="/home/kleif/Dokumente/Pytohn/P24PyPDF"
VENV_DIR="$PROJECT_DIR/vmve"
source "$VENV_DIR/bin/activate"
python "$PROJECT_DIR/mePDF.py" "$@"
```

```bash
sudo chmod +x /usr/local/bin/mepdf
```







---
<!-- AUTOGEN_START -->

---
#Folder
[[PyDate]]
[[PyReport]]

---
#Markdown
![[PyReport.md]]
<!-- AUTOGEN_END -->
\n
