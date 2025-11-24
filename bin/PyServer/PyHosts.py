#!/usr/bin/env python3
import os
import socket
from datetime import datetime

HOSTS_FILE = "/etc/hosts"

# Determine IPs from ENV or (for IP1) via socket fallback
def get_ip(env_var):
    ip = os.getenv(env_var)
    if ip:
        return ip
    if env_var == "IP1":
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
        finally:
            s.close()
    return None

IP1 = get_ip("IP1")

# Domains come from Bash wrapper via ENV: LOCAL_DOMAIN, GLOBAL_DOMAIN
# Hardcoded lists:
DOMAINS_IP1 = "$LOCAL_DOMAIN"
DOMAINS_IP2 = "$GLOBAL_DOMAIN"

# Logging function
def log(msg):
    print(f"{datetime.now():%Y-%m-%d %H:%M:%S} - {msg}")

# Add entries if not present
def add_entries(ip, domains, header):
    if not ip or not domains:
        return
    with open(HOSTS_FILE, "r") as f:
        lines = f.readlines()
    if not any(header in line for line in lines):
        with open(HOSTS_FILE, "a") as f:
            f.write(f"{header}\n")
    with open(HOSTS_FILE, "a") as f:
        for d in domains:
            if d and not any(d in line.split() for line in lines):
                f.write(f"{ip} {d}\n")
                log(f"Entry added: {ip} {d}")

if __name__ == "__main__":
    if os.geteuid() != 0:
        print("This script must be run as root!")
        exit(1)

    add_entries(IP1, DOMAINS_IP1, "#====== LOCAL_DOMAIN ======")
    add_entries(IP1, DOMAINS_IP2, "#====== GLOBAL_DOMAIN ======")