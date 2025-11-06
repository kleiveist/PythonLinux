---
Cover: '[[PyReport-01.png]]'
Section: MyHub
Rank: Python
Projekt: PythonLinux
Task: bin
tags:
- PyReport
- MyHub
- Python
- PythonLinux
- bin
link1: '[[PyReport]]'
---

Installation:
- Öffne terminal im Verzeichnis in der sich auch folderlist befindet.
- Global installieren:
```bash
sudo install -m 0755 folderlist /usr/local/bin/folderlist
```
---
Beispiele (einheitlich mit `--help`):
- `folderlist --3` → Tiefe 3
- `folderlist --noic 3` oder `folderlist 3 --noic` → Icons aus, Tiefe 3
- `folderlist --no-files --4` → nur Ordner, Tiefe 4
- `folderlist --multi --3` → erzeugt `1..3-FolderList.txt`
- Natürlich gehen weiterhin `folderlist 3` und `folderlist noic 3`.

---
---
Installation:
- Öffne terminal im Verzeichnis in der sich auch summary befindet.
- Global installieren:
```bash
sudo install -m 0755 summary /usr/local/bin/summary
```
---
