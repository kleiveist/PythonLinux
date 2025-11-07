#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Systemreport für Linux (Arch/CachyOS u. a.)
- Ausgabe mit Icons und Tabellen (rich)
- Optional: Markdown-Datei auf dem Desktop via --md
- Sammelt: OS/Kern, Uptime, CPU, RAM (inkl. Module, sofern Root/dmidecode),
  GPU (lspci/lshw, nvidia-smi/rocm-smi wenn vorhanden), Datenträger (lsblk),
  Mainboard/BIOS (dmidecode), Netzwerk, Virtualisierung.
"""

import os
import re
import json
import time
import shlex
import shutil
import socket
import platform
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

# Drittanbieter
try:
    import psutil
except ImportError:
    print("Fehlt: psutil  -> pip install psutil  oder  pacman -S python-psutil")
    raise

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich import box
except ImportError:
    print("Fehlt: rich  -> pip install rich  oder  pacman -S python-rich")
    raise

# distro ist praktisch für Distros
try:
    import distro
except ImportError:
    distro = None
    # Hinweis in Ausgabe

# CPU-Details
try:
    import cpuinfo
except ImportError:
    cpuinfo = None

console = Console()

def run_cmd(cmd, timeout=10):
    """
    Führt einen Shell-Befehl aus und liefert stdout (str) oder None.
    """
    try:
        if isinstance(cmd, str):
            proc = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, text=True)
        else:
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, text=True)
        if proc.returncode == 0 and proc.stdout:
            return proc.stdout.strip()
        return None
    except Exception:
        return None

def which(cmd):
    return shutil.which(cmd) is not None

def bytes_to_gib(b):
    try:
        return b / (1024 ** 3)
    except Exception:
        return None

def human_bytes(num, suffix="B"):
    # 1024er Schritte
    for unit in ["","Ki","Mi","Gi","Ti","Pi"]:
        if abs(num) < 1024.0:
            return f"{num:,.2f} {unit}{suffix}".replace(",", ".")
        num /= 1024.0
    return f"{num:.2f} Ei{suffix}"

def get_os_info():
    uname = platform.uname()
    kern_rel = uname.release
    kern_ver = uname.version
    arch = uname.machine
    hostname = uname.node

    # Distro
    if distro:
        dist_name = distro.name(pretty=True)
        dist_ver = distro.version(best=True)
        dist_id = distro.id()
        distro_str = dist_name if dist_name else (dist_id or "Unbekannt")
        if dist_ver:
            distro_str += f" {dist_ver}"
    else:
        # Fallback: /etc/os-release lesen
        distro_str = "Unbekannt"
        try:
            with open("/etc/os-release", "r", encoding="utf-8") as f:
                data = dict(line.strip().replace('"','').split("=",1) for line in f if "=" in line)
            distro_str = data.get("PRETTY_NAME") or data.get("NAME") or "Unbekannt"
        except Exception:
            pass

    # Uptime
    try:
        boot = datetime.fromtimestamp(psutil.boot_time())
        uptime_td = datetime.now() - boot
        uptime = str(uptime_td).split(".")[0]
    except Exception:
        uptime = "n/a"

    # Virtualisierung
    virt = "none"
    if which("systemd-detect-virt"):
        out = run_cmd("systemd-detect-virt")
        if out:
            virt = out.strip()
    elif which("virt-what"):
        out = run_cmd("virt-what")
        virt = out.strip() if out else "none"

    return {
        "Hostname": hostname,
        "Distro": distro_str,
        "Kernel": f"{kern_rel}",
        "Kernel-Details": kern_ver,
        "Architektur": arch,
        "Uptime": uptime,
        "Virtualisierung": virt,
    }

def get_cpu_info():
    info = {}
    # psutil
    info["Logische Kerne"] = psutil.cpu_count(logical=True)
    info["Physische Kerne"] = psutil.cpu_count(logical=False)

    freq = None
    try:
        f = psutil.cpu_freq()
        if f:
            freq = f.current
            info["Takt (aktuell)"] = f"{f.current/1000:.2f} GHz"
            info["Takt (min/max)"] = f"{f.min/1000:.2f} / {f.max/1000:.2f} GHz"
    except Exception:
        pass

    if cpuinfo:
        try:
            ci = cpuinfo.get_cpu_info()
            if ci.get("brand_raw"):
                info["Modell"] = ci["brand_raw"]
            if ci.get("arch"):
                info["Architektur"] = ci["arch"]
            if ci.get("vendor_id_raw"):
                info["Hersteller"] = ci["vendor_id_raw"]
            # advertised hz
            hz = ci.get("hz_advertised_friendly") or ci.get("hz_advertised")
            if hz and "Takt (beworben)" not in info:
                info["Takt (beworben)"] = str(hz)
            l2 = ci.get("l2_cache_size")
            l3 = ci.get("l3_cache_size")
            if l2: info["L2-Cache"] = str(l2)
            if l3: info["L3-Cache"] = str(l3)
            flags = ci.get("flags")
            if flags:
                info["Features"] = ", ".join(sorted(flags)[:20]) + (" …" if len(flags) > 20 else "")
        except Exception:
            pass
    else:
        info["Hinweis"] = "Für detailliertere CPU-Daten: python-cpuinfo installieren."

    return info

def parse_dmidecode_memory(text):
    modules = []
    cur = {}
    for line in text.splitlines():
        if line.strip() == "Memory Device":
            if cur:
                modules.append(cur)
            cur = {}
        else:
            m = re.match(r"\s*(Size|Type|Speed|Manufacturer|Part Number|Locator|Configured Memory Speed|Form Factor):\s*(.*)", line)
            if m:
                key, val = m.group(1), m.group(2).strip()
                cur[key] = val
    if cur:
        modules.append(cur)
    # Filter sinnvolle Module
    modules = [m for m in modules if any(k in m for k in ("Size","Type","Speed","Manufacturer","Part Number"))]
    return modules

def get_ram_info():
    info = {}
    vm = psutil.virtual_memory()
    info["Gesamt"] = human_bytes(vm.total)
    info["Verfügbar"] = human_bytes(vm.available)
    info["Belegt"] = f"{human_bytes(vm.used)} ({vm.percent:.1f}%)"
    # Swap
    sm = psutil.swap_memory()
    info["Swap"] = f"{human_bytes(sm.total)} (belegt: {human_bytes(sm.used)} / {sm.percent:.1f}%)"

    modules = []
    if which("dmidecode"):
        out = run_cmd("dmidecode -t memory", timeout=20)
        if out:
            modules = parse_dmidecode_memory(out)
            info["Hinweis"] = "RAM-Module voll auslesbar."
        else:
            info["Hinweis"] = "Für RAM-Modul-Details: mit sudo ausführen (dmidecode)."
    else:
        info["Hinweis"] = "Tool 'dmidecode' nicht gefunden – weniger Details."

    return info, modules

def get_gpu_info():
    gpus = []

    # 1) NVIDIA spezifisch
    if which("nvidia-smi"):
        out = run_cmd("nvidia-smi --query-gpu=name,driver_version,memory.total,clocks.gr --format=csv,noheader,nounits")
        if out:
            for line in out.splitlines():
                try:
                    name, drv, mem_mb, clk_mhz = [x.strip() for x in line.split(",")]
                    gpus.append({
                        "Vendor": "NVIDIA",
                        "Name": name,
                        "Treiber": drv,
                        "VRAM": f"{int(mem_mb)/1024:.2f} GiB",
                        "GPU-Clock": f"{clk_mhz} MHz"
                    })
                except Exception:
                    pass

    # 2) AMD ROCm (optional)
    if not gpus and which("rocm-smi"):
        out = run_cmd("rocm-smi --showproductname --showvbios --showmeminfo vram --showclocks", timeout=15)
        if out:
            # Grobe Extraktion
            prod = re.findall(r"Card\s+\d+:\s+(.+)", out)
            vram = re.findall(r"VRAM\s+Total Memory:\s+(\d+)\s+MiB", out)
            clk = re.findall(r"Current GPU clock\s*:\s*(\d+)\s*MHz", out)
            name = prod[0].strip() if prod else "AMD GPU"
            vr = f"{int(vram[0])/1024:.2f} GiB" if vram else "n/a"
            ghz = f"{clk[0]} MHz" if clk else "n/a"
            gpus.append({"Vendor":"AMD","Name":name,"VRAM":vr,"GPU-Clock":ghz})

    # 3) lshw JSON (allgemein)
    if which("lshw"):
        out = run_cmd("lshw -C display -json", timeout=20)
        if out:
            try:
                data = json.loads(out)
                if isinstance(data, dict):
                    data = [data]
                for d in data:
                    prod = d.get("product") or "Display-Controller"
                    vend = d.get("vendor") or ""
                    conf = d.get("configuration", {})
                    clk = conf.get("clock")
                    size = None
                    # lshw gibt 'size' tlw. in Bytes an:
                    if isinstance(d.get("size"), int):
                        size = human_bytes(d.get("size"))
                    elif isinstance(d.get("capacity"), int):
                        size = human_bytes(d.get("capacity"))
                    gpus.append({
                        "Vendor": vend.strip(),
                        "Name": prod.strip(),
                        "VRAM": size or "n/a",
                        "GPU-Clock": f"{clk} Hz" if clk else "n/a"
                    })
            except Exception:
                pass

    # 4) lspci Fallback
    if not gpus and which("lspci"):
        out = run_cmd("lspci -mm -nn | egrep 'VGA|3D|Display'")
        if out:
            for line in out.splitlines():
                # Beispiel: '01:00.0 "VGA compatible controller" "NVIDIA Corporation" ... "GeForce RTX ..."'
                parts = [p.strip().strip('"') for p in line.split('"') if p.strip()]
                # Vendor/Prod heuristisch
                vendor = parts[2] if len(parts) > 2 else "Unbekannt"
                name = parts[4] if len(parts) > 4 else parts[-1] if parts else "GPU"
                gpus.append({"Vendor": vendor, "Name": name, "VRAM": "n/a", "GPU-Clock":"n/a"})

    # 5) glxinfo für Renderer
    renderer = None
    if which("glxinfo"):
        out = run_cmd("glxinfo -B")
        if out:
            m = re.search(r"OpenGL renderer string:\s*(.+)", out)
            if m:
                renderer = m.group(1).strip()

    return gpus, renderer

def get_storage_info():
    disks = []
    if which("lsblk"):
        out = run_cmd("lsblk -J -O")
        if out:
            try:
                data = json.loads(out)
                for dev in data.get("blockdevices", []):
                    if dev.get("type") == "disk":
                        entry = {
                            "Name": dev.get("name"),
                            "Modell": dev.get("model"),
                            "Größe": human_bytes(dev.get("size") or 0) if isinstance(dev.get("size"), int) else (dev.get("size") or "n/a"),
                            "Schnittstelle": dev.get("tran") or "n/a",
                            "Rotational": "HDD" if dev.get("rota") else "SSD",
                            "Seriennr.": dev.get("serial") or "n/a",
                        }
                        parts = []
                        for ch in dev.get("children", []) or []:
                            parts.append({
                                "Partition": ch.get("name"),
                                "FS": ch.get("fstype") or "n/a",
                                "Mount": ch.get("mountpoint") or ""
                            })
                        entry["Partitionen"] = parts
                        disks.append(entry)
            except Exception:
                pass
    return disks

def get_board_bios_info():
    board = {}
    bios = {}
    if which("dmidecode"):
        out_b = run_cmd("dmidecode -t baseboard", timeout=15)
        out_bios = run_cmd("dmidecode -t bios", timeout=15)
        if out_b:
            for k in ("Manufacturer","Product Name","Version","Serial Number"):
                m = re.search(rf"{k}:\s*(.+)", out_b)
                if m:
                    board[k] = m.group(1).strip()
        if out_bios:
            for k in ("Vendor","Version","Release Date"):
                m = re.search(rf"{k}:\s*(.+)", out_bios)
                if m:
                    bios[k] = m.group(1).strip()
    return board, bios

def get_network_info():
    nics = []
    # Namen + MAC + Status
    try:
        for name, addrs in psutil.net_if_addrs().items():
            mac = next((a.address for a in addrs if a.family == psutil.AF_LINK), None)
            ipv4 = next((a.address for a in addrs if a.family == socket.AF_INET), None)
            ipv6 = next((a.address for a in addrs if a.family == socket.AF_INET6), None)
            stats = psutil.net_if_stats().get(name)
            up = stats.isup if stats else False
            speed = f"{stats.speed} Mbit/s" if stats and stats.speed > 0 else "n/a"
            nics.append({
                "Interface": name,
                "MAC": mac or "n/a",
                "IPv4": ipv4 or "",
                "IPv6": ipv6 or "",
                "Up": "Ja" if up else "Nein",
                "Speed": speed
            })
    except Exception:
        pass

    # lspci Ethernet/WLAN
    pci_lines = []
    if which("lspci"):
        out = run_cmd("lspci -nn | egrep -i 'ethernet|network|wireless'")
        if out:
            pci_lines = out.splitlines()
    return nics, pci_lines

def xdg_desktop_path():
    # Versuche XDG-Desktop-Ordner zu ermitteln
    config = Path.home() / ".config" / "user-dirs.dirs"
    if config.exists():
        try:
            txt = config.read_text(encoding="utf-8")
            m = re.search(r'XDG_DESKTOP_DIR="?(.+?)"?\n', txt)
            if m:
                p = m.group(1).replace("$HOME", str(Path.home()))
                return Path(p)
        except Exception:
            pass
    # Fallback
    return Path.home() / "Desktop"

def build_markdown(data):
    lines = []
    add = lines.append

    # Titel
    add(f"# Systemreport – {data['os']['Hostname']}")
    add("")
    add(f"Erstellt am: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    add("")

    # OS
    add("## Betriebssystem 🐧")
    for k,v in data["os"].items():
        add(f"- **{k}:** {v}")
    add("")

    # CPU
    add("## Prozessor 🧠")
    for k,v in data["cpu"].items():
        add(f"- **{k}:** {v}")
    add("")

    # RAM
    add("## Arbeitsspeicher 🧵")
    for k,v in data["ram_summary"].items():
        add(f"- **{k}:** {v}")
    if data["ram_modules"]:
        add("")
        add("### RAM-Module")
        add("| Slot | Größe | Typ | Speed | Hersteller | Part-Nummer |")
        add("|---|---:|---|---:|---|---|")
        for m in data["ram_modules"]:
            add(f"| {m.get('Locator','')} | {m.get('Size','')} | {m.get('Type','')} | {m.get('Configured Memory Speed', m.get('Speed',''))} | {m.get('Manufacturer','')} | {m.get('Part Number','')} |")
    add("")

    # GPU
    add("## Grafik 🎮")
    if data["gpus"]:
        for g in data["gpus"]:
            add(f"- {g.get('Vendor','')} {g.get('Name','')}: VRAM {g.get('VRAM','n/a')}, Takt {g.get('GPU-Clock','n/a')}")
    else:
        add("- Keine GPU-Infos gefunden.")
    if data["glx_renderer"]:
        add(f"- OpenGL Renderer: {data['glx_renderer']}")
    add("")

    # Storage
    add("## Datenträger 💽")
    if data["disks"]:
        for d in data["disks"]:
            add(f"- {d['Name']}: {d['Modell'] or 'n/a'} – {d['Größe']} – {d['Rotational']} – Schnittstelle: {d['Schnittstelle']} – Seriennr.: {d['Seriennr.']}")
            if d["Partitionen"]:
                for p in d["Partitionen"]:
                    add(f"  - {p['Partition']}: {p['FS']} @ {p['Mount']}")
    else:
        add("- Keine Datenträger gefunden.")
    add("")

    # Board/BIOS
    add("## Mainboard/BIOS 🧩")
    if data["board"]:
        add("- Mainboard:")
        for k,v in data["board"].items():
            add(f"  - {k}: {v}")
    if data["bios"]:
        add("- BIOS/UEFI:")
        for k,v in data["bios"].items():
            add(f"  - {k}: {v}")
    add("")

    # Netzwerk
    add("## Netzwerk 🌐")
    if data["nics"]:
        add("| IF | MAC | IPv4 | IPv6 | Up | Speed |")
        add("|---|---|---|---|---|---|")
        for n in data["nics"]:
            add(f"| {n['Interface']} | {n['MAC']} | {n['IPv4']} | {n['IPv6']} | {n['Up']} | {n['Speed']} |")
    if data["nic_pci"]:
        add("")
        add("PCI (Netzwerkcontroller):")
        for l in data["nic_pci"]:
            add(f"- {l}")
    add("")

    return "\n".join(lines)

def print_table(title, rows, icon):
    table = Table(title=f"{icon} {title}", box=box.SIMPLE_HEAVY, show_lines=False)
    table.add_column("Eigenschaft", style="bold")
    table.add_column("Wert")
    for k,v in rows.items():
        table.add_row(str(k), str(v))
    console.print(table)

def print_list_table(title, cols, entries, icon):
    table = Table(title=f"{icon} {title}", box=box.SIMPLE_HEAVY, show_lines=False)
    for c in cols:
        table.add_column(c)
    for e in entries:
        table.add_row(*[str(e.get(c, "")) for c in cols])
    console.print(table)

def main():
    import argparse
    ap = argparse.ArgumentParser(description="Systemreport (Linux) mit Icons und optionaler Markdown-Datei.")
    ap.add_argument("--md", action="store_true", help="Erstellt zusätzlich eine Markdown-Datei auf dem Desktop.")
    args = ap.parse_args()

    # Sammeln
    osi = get_os_info()
    cpi = get_cpu_info()
    ramsum, rammods = get_ram_info()
    gpus, glx = get_gpu_info()
    disks = get_storage_info()
    board, bios = get_board_bios_info()
    nics, nic_pci = get_network_info()

    # Konsole ausgeben
    console.rule("[bold]Systemreport[/bold]")

    print_table("Betriebssystem", osi, "🐧")
    print_table("Prozessor", cpi, "🧠")

    print_table("Arbeitsspeicher", ramsum, "🧵")
    if rammods:
        cols = ["Locator","Size","Type","Configured Memory Speed","Manufacturer","Part Number"]
        # Werte mappen
        mapped = []
        for m in rammods:
            mapped.append({
                "Locator": m.get("Locator",""),
                "Size": m.get("Size",""),
                "Type": m.get("Type",""),
                "Configured Memory Speed": m.get("Configured Memory Speed", m.get("Speed","")),
                "Manufacturer": m.get("Manufacturer",""),
                "Part Number": m.get("Part Number","")
            })
        print_list_table("RAM-Module", ["Locator","Size","Type","Configured Memory Speed","Manufacturer","Part Number"], mapped, "🔩")

    # GPU
    if gpus:
        print_list_table("Grafik", ["Vendor","Name","VRAM","GPU-Clock"], gpus, "🎮")
    else:
        console.print(Panel.fit("Keine GPU-Details gefunden. Installiere lspci/lshw oder nvidia-smi/rocm-smi für mehr Infos.", title="🎮 Grafik", box=box.SIMPLE_HEAVY))
    if glx:
        console.print(Panel.fit(f"OpenGL Renderer: {glx}", title="Renderer", box=box.SIMPLE_HEAVY))

    # Storage
    if disks:
        # Flache Tabelle + Partitionsliste darunter
        cols = ["Name","Modell","Größe","Rotational","Schnittstelle","Seriennr."]
        print_list_table("Datenträger", cols, disks, "💽")
        # Partitionen separat auflisten
        for d in disks:
            parts = d.get("Partitionen", [])
            if parts:
                print_list_table(f"Partitionen von {d['Name']}", ["Partition","FS","Mount"], parts, "📦")
    else:
        console.print(Panel.fit("Keine Datenträger gefunden oder lsblk nicht verfügbar.", title="💽 Datenträger", box=box.SIMPLE_HEAVY))

    # Mainboard/BIOS
    if board or bios:
        if board:
            print_table("Mainboard", board, "🧩")
        if bios:
            print_table("BIOS/UEFI", bios, "🧬")
    else:
        console.print(Panel.fit("Für Mainboard/BIOS-Details dmidecode installieren und ggf. mit sudo ausführen.", title="🧩 Mainboard/BIOS", box=box.SIMPLE_HEAVY))

    # Netzwerk
    if nics:
        print_list_table("Netzwerk-Interfaces", ["Interface","MAC","IPv4","IPv6","Up","Speed"], nics, "🌐")
    if nic_pci:
        console.print(Panel.fit("\n".join(nic_pci), title="PCI Netzwerk-Controller", box=box.SIMPLE_HEAVY))

    console.rule()

    # Markdown speichern
    if args.md:
        data = {
            "os": osi,
            "cpu": cpi,
            "ram_summary": ramsum,
            "ram_modules": rammods,
            "gpus": gpus,
            "glx_renderer": glx,
            "disks": disks,
            "board": board,
            "bios": bios,
            "nics": nics,
            "nic_pci": nic_pci
        }
        md = build_markdown(data)
        desktop = xdg_desktop_path()
        desktop.mkdir(parents=True, exist_ok=True)
        out_path = desktop / "system_report.md"
        out_path.write_text(md, encoding="utf-8")
        console.print(f"📝 Markdown exportiert nach: {out_path}")

if __name__ == "__main__":
    main()
