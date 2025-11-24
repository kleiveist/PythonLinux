#!/usr/bin/env python3
import os
import socket
import subprocess
from datetime import datetime

# 1) Try ENV variable, 2) fallback to socket query
def get_server_ip():
    if ip := os.getenv("SERVER_IP"):
        return ip
    # Fallback
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    finally:
        s.close()

# Pass Bash variable as ENV
SERVER_IP = get_server_ip()
# Prefix from first three octets
PREFIX = ".".join(SERVER_IP.split('.')[:3])

HOSTS = {
    "1.1.1.1": "Cloudflare DNS",
    "8.8.8.8": "Google DNS",
    SERVER_IP: "Server",
    f"{PREFIX}.1": "RouterHome",
    f"{PREFIX}.4": "Pi-hole DNS",
    f"{PREFIX}.5": "VPN Server",
    "$LOCAL_DOMAIN": "domain1",
    "$GLOBAL_DOMAIN": "domain2",
}

def ping_host(host):
    try:
        subprocess.run(
            ["ping", "-c", "3", "-W", "2", host],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        return True
    except subprocess.CalledProcessError:
        return False

def main():
    print("==== Starting Ping Test ====")
    print(f"Date: {datetime.now():%Y-%m-%d %H:%M:%S}\\n")
    failed = []
    for host, desc in HOSTS.items():
        print(f"Pinging {host} ({desc})…")
        if ping_host(host):
            print(f"{host} ({desc}) is reachable ✅")
        else:
            failed.append(f"{host} ({desc})")
            print(f"{host} ({desc}) is unreachable ❌")
        print()
    print("==== Ping Test Completed ====")
    if failed:
        print("==== Failed Hosts ====")
        print(*failed, sep="\n")
    else:
        print("All hosts are reachable ✅")

if __name__ == "__main__":
    main()