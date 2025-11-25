#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

# ---------- Settings ----------
# Hier können die Standardwerte für Nutzer, Mountpoint und Datenträger-Labels
# bequem angepasst werden. Weitere Datenträger einfach in DEFAULT_LABELS ergänzen
# oder entfernen.
DEFAULT_USER = "kleif"
DEFAULT_MOUNTPOINT = ""
DEFAULT_LABELS = [
    "T7-1TB",
    "T7-2TB",
]

# ---------- UI/Styling ----------
def _supports_color():
    return sys.stdout.isatty() and os.environ.get("NO_COLOR", "") == ""

def _supports_emoji():
    # lässt sich bei Bedarf mit NO_EMOJI=1 abschalten
    no_emoji = os.environ.get("NO_EMOJI", "") != ""
    return (not no_emoji) and sys.stdout.isatty()

COLOR = _supports_color()
EMOJI = _supports_emoji()

class C:
    if COLOR:
        BOLD = "\033[1m"
        DIM = "\033[2m"
        RED = "\033[31m"
        GREEN = "\033[32m"
        YELLOW = "\033[33m"
        BLUE = "\033[34m"
        MAGENTA = "\033[35m"
        CYAN = "\033[36m"
        GRAY = "\033[90m"
        RESET = "\033[0m"
    else:
        BOLD = DIM = RED = GREEN = YELLOW = BLUE = MAGENTA = CYAN = GRAY = RESET = ""

I = {
    "section": "🧭" if EMOJI else "==",
    "check":   "✅" if EMOJI else "[OK]",
    "fail":    "❌" if EMOJI else "[X]",
    "warn":    "⚠️" if EMOJI else "[!]",
    "info":    "ℹ️" if EMOJI else "[i]",
    "bolt":    "⚡" if EMOJI else "--",
    "disk":    "💽" if EMOJI else "[disk]",
    "folder":  "📁" if EMOJI else "[dir]",
    "lock":    "🔒" if EMOJI else "[lock]",
    "unlock":  "🔓" if EMOJI else "[unlock]",
    "hammer":  "🛠️" if EMOJI else "[fix]",
    "spark":   "✨" if EMOJI else "*",
}

def section(title):
    print(f"\n{C.BOLD}{I['section']} {title}{C.RESET}")

def info(msg):
    print(f"{C.CYAN}{I['info']} {msg}{C.RESET}")

def warn(msg):
    print(f"{C.YELLOW}{I['warn']} {msg}{C.RESET}")

def ok(msg):
    print(f"{C.GREEN}{I['check']} {msg}{C.RESET}")

def fail(msg):
    print(f"{C.RED}{I['fail']} {msg}{C.RESET}")

def step(msg):
    print(f"{C.MAGENTA}{I['bolt']} {msg}{C.RESET}")

def kv(label, value):
    print(f"{C.GRAY}{label}:{C.RESET} {value}")

def cmd_preview(cmd_list):
    s = " ".join(shlex.quote(c) for c in cmd_list)
    print(f"{C.GRAY}{I['hammer']} {s}{C.RESET}")

# ---------- Helpers ----------
def run(cmd, check=True, capture=True, sudo=False):
    cmd_list = cmd if isinstance(cmd, list) else shlex.split(cmd)
    if sudo and os.geteuid() != 0:
        cmd_list = ["sudo"] + cmd_list
    try:
        if capture:
            res = subprocess.run(cmd_list, check=check, text=True,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return res.stdout.strip()
        else:
            subprocess.run(cmd_list, check=check)
            return ""
    except subprocess.CalledProcessError as e:
        if capture and e.stderr:
            print(C.GRAY + e.stderr.strip() + C.RESET)
        if check:
            raise
        return ""

def which(cmd):
    return shutil.which(cmd) is not None

def ls_ld(path: Path):
    run(["ls", "-ld", str(path)], check=False, capture=False)

def check_write(path: Path, filename=".ffs_lock_test") -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        testfile = path / filename
        with open(testfile, "w") as f:
            f.write("test\n")
        testfile.unlink(missing_ok=True)
        return True
    except Exception as e:
        fail(f"Kein Schreibzugriff auf {path}: {e}")
        return False

def findmnt(path: Path) -> str:
    return run(["findmnt", str(path)], check=False)

def findmnt_field(path: Path, field: str) -> str:
    out = run(["findmnt", "-no", field, str(path)], check=False)
    return out.strip()

def get_mount_info(path: Path):
    return {
        "TARGET": findmnt_field(path, "TARGET"),
        "SOURCE": findmnt_field(path, "SOURCE"),
        "FSTYPE": findmnt_field(path, "FSTYPE") or "none",
        "OPTIONS": findmnt_field(path, "OPTIONS"),
    }

def ensure_dir(path: Path):
    if not path.exists():
        step(f"Ordner anlegen: {path}")
        run(["sudo", "mkdir", "-p", str(path)], check=True, capture=False)

def remount_rw_if_ro(mp: Path, src: str):
    opts = findmnt_field(mp, "OPTIONS")
    if "ro" in (opts or "").split(","):
        warn(f"{mp} ist read-only – Remount rw versuchen …")
        cmd = ["mount", "-o", "remount,rw", src, str(mp)]
        cmd_preview(["sudo"] + cmd)
        run(cmd, sudo=True, check=False, capture=False)

def remount_exfat_vfat(mp: Path, src: str, uid: int, gid: int):
    # 1) Remount versuchen
    opts = f"remount,uid={uid},gid={gid},umask=022,iocharset=utf8"
    cmd = ["mount", "-o", opts, src, str(mp)]
    cmd_preview(["sudo"] + cmd)
    run(cmd, sudo=True, check=False, capture=False)

    # 2) Prüfen, ob übernommen
    after = findmnt_field(mp, "OPTIONS")
    if after and ("uid=" in after and "gid=" in after):
        ok("Remount hat uid/gid übernommen.")
        return

    warn("Remount hat uid/gid NICHT übernommen – Neu-Mount wird versucht …")

    # 3) Umount (sanft), ggf. lazy als Fallback
    try:
        cmd = ["umount", str(mp)]
        cmd_preview(["sudo"] + cmd)
        run(cmd, sudo=True, check=True, capture=False)
    except Exception:
        warn("Umount blockiert – lazy unmount.")
        cmd = ["umount", "-l", str(mp)]
        cmd_preview(["sudo"] + cmd)
        run(cmd, sudo=True, check=True, capture=False)

    # 4) Frischer Mount mit Optionen
    cmd = ["mount", "-t", "exfat", "-o", f"uid={uid},gid={gid},umask=022,iocharset=utf8", src, str(mp)]
    cmd_preview(["sudo"] + cmd)
    run(cmd, sudo=True, check=False, capture=False)

def remount_ntfs(mp: Path, src: str, uid: int, gid: int):
    # erst remount versuchen …
    opts = f"remount,uid={uid},gid={gid},umask=022,windows_names"
    cmd = ["mount", "-o", opts, src, str(mp)]
    cmd_preview(["sudo"] + cmd)
    ok1 = run(cmd, sudo=True, check=False) == ""
    if not ok1:
        # … dann mit ntfs-3g neu mounten
        warn("Fallback auf ntfs-3g")
        cmd = ["umount", str(mp)]
        cmd_preview(["sudo"] + cmd)
        run(cmd, sudo=True, check=False, capture=False)
        cmd = ["mount", "-t", "ntfs-3g", "-o", f"uid={uid},gid={gid},umask=022", src, str(mp)]
        cmd_preview(["sudo"] + cmd)
        run(cmd, sudo=True, check=False, capture=False)

def chown_posix_root(mp: Path, user: str):
    cmd = ["chown", f"{user}:{user}", str(mp)]
    cmd_preview(["sudo"] + ["chown", f"{user}:{user}", str(mp)])
    run(cmd, sudo=True, check=False, capture=False)
    cmd = ["chmod", "u+rwx", str(mp)]
    cmd_preview(["sudo"] + cmd)
    run(cmd, sudo=True, check=False, capture=False)

# ---------- Core logic ----------
def fix_permissions(mountpoint: Path, user: str, uid: int, gid: int):
    mi = get_mount_info(mountpoint)
    kv("TARGET", mi["TARGET"])
    kv("SOURCE", mi["SOURCE"] or "(none)")
    kv("FSTYPE", mi["FSTYPE"])
    kv("OPTIONS", mi["OPTIONS"] or "")

    if mi["FSTYPE"] == "none":
        fail(f"{mountpoint} ist nicht gemountet. Bitte Datenträger einhängen.")
        return False

    remount_rw_if_ro(mountpoint, mi["SOURCE"])

    if mi["FSTYPE"] in ("ext4", "xfs", "btrfs"):
        info(f"Dateisystem {mi['FSTYPE']} → Besitzrechte am Mountpunkt setzen")
        chown_posix_root(mountpoint, user)

    elif mi["FSTYPE"] in ("exfat", "vfat"):
        info(f"Dateisystem {mi['FSTYPE']} → Remount mit uid/gid")
        if not mi["SOURCE"]:
            fail("Kein SOURCE gefunden – Abbruch.")
            return False
        remount_exfat_vfat(mountpoint, mi["SOURCE"], uid, gid)

    elif mi["FSTYPE"] in ("ntfs", "fuseblk"):
        info(f"Dateisystem {mi['FSTYPE']} → Remount mit NTFS‑Optionen")
        if not mi["SOURCE"]:
            fail("Kein SOURCE gefunden – Abbruch.")
            return False
        remount_ntfs(mountpoint, mi["SOURCE"], uid, gid)

    else:
        warn(f"Unbekanntes FSTYPE: {mi['FSTYPE']} – keine Änderung vorgenommen.")
        return False

    # Status nach Anpassung anzeigen
    print()
    info("Mount‑Status nach Anpassung:")
    print(findmnt(mountpoint))
    return True

def test_targets(targets):
    section("Schreibtest auf Zielen")
    for t in targets:
        print(f"{I['folder']} {C.BOLD}{t}{C.RESET}")
        ls_ld(Path(t))
        mt = findmnt(Path(t))
        if mt:
            print(mt)
        if check_write(Path(t)):
            ok("Schreibtest erfolgreich")
        else:
            fail("Kein Schreibzugriff")

def flatpak_overrides(user_media_root: Path, mountpoint: Path):
    section("Flatpak‑Rechte")
    if not which("flatpak"):
        warn("flatpak nicht gefunden – Schritt übersprungen.")
        return
    cmds = []
    if mountpoint:
        cmds.append(["flatpak", "override", "--user", f"--filesystem={str(mountpoint)}", "org.freefilesync.FreeFileSync"])
    cmds.extend([
        ["flatpak", "override", "--user", f"--filesystem={str(user_media_root)}", "org.freefilesync.FreeFileSync"],
        ["flatpak", "override", "--user", "--filesystem=xdg-run/gvfs", "org.freefilesync.FreeFileSync"],
    ])
    for c in cmds:
        cmd_preview(c)
        run(c, check=False, capture=False)
    ok("Flatpak‑Overrides gesetzt (sofern Flatpak installiert).")

def restart_ffs():
    section("FreeFileSync neu starten")
    if not shutil.which("flatpak"):
        info("Flatpak nicht gefunden – überspringe.")
        return
    # Ist die App installiert?
    rc = subprocess.run(
        ["flatpak", "info", "org.freefilesync.FreeFileSync"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    if rc.returncode != 0:
        info("FreeFileSync (Flatpak) nicht installiert – überspringe.")
        return
    # Falls läuft: leise beenden (keine Fehlermeldung zeigen)
    subprocess.run(
        ["flatpak", "kill", "org.freefilesync.FreeFileSync"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    # Start im Hintergrund
    try:
        subprocess.Popen(
            ["flatpak", "run", "org.freefilesync.FreeFileSync"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        ok("FreeFileSync gestartet.")
    except Exception as e:
        warn(f"Konnte FreeFileSync nicht starten: {e}")

# ---------- CLI ----------
def parse_args():
    p = argparse.ArgumentParser(description="Fix FreeFileSync Berechtigungen mit hübscher Ausgabe")
    p.add_argument("--user", default=DEFAULT_USER, help=f"Zielnutzer (Default: {DEFAULT_USER})")
    p.add_argument("--mount", default=DEFAULT_MOUNTPOINT,
                   help=f"Mountpunkt (Default: {DEFAULT_MOUNTPOINT})")
    p.add_argument("--labels", nargs="*", default=list(DEFAULT_LABELS),
                   help="Label‑Namen unter /run/media/<user>/…")
    return p.parse_args()

def main():
    args = parse_args()
    user = args.user
    uid = int(run(["id", "-u", user]) or 1000)
    gid = int(run(["id", "-g", user]) or 1000)
    configured_mount = (args.mount or "").strip()
    mountpoint = Path(configured_mount) if configured_mount else None
    user_media_root = Path("/run/media") / user
    mountpoint_active = mountpoint
    if mountpoint:
        mi = get_mount_info(mountpoint)
        if mi["FSTYPE"] == "none":
            info(f"{mountpoint} ist nicht gemountet – dedizierter Mount wird übersprungen.")
            mountpoint_active = None
    targets = ([mountpoint_active] if mountpoint_active else []) + [user_media_root / lbl for lbl in args.labels]

    section("Umgebung")
    kv("User", f"{user} (uid={uid}, gid={gid})")
    kv("Mountpunkt (config)", str(mountpoint) if mountpoint else "(leer)")
    kv("Mount genutzt", str(mountpoint_active) if mountpoint_active else "kein dedizierter Mount")
    kv("User‑Mediapfad", str(user_media_root))
    kv("Emoji", "an" if EMOJI else "aus")
    kv("Farben", "an" if COLOR else "aus")

    test_targets(targets)

    section(f"Reparatur {I['hammer']}")
    if mountpoint_active:
        ensure_dir(mountpoint_active)
        fix_permissions(mountpoint_active, user, uid, gid)
    else:
        info("Mount‑Reparatur übersprungen (kein dedizierter Mount aktiv).")

    section(f"Lock‑Test {I['lock']}")
    if mountpoint_active:
        lock = mountpoint_active / "sync.ffs_lock"
        try:
            with open(lock, "w") as f:
                f.write("lock\n")
            ok("Lock‑Datei kann geschrieben werden.")
            lock.unlink(missing_ok=True)
        except Exception as e:
            fail(f"weiterhin kein Schreibzugriff auf {mountpoint_active}: {e}")
    else:
        info("Lock‑Test übersprungen (kein dedizierter Mount aktiv).")

    flatpak_overrides(user_media_root, mountpoint_active)
    restart_ffs()

    section(f"Fertig {I['spark']}")
    print("Wenn Fehlermeldungen bleiben, bitte ausgeben:")
    if mountpoint_active:
        print(f"  findmnt {mountpoint_active}")
        print(f"  ls -ld {mountpoint_active}")
    else:
        print("  findmnt <Mountpunkt>")
        print("  ls -ld <Mountpunkt>")
    print("  sudo dmesg | tail -n 50")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
        warn("Abgebrochen mit Ctrl+C")
