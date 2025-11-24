#!/usr/bin/env python3
import os
import sys
import subprocess
import importlib

# ======================================================
# HIER nur den Config-Namen ändern (ohne .py)
# z.B. "pihole", "proxmox", "nextcloud", ...
# ======================================================
CONFIG_MODULE_NAME = "pihole"
# ======================================================

HOME = os.path.expanduser("~")
SSH_DIR = os.path.join(HOME, ".ssh")

# ~/.ssh als Suchpfad für Python-Module hinzufügen
sys.path.insert(0, SSH_DIR)

try:
    print(f"📁 Lade Config-Modul '{CONFIG_MODULE_NAME}' aus {SSH_DIR} ...")
    config = importlib.import_module(CONFIG_MODULE_NAME)
    print("✅ Config erfolgreich geladen.\n")
except ImportError as e:
    print(f"❌ [FEHLER] Konnte Config-Modul '{CONFIG_MODULE_NAME}' nicht laden.")
    print(f"   Erwartet: {SSH_DIR}/{CONFIG_MODULE_NAME}.py")
    print(f"   Originalfehler: {e}")
    sys.exit(1)

# Werte aus dem Config-Modul holen
SSH_KEY_FILE = getattr(config, "SSH_KEY_FILE", "id_ed25519")
SSH_USER     = getattr(config, "SSH_USER", "root")
SSH_HOST     = getattr(config, "SSH_HOST", None)
SSH_PORT     = getattr(config, "SSH_PORT", 22)

PROMPT_TAG   = getattr(config, "PROMPT_TAG", CONFIG_MODULE_NAME.upper())
COLOR_STD    = getattr(config, "COLOR_STD", "0;32")
COLOR_PROMPT = getattr(config, "COLOR_PROMPT", "1;32")

if SSH_HOST is None:
    print("❌ [FEHLER] In der Config fehlt SSH_HOST.")
    sys.exit(1)

SSH_KEY_PATH = os.path.join(SSH_DIR, SSH_KEY_FILE)


def ensure_bashrc_color_block():
    """
    Legt auf dem SERVER/CT in ~/.bashrc den Block an:

    # ===========================================
    # Farbmodus nur, wenn per SSH verbunden
    # ===========================================
    if [ -n "$SSH_CONNECTION" ]; then
        printf '\e[0;32m'
        PS1='...'
        trap 'printf "\e[0m"' EXIT
    fi

    → mit Tag/Farben aus der Config.
    → nur, wenn der Block noch nicht existiert.
    """
    print("🎨 Prüfe Farb-Block in ~/.bashrc auf dem Server ...")

    snippet = f"""# BEGIN SSH_COLOR_BLOCK {PROMPT_TAG}
# ===========================================
# Farbmodus nur, wenn per SSH verbunden
# ===========================================
if [ -n "$SSH_CONNECTION" ]; then
    # Standardfarbe auf setzen (alles, was danach ausgegeben wird)
    printf '\\e[{COLOR_STD}m'

    # Prompt schön farbig
    PS1='\\[\\e[{COLOR_PROMPT}m\\][{PROMPT_TAG}] \\u@\\h:\\w# \\[\\e[{COLOR_STD}m\\]'

    # Beim Beenden der SSH-Shell Farben zurücksetzen,
    # damit dein lokales Terminal NICHT bunt bleibt
    trap 'printf "\\e[0m"' EXIT
fi
# END SSH_COLOR_BLOCK {PROMPT_TAG}
"""

    remote_script = f"""mkdir -p ~/.ssh
touch ~/.bashrc
if ! grep -q "BEGIN SSH_COLOR_BLOCK {PROMPT_TAG}" ~/.bashrc 2>/dev/null; then
    echo "➕ Installiere Farb-Block für {PROMPT_TAG} in ~/.bashrc ..."
    cat << 'EOF_SSH_COLOR_BLOCK' >> ~/.bashrc
{snippet}
EOF_SSH_COLOR_BLOCK
else
    echo "ℹ️ Farb-Block für {PROMPT_TAG} bereits vorhanden – übersprungen."
fi
"""

    cmd = [
        "ssh",
        "-i", SSH_KEY_PATH,
        "-p", str(SSH_PORT),
        f"{SSH_USER}@{SSH_HOST}",
        "bash",
        "-lc",
        remote_script,
    ]

    try:
        subprocess.run(cmd, check=True)
        print("✅ ~/.bashrc auf dem Server geprüft/aktualisiert.\n")
    except Exception as e:
        print("⚠️ Konnte ~/.bashrc auf dem Server nicht anpassen:")
        print(f"   {e}\n")


def main():
    print("🔑 SSH-Verbindungsdaten:")
    print(f"   👤 Benutzer : {SSH_USER}")
    print(f"   🌐 Host     : {SSH_HOST}")
    print(f"   🔌 Port     : {SSH_PORT}")
    print(f"   🗝️ Key-Datei: {SSH_KEY_PATH}\n")

    if not os.path.exists(SSH_KEY_PATH):
        print("❌ [FEHLER] SSH-Key-Datei nicht gefunden.")
        print(f"   Pfad: {SSH_KEY_PATH}")
        sys.exit(1)

    # 1️⃣ Vor der Session: Farb-Block in ~/.bashrc sicherstellen
    ensure_bashrc_color_block()

    # 2️⃣ Normale interaktive SSH-Sitzung starten
    cmd = [
        "ssh",
        "-i", SSH_KEY_PATH,
        "-p", str(SSH_PORT),
        f"{SSH_USER}@{SSH_HOST}",
    ]

    print("🖥️ Starte SSH-Verbindung ...")
    print(f"   ➜ Verbinde zu {SSH_USER}@{SSH_HOST} mit Key 🗝️ {SSH_KEY_PATH}\n")

    try:
        subprocess.run(cmd)
        print("\n✅ SSH-Sitzung beendet.")
    except KeyboardInterrupt:
        print("\n⚠️ Verbindung vom Benutzer abgebrochen.")
    except Exception as e:
        print("\n❌ Unerwarteter Fehler bei der SSH-Verbindung:")
        print(f"   🧨 {e}")


if __name__ == "__main__":
    main()
