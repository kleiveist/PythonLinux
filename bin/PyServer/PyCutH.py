#!/usr/bin/env python3
import datetime
from pathlib import Path


def log_message(message: str) -> None:
    """Entspricht der log_message-Funktion im Bash-Skript."""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"{now} - {message}")


def main() -> None:
    hosts_path = Path("/etc/hosts")

    log_message("Starte Anzeige der /etc/hosts Datei")

    print("📁 Contents of /etc/hosts:")
    print("-----------------------------")

    try:
        content = hosts_path.read_text(encoding="utf-8", errors="replace")
        print(content, end="" if content.endswith("\n") else "\n")
    except Exception as e:
        log_message(f"Fehler beim Lesen von {hosts_path}: {e}")

    print("+----------------------------------------------------+")


if __name__ == "__main__":
    main()
