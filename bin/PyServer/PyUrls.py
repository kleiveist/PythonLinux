#!/usr/bin/env python3
import os
import ssl
import urllib.request
from datetime import datetime
from typing import List, Tuple


def log_message(message: str) -> None:
    """Log message with timestamp (ähnlich zur Bash-Funktion log_message)."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"{now} - {message}")


def get_env_var(name: str) -> str:
    """Hole eine Umgebungsvariable oder wirf einen Fehler, wenn sie fehlt."""
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Umgebungsvariable {name} ist nicht gesetzt.")
    return value


def build_urls(server_ip: str, local_domain: str, global_domain: str) -> List[str]:
    """Erzeuge die gleiche URL-Liste wie im Bash-Skript."""
    return [
        f"http://{server_ip}",
        f"https://{server_ip}",
        f"http://{local_domain}",
        f"https://{local_domain}",
        f"http://{global_domain}",
        f"https://{global_domain}",
    ]


def check_url(url: str, timeout: int = 5) -> Tuple[str, str]:
    """
    Prüfe eine URL mit einem HEAD-Request.
    Entspricht grob: curl -k -I --silent --fail --max-time 5
    """
    # SSL-Überprüfung deaktivieren (wie curl -k / --insecure)
    context = ssl._create_unverified_context()

    request = urllib.request.Request(url, method="HEAD")

    try:
        with urllib.request.urlopen(request, timeout=timeout, context=context):
            mark = "✅"
    except Exception:
        mark = "❌"

    return url, mark


def print_table(results: List[Tuple[str, str]]) -> None:
    """Gibt die Ergebnisse als ASCII-Tabelle aus, ähnlich dem Bash-Skript."""
    col_width_url = 60
    col_width_mark = 3

    def border(char: str = "-") -> str:
        return (
            "+-" + (char * col_width_url) + "-+-" + (char * col_width_mark) + "-+"
        )

    # Kopfzeile
    print(border("-"))
    print(f"| {'URL':{col_width_url}} | {'':{col_width_mark}} |")
    print(border("="))

    # Datenzeilen
    for url, mark in results:
        print(f"| {url:{col_width_url}} | {mark:{col_width_mark}} |")

    # Fußzeile
    print(border("-"))


def main() -> None:
    # Entspricht den "Dynamic variables" aus dem Bash-Skript
    server_ip = get_env_var("SERVER_IP")
    local_domain = get_env_var("LOCAL_DOMAIN")
    global_domain = get_env_var("GLOBAL_DOMAIN")

    urls = build_urls(server_ip, local_domain, global_domain)

    results: List[Tuple[str, str]] = []

    for url in urls:
        log_message(f"Prüfe {url}")
        results.append(check_url(url))

    print_table(results)


if __name__ == "__main__":
    main()
