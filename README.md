---
Cover: '[[inst-01.png]]'
Section: MyHub
Rank: Python
Projekt: PythonLinux
Task: inst
tags:
- inst
- MyHub
- Python
- PythonLinux
- inst
link1: '[[inst]]'
---

### 📘 Dokumentation: Installer/Updater für „PythonLinux“ (install.sh)

Diese Anleitung erklärt Zweck, Funktionsweise, Voraussetzungen, Installation, Aktualisierung, Konfiguration, Fehlerbehebung und Deinstallation des bereitgestellten Bash-Skripts. Sie richtet sich an Admins und Entwickler, die das Repository „PythonLinux“ systemweit bereitstellen möchten.

---

### 🔎 Überblick (TL;DR)

- Klont/aktualisiert ein Git-Repository nach /opt/PythonLinux (Standard).
- Legt nur dort virtuelle Umgebungen (.venv) an, wo venv.txt existiert.
- Erzeugt ausführbare Wrapper in /usr/local/bin für alle Python-Skripte unter bin/** und game/**.
- Wrapper wählen zur Laufzeit automatisch die nächste .venv (vom Skriptordner aus aufwärts, bis zum Repo-Root), sonst System-Python.
- Emoji-Ausgaben sorgen für klare, gut sichtbare Statusmeldungen.

---

### 🧩 Unterstützte Systeme und Voraussetzungen

- Betriebssystem: Debian/Ubuntu und Derivate (verwendet apt-get).
- Root-Rechte: Erforderlich (sudo), da in /opt und /usr/local/bin geschrieben wird.
- Internetzugang: Für Git und Paketinstallation (pip).
- Das Skript installiert bei Bedarf die Systempakete: git, python3, python3-venv, python3-pip, findutils.

Hinweis für andere Distributionen (RHEL/Fedora/SUSE): Das Skript nutzt apt-get. Für diese Systeme müssten die Paketinstallationsbefehle in der Funktion apt_install_deps angepasst werden.

---

### 🧠 Was das Skript genau macht (Ablauf)

1. Root prüfen
    
    - Abbruch, falls kein Root (Bitte als root ausführen …).
2. Systemabhängigkeiten installieren
    
    - apt-get update
    - Installation: git, python3, python3-venv, python3-pip, findutils
3. Repository klonen oder aktualisieren
    
    - Ziel: /opt/PythonLinux (Standard)
    - Falls bereits vorhanden: git fetch --all --prune, dann pull --ff-only (oder Reset auf Remote-Default-Branch)
4. Repo-Root markieren
    
    - Leere Datei .repo-root im Projektverzeichnis. Dient als Stopmarker für die spätere .venv-Suche.
5. Spezifische Erstkonfiguration für PyPDF
    
    - Falls Verzeichnis bin/PyDate/PyPDF existiert und keine venv.txt vorhanden ist: venv.txt mit Packages (pymupdf4llm, PyPDF2, rich, tqdm) anlegen.
6. Virtuelle Umgebungen anlegen/aktualisieren
    
    - Durchsucht Ordner mit .py-Dateien unter bin/** und game/**.
    - Nur wenn in einem Ordner eine venv.txt liegt, wird dort <dir>/.venv erstellt/aktualisiert und Pakete gemäß venv.txt installiert (Kommentare/Leerzeilen erlaubt).
7. Dateirechte setzen
    
    - *.py → 0644 (lesen/schreiben für Eigentümer, lesen für andere)
    - *.sh → 0755 (ausführbar)
8. Wrapper erzeugen
    
    - Für alle _.py unter bin/_* und game/** wird ein Wrapper unter /usr/local/bin erzeugt (Standardpräfix: pl-).
    - Optional: Python-Syntaxprüfung (VERIFY=1). Bei Fehlern wird gewarnt, der Wrapper dennoch erstellt.
9. Abschlussausgabe
    
    - Zusammenfassung der Pfade und Hinweise.

---

### 🧱 Verzeichnis- und Wrapper-Konzept

- Projektverzeichnis (Standard): /opt/PythonLinux
- Markerdatei: /opt/PythonLinux/.repo-root
- Skriptquellen: /opt/PythonLinux/bin/** und /opt/PythonLinux/game/**
- Wrapper: /usr/local/bin/pl-<name>

Wrapper-Auflösung zur Laufzeit:

- Startet im Ordner des Zielskripts, sucht aufwärts die nächste .venv/bin/python.
- Stoppt am Repo-Root (.repo-root) oder Dateisystemwurzel.
- Fällt zurück auf System-Python (/usr/bin/python3 standardmäßig), wenn keine .venv gefunden wird.

Beispielstruktur:

```
/opt/PythonLinux
├─ .repo-root
├─ bin/
│  ├─ tools/
│  │  ├─ venv.txt        # Pakete → erzeugt /opt/PythonLinux/bin/tools/.venv
│  │  └─ foo.py          # Wrapper: /usr/local/bin/pl-foo
│  └─ bar.py             # Keine venv.txt im Ordner → nutzt System-Python
└─ game/
   └─ play.py            # Wrapper: /usr/local/bin/pl-play
```

Namenskonflikte:

- Standardname: pl-<skriptbasisname> (ohne .py)
- Bei Kollision (z. B. bin/foo.py und game/foo.py):
    - Erstes Skript → pl-foo
    - Zweites Skript → pl-bin-foo oder pl-game-foo (Pfad-Anteile werden mit - verbunden, „_“ und Leerzeichen → „-“)

---

### ⚙️ Konfiguration per Umgebungsvariablen

Du kannst das Verhalten ohne Skriptänderungen steuern, indem du Variablen beim Aufruf setzt:

|Variable|Bedeutung|Standardwert|
|---|---|---|
|REPO_URL|Git-URL des Projekts|[https://github.com/kleiveist/PythonLinux.git](https://github.com/kleiveist/PythonLinux.git)|
|INSTALL_ROOT|Parent-Verzeichnis für das Projekt|/opt|
|PROJECT_NAME|Verzeichnisname unter INSTALL_ROOT|PythonLinux|
|PROJECT_DIR|Vollständiger Projektpfad|/opt/PythonLinux|
|WRAPPER_DIR|Zielordner für Wrapper|/usr/local/bin|
|WRAPPER_PREFIX|Präfix für Wrapper-Namen|pl-|
|VERIFY|1 = Python-Syntaxprüfung aktiv, 0 = aus|1|
|PYTHON_SYS_BIN|Pfad zum Fallback-Python|/usr/bin/python3|

Beispiele:

- Eigenes Repo und Präfix:
    
    ```
    sudo REPO_URL=https://github.com/meinuser/meinrepo.git \
         WRAPPER_PREFIX=my- \
         ./install.sh
    ```
    
- Wrapper nur im Home (für Tests in einer VM/Container – erfordert Root wegen require_root):
    
    ```
    sudo WRAPPER_DIR=/usr/local/bin \
         INSTALL_ROOT=/opt \
         ./install.sh
    ```
    

Tipp: Du kannst PROJECT_DIR direkt setzen, um sowohl INSTALL_ROOT als auch PROJECT_NAME zu übersteuern:

```
sudo PROJECT_DIR=/srv/apps/PythonLinux ./install.sh
```

---

### 🐍 Virtuelle Umgebungen (venv.txt)

- Eine venv wird nur in Ordnern erzeugt, in denen eine Datei venv.txt liegt.
    
- Format: Ein Paket pro Zeile, Kommentare mit #, leere Zeilen erlaubt.
    
- Beispiel venv.txt:
    
    ```
    # Basis-Tools
    rich
    tqdm
    # PDF
    PyPDF2
    pymupdf4llm
    ```
    
- Installation:
    
    - Erstellt <ordner>/.venv, falls nicht vorhanden.
    - Aktualisiert pip, wheel, setuptools.
    - Installiert die Pakete aus venv.txt.

Wichtig: Die Wrapper wählen zur Laufzeit automatisch die nächste .venv von unten nach oben. Du kannst also eine zentrale venv.txt in einem gemeinsamen Elternordner platzieren, die dann für darunterliegende Skripte greift.

---

### 🧪 Syntaxprüfung (optional)

- Gesteuert über VERIFY (Standard: 1).
- Prüft jedes Python-Skript mit py_compile (ohne Ausführung).
- Bei Fehlern: Warnung, aber der Wrapper wird dennoch erstellt. Das erleichtert schrittweise Migrationen.

Deaktivieren:

```
sudo VERIFY=0 ./install.sh
```

---

### 🔐 Dateirechte

- Python-Dateien (*.py) werden auf 0644 gesetzt (nicht ausführbar; Ausführung erfolgt über den Interpreter).
- Shell-Skripte (*.sh) werden auf 0755 gesetzt (ausführbar).
- Wrapper in /usr/local/bin sind ausführbar (install -m 0755 …).

---

### 🚀 Installation

1. Skript verfügbar machen (z. B. aus Ihrer Quelle in ein Arbeitsverzeichnis legen)
2. Ausführen:
    
    ```
    sudo ./install.sh
    ```
    
3. Ergebnis:
    - Repository liegt unter /opt/PythonLinux (Standard).
    - Wrapper liegen unter /usr/local/bin und heißen pl-<name>.

Überprüfung:

```
which pl-foo
pl-foo --help  # falls Skript eine Hilfe unterstützt
```

---

### 🔄 Aktualisierung (Update)

Das Skript ist idempotent. Für Updates genügt:

```
sudo ./install.sh
```

- Holt neue Commits (git fetch + pull).
- Aktualisiert venvs dort, wo venv.txt existiert.
- Erzeugt neue Wrapper für neue Skripte und aktualisiert bestehende Wrapper.

---

### 🧹 Deinstallation

Vorsicht: Es gibt keinen automatischen Uninstaller. Nachfolgende Schritte helfen bei einer sauberen Entfernung.

1. Wrapper entfernen, die auf dieses Projekt zeigen:
    
    ```
    PROJECT_DIR=/opt/PythonLinux
    sudo bash -c 'grep -rl --null "SCRIPT_PATH=\"'"$PROJECT_DIR"'/"
      /usr/local/bin | xargs -0 -r rm -v'
    ```
    
    Tipp (trockenlauf): Ersetze rm -v durch xargs -0 -r -n1 echo
    
2. Projektverzeichnis löschen:
    
    ```
    sudo rm -rf /opt/PythonLinux
    ```
    
3. Optional: Unbenutzte venvs/Pakete prüfen (falls außerhalb des Projektbaums angelegt – standardmäßig nicht).
    

---

### 🐞 Fehlerbehebung (Troubleshooting)

- „Bitte als root ausführen“  
    → Mit sudo starten:
    
    ```
    sudo ./install.sh
    ```
    
- apt-get Fehler (Netzwerk/Proxy/Repo)  
    → Netzwerk/Proxy konfigurieren, apt-Quellen prüfen, erneut ausführen.
    
- pip-Installationsfehler (z. B. Build-Tools fehlen)  
    → Fehlermeldung lesen; ggf. zusätzliche Systempakete installieren (z. B. build-essential, libffi-dev, python3-dev), dann erneut ausführen.  
    → Bei Unternehmensproxies: Umgebungsvariablen wie HTTPS_PROXY setzen.
    
- Wrapper findet keine .venv  
    → Liegt eine venv.txt im Skriptordner (oder einem Elternordner unterhalb des Repo-Roots)?  
    → Wurde die venv erstellt? Prüfe auf <ordner>/.venv/bin/python.  
    → Andernfalls wird System-Python genutzt.
    
- Zwei Skripte mit gleichem Namen erzeugen einen Namenskonflikt  
    → Gewollt: Das zweite Skript bekommt automatisch einen pfadbasierten Namen (z. B. pl-game-foo).  
    → Alternativ: WRAPPER_PREFIX anpassen oder Skriptnamen ändern.
    
- Ausführung scheitert mit „Permission denied“  
    → Prüfe Rechte: Wrapper müssen 0755 sein; das Skript setzt das automatisch.  
    → PATH prüfen: /usr/local/bin sollte in PATH vor /usr/bin liegen.
    
- Non-Debian-System  
    → apt_install_deps an die Paketverwaltung anpassen (dnf/yum/zypper).  
    → Oder in Container/VM mit Debian/Ubuntu ausführen.
    
- Hinweis zu einer kleinen Auffälligkeit:  
    In ensure_venv_for_dir wird pip zweimal direkt hintereinander upgegradet:
    
    ```
    "${pip}" install --upgrade pip wheel setuptools >/dev/null; local pip=...
    "${pip}" install --upgrade pip wheel setuptools >/dev/null
    ```
    
    Das ist funktional harmlos (zweites Upgrade ist idempotent), kann aber ohne Funktionsverlust auf einen einzigen Aufruf reduziert werden.
    

---

### 🧪 Beispiel: Eigene venv für ein Untermodul

Angenommen, du hast ein Skript bin/report/gen.py mit Abhängigkeiten pandas und rich.

1. venv.txt in bin/report/ anlegen:
    
    ```
    pandas
    rich
    ```
    
2. Installationsskript ausführen:
    
    ```
    sudo ./install.sh
    ```
    
3. Ergebnis:
    - /opt/PythonLinux/bin/report/.venv existiert.
    - Wrapper /usr/local/bin/pl-gen wurde angelegt.
    - Aufruf:
        
        ```
        pl-gen --help
        ```
        
    - Der Wrapper nutzt automatisch die .venv unter bin/report/.

---

### 🧰 Anpassungen und Best Practices

- Paketstände fixieren: In venv.txt Versionen pinnen, z. B. rich==13.7.1, um reproduzierbare Umgebungen zu erhalten.
- Gemeinsame venv: Lege venv.txt in einem Elternordner (z. B. bin/) ab, wenn mehrere Skripte dieselben Pakete teilen sollen.
- Rollbacks: Da ein git pull --ff-only genutzt wird, sind Hard-Resets auf den Remote-Default-Branch nur im Sonderfall (fehlendes Upstream) vorgesehen. Für kontrollierte Releases empfiehlt sich ein definierter Branch/Tag und ggf. REPO_URL/Branch-Strategie im eigenen Fork.

---

### 🧾 Ausgaben und ihre Bedeutung

- 🟢 …: Normale Statusmeldung
- 🟠 …: Warnung (z. B. leere venv.txt oder Syntaxfehler; der Prozess läuft weiter)
- 🔴 …: Fehler, der zum Abbruch führt
- ⚙️ …: Installation von Systemabhängigkeiten
- 📥 …: Repo aktualisieren
- 🧭 …: Repo klonen
- 🧩 …: venv.txt angelegt (PyPDF-Erstinstallation)
- 🔧 …: venv-Prüfung/Installation
- 🛡️ …: Dateirechte gesetzt
- 🧪 …: Skriptprüfung/Wrapper-Erzeugung
- 🪄 …: Wrapper wurde erzeugt
- ✅ …: Alles abgeschlossen

---

### ❓FAQ

- Muss ich die Wrapper direkt aufrufen?  
    Nein, aber es ist bequem. Die Wrapper kümmern sich um die richtige Python-Umgebung. Alternativ kannst du die Skripte auch manuell mit einem Interpreter starten.
    
- Woher weiß der Wrapper, welche venv er nehmen soll?  
    Er sucht vom Skriptordner aus nach oben, bis er eine .venv findet oder auf .repo-root stößt.
    
- Werden bestehende Wrapper überschrieben?  
    Ja, Wrapper mit gleichem Namen werden bei erneutem Lauf aktualisiert (install -m 0755 …).
    
- Kann ich ohne Root installieren?  
    Das Skript verlangt Root (require_root). Für eine reine Benutzerinstallation müsste das Skript angepasst werden (andere WRAPPER_DIR/INSTALL_ROOT und require_root entfernen/ändern). Alternativ: in einem Container/VM mit Root ausführen.
    

---

### 📌 Zusammenfassung

Das Skript bietet einen sicheren, reproduzierbaren Weg, ein Python-Projekt systemweit zu deployen:

- Git-Update, venv-Management per Markerdatei venv.txt, robuste Wrapper mit automatischer Interpreterwahl.
- Klar strukturierte Ausgaben und idempotentes Verhalten ermöglichen wiederholbare Updates.
- Über Umgebungsvariablen lässt sich der Installationsort, die Wrapper-Strategie und die Python-Prüfung flexibel anpassen.

Wenn du möchtest, passe ich dir eine „Uninstall“-Routine, eine per-User-Installation (ohne Root) oder ein RPM-/DNF-kompatibles apt_install_deps an.\n\n<!-- AUTOGEN_START -->

---
#Files
![[install.sh]]
<!-- AUTOGEN_END -->
\n