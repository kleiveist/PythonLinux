#!/usr/bin/env python3
import os
import sys
import subprocess
import importlib
import re

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

# Neues Flag: steuert, ob Host-Key-Änderungen automatisch repariert werden
AUTO_ACCEPT_CHANGED_HOSTKEY = getattr(config, "AUTO_ACCEPT_CHANGED_HOSTKEY", True)

if SSH_HOST is None:
    print("❌ [FEHLER] In der Config fehlt SSH_HOST.")
    sys.exit(1)

SSH_KEY_PATH = os.path.join(SSH_DIR, SSH_KEY_FILE)


def run_ssh_with_known_hosts_fix(cmd, description="SSH-Befehl"):
    """Führt einen SSH-Befehl aus und repariert bei Bedarf automatisch known_hosts.

    Verhalten:
    - Wenn alles ok: normale Ausgabe, fertig.
    - Wenn "REMOTE HOST IDENTIFICATION HAS CHANGED":
        * Wenn AUTO_ACCEPT_CHANGED_HOSTKEY = False:
            - NUR Hinweis + Fehlermeldung, keine Änderung an known_hosts.
        * Wenn True:
            - Problematische Zeile aus known_hosts löschen.
            - Befehl EINMAL neu ausführen.
    """
    print(f"🛰  Starte {description} ...")

    # Immer StrictHostKeyChecking=accept-new verwenden, damit NEUE Hosts automatisch
    # akzeptiert werden (das Problem sind ja geänderte Keys, nicht neue).
    base_cmd = cmd[:]
    if base_cmd and base_cmd[0] == "ssh":
        base_cmd = ["ssh", "-o", "StrictHostKeyChecking=accept-new"] + base_cmd[1:]

    result = subprocess.run(base_cmd, capture_output=True, text=True)

    # Erfolg beim ersten Versuch
    if result.returncode == 0:
        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
        print(f"✅ {description} erfolgreich.\n")
        return

    stderr = result.stderr or ""

    offending_match = re.search(
        r"Offending .* key in (?P<file>.+):(?P<line>\d+)",
        stderr,
    )

    # Kein Host-Key-Problem → normaler Fehler
    if "REMOTE HOST IDENTIFICATION HAS CHANGED" not in stderr or not offending_match:
        print(f"❌ {description} fehlgeschlagen.")
        if result.stdout:
            print(result.stdout, end="")
        if stderr:
            print(stderr, end="", file=sys.stderr)
        print()
        return

    offending_file = offending_match.group("file").strip()
    offending_line = int(offending_match.group("line"))

    print("⚠️  Host-Key hat sich geändert.")
    print(f"    Problematischer Eintrag: {offending_file}:{offending_line}")

    if not AUTO_ACCEPT_CHANGED_HOSTKEY:
        print("🚫 AUTO_ACCEPT_CHANGED_HOSTKEY = False – keine automatische Reparatur.")
        print("    Bitte manuell ausführen, z.B.:")
        print(f"    ssh-keygen -R {SSH_HOST}")
        print(f"    ssh-keygen -R {SSH_HOST} # falls als Hostname eingetragen\n")
        print(stderr, end="", file=sys.stderr)
        return

    # Auto-Reparatur ist aktiv
    try:
        with open(offending_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        index = offending_line - 1
        removed_line = None
        if 0 <= index < len(lines):
            removed_line = lines.pop(index).rstrip("\n")
            print(f"    🧹 Entferne Zeile {offending_line} aus known_hosts:")
            print(f"       {removed_line}")
        else:
            print("    ❓ Zeilennummer außerhalb des gültigen Bereichs – keine Änderung.")
            removed_line = None

        with open(offending_file, "w", encoding="utf-8") as f:
            f.writelines(lines)

        print("    💾 known_hosts aktualisiert. Versuche erneut zu verbinden ...\n")

    except Exception as e:
        print("❌ Konnte known_hosts nicht bearbeiten:")
        print(f"   {e}")
        print("   Bitte manuell prüfen (z.B. ssh-keygen -R HOST).\n")
        print(stderr, end="", file=sys.stderr)
        return

    # Zweiter Versuch nach Reparatur
    result2 = subprocess.run(base_cmd, capture_output=True, text=True)

    if result2.returncode == 0:
        if result2.stdout:
            print(result2.stdout, end="")
        if result2.stderr:
            print(result2.stderr, end="", file=sys.stderr)
        print(f"✅ {description} nach Reparatur erfolgreich.\n")
        return
    else:
        print("❌ Auch nach Reparatur von known_hosts gab es einen Fehler:")
        if result2.stdout:
            print(result2.stdout, end="")
        if result2.stderr:
            print(result2.stderr, end="", file=sys.stderr)
        print()
        return


def ensure_bashrc_color_block():
    """Legt auf dem SERVER/CT in ~/.bashrc den Farb-Block an.

    Block sieht etwa so aus:

    # BEGIN SSH_COLOR_BLOCK <TAG>
    ...
    # END SSH_COLOR_BLOCK <TAG>

    und wird nur eingefügt, wenn er noch nicht existiert.
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

    run_ssh_with_known_hosts_fix(cmd, description="Update von ~/.bashrc auf dem Server")


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
