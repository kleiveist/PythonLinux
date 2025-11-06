---
Cover: '[[Wrapper-01.png]]'
Section: MyHub
Rank: Python
Projekt: PythonLinux
Task: bin
tags:
- Wrapper
- MyHub
- Python
- PythonLinux
- bin
link1: '[[Wrapper]]'
---

### 2. Wrapper-Skripte
---
```bash
cd /usr/local/bin
```

```bash
sudo nano /usr/local/bin/renameEB
```

```bash
#!/bin/bash
PROJECT_DIR="/home/kleif/Dokumente/Pytohn/P24PyPDF"
VENV_DIR="$PROJECT_DIR/vmve"
source "$VENV_DIR/bin/activate"
python "$PROJECT_DIR/renameEB.py" "$@"
```

```bash
sudo chmod +x /usr/local/bin/renameEB
```

---



