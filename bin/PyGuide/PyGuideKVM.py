#!/usr/bin/env python3
import os
import subprocess
import shutil

BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"
GREEN = "\033[32m"
BLUE = "\033[34m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
RED = "\033[31m"

def line():
    print(f"{DIM}────────────────────────────────────────────────────────────{RESET}")

def title():
    os.system("clear")
    print(f"\n{BOLD}🐧 KVM/QEMU & virt-manager Anleitung für CachyOS{RESET}")
    line()
    print(f"{DIM}Dieses Skript führt NICHT automatisch Installationen aus,")
    print("sondern zeigt dir die empfohlenen Schritte und Befehle." + RESET)

def step(nr, text):
    print(f"\n{BOLD}{BLUE}➤ Schritt {nr}:{RESET} {text}")

def cmd(text):
    print(f"   {CYAN}⮡ Befehl:{RESET} {text}")

def info(text):
    print(f"   {YELLOW}ℹ{RESET} {text}")

def warn(text):
    print(f"   {RED}⚠{RESET} {text}")

def good(text):
    print(f"   {GREEN}✔{RESET} {text}")

def check_virtualization():
    print(f"\n{BOLD}🧠 CPU & Virtualisierung prüfen{RESET}")
    line()
    lscpu = shutil.which("lscpu")
    if not lscpu:
        warn("Befehl 'lscpu' wurde nicht gefunden. Kann Virtualisierung nicht automatisch prüfen.")
        info("Du kannst das Paket, das 'lscpu' enthält (util-linux), nachinstallieren und dann:")
        cmd("lscpu | grep -E 'svm|vmx'")
        return

    try:
        out = subprocess.check_output([lscpu], text=True, stderr=subprocess.DEVNULL)
        if "svm" in out or "vmx" in out:
            good("Hardware-Virtualisierung wurde gefunden (svm/vmx vorhanden).")
        else:
            warn("Keine Hardware-Virtualisierung erkannt (svm/vmx fehlen).")
            warn("Bitte im BIOS/UEFI nach 'SVM', 'AMD-V' oder 'Intel VT-x' suchen und aktivieren.")
    except subprocess.CalledProcessError:
        warn("Konnte 'lscpu' nicht ausführen.")
    info("Du kannst selbst testen mit:")
    cmd("lscpu | grep -E 'svm|vmx'")

def show_steps():
    step(1, "System aktualisieren 💾")
    info("Halte zuerst dein CachyOS/Arch-System auf dem neuesten Stand.")
    cmd("sudo pacman -Syu")
    warn("Falls 404-Fehler bei CachyOS-Repos auftauchen, zuerst die Mirrorliste reparieren:")
    cmd("sudo cachyos-rate-mirrors")

    step(2, "Virtualisierungspakete installieren ⚙️")
    info("Schlanke Variante, ausreichend für KVM + libvirt + virt-manager:")
    cmd("sudo pacman -S --needed qemu-base qemu-system-x86 qemu-img libvirt virt-manager dnsmasq iptables-nft edk2-ovmf")

    step(3, "libvirtd aktivieren 🔌")
    info("libvirtd ist der Dienst, der die VMs verwaltet.")
    cmd("sudo systemctl enable --now libvirtd.service")
    info("Wenn hier 'Unit libvirtd.service does not exist' kommt, ist libvirt nicht korrekt installiert.")

    step(4, "Benutzer zur libvirt-Gruppe hinzufügen 👤")
    info("Damit du VMs als normaler Benutzer verwalten kannst:")
    cmd("sudo usermod -aG libvirt $USER")
    info("Danach musst du dich ab- und wieder anmelden (oder neu booten).")

    step(5, "Installation testen ✅")
    info("Prüfe, ob libvirt läuft:")
    cmd("virsh list --all")
    good("Wenn eine (ggf. leere) Liste ohne Fehlermeldung erscheint, ist libvirt korrekt aktiv.")

    step(6, "virt-manager starten 🖥")
    info("Grafische Oberfläche zum Verwalten deiner VMs:")
    cmd("virt-manager")
    info("Dort kannst du neue VMs anlegen, Snapshots erstellen usw.")

    step(7, "Beispiel: Windows-VM anlegen 🪟")
    info("1) Windows-ISO von Microsoft herunterladen.")
    info("2) In virt-manager auf 'Neue virtuelle Maschine' klicken.")
    info("3) 'Lokales Installationsmedium (ISO)' wählen und das ISO auswählen.")
    info("4) Als Betriebssystem-Typ Windows 10/11 wählen.")
    info("5) Firmware in den VM-Details auf UEFI (OVMF) stellen.")
    print(f"   {GREEN}✔{RESET} RAM: 8–16 GiB")
    print(f"   {GREEN}✔{RESET} vCPUs: 4–8")
    print(f"   {GREEN}✔{RESET} Disk: 80–150 GiB (qcow2)")

    step(8, "Beispiel: Kali Linux VM anlegen 🐉")
    info("1) Kali-ISO von der offiziellen Kali-Webseite herunterladen.")
    info("2) Wieder 'Neue virtuelle Maschine' → ISO auswählen.")
    info("3) OS-Typ: Debian/Kali.")
    print(f"   {GREEN}✔{RESET} RAM: 4–8 GiB")
    print(f"   {GREEN}✔{RESET} vCPUs: 2–4")
    print(f"   {GREEN}✔{RESET} Disk: 40–60 GiB")

    step(9, "Optionale Performance-Tweaks 🚀")
    info("In den VM-Details (virt-manager):")
    print(f"   {GREEN}✔{RESET} CPU-Typ auf 'host-passthrough' stellen")
    print(f"   {GREEN}✔{RESET} VirtIO für Disk & Netzwerk verwenden (schneller als emulierte Geräte)")
    info("Für Windows brauchst du ggf. zusätzliche VirtIO-Treiber (separate ISO von Fedora/RedHat-Seite).")

def summary():
    line()
    print(f"{BOLD}📋 Kurzüberblick{RESET}")
    print(f"  {GREEN}1.{RESET} System aktualisieren (pacman -Syu)")
    print(f"  {GREEN}2.{RESET} qemu, libvirt, virt-manager, ovmf installieren")
    print(f"  {GREEN}3.{RESET} libvirtd aktivieren und Benutzer zur Gruppe libvirt hinzufügen")
    print(f"  {GREEN}4.{RESET} Reboot / neu einloggen")
    print(f"  {GREEN}5.{RESET} virt-manager starten und VMs (Windows, Kali) anlegen\n")
    print(f"{DIM}Hinweis: Dieses Skript ist nur eine Anleitung.")
    print("Du musst die angezeigten Befehle selbst im Terminal ausführen." + RESET)
    line()

def main():
    title()
    check_virtualization()
    show_steps()
    summary()

if __name__ == "__main__":
    main()
