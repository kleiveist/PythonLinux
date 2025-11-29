#!/usr/bin/env python3
import subprocess
import sys

cmd = ["flatpak", "run", "--command=alvr_launcher", "com.valvesoftware.Steam"]

try:
    subprocess.run(cmd, check=True)
except FileNotFoundError:
    print("Fehler: 'flatpak' wurde nicht gefunden. Ist Flatpak installiert?")
    sys.exit(1)
except subprocess.CalledProcessError as e:
    print(f"ALVR konnte nicht gestartet werden (Exit-Code {e.returncode}).")
    sys.exit(e.returncode)
