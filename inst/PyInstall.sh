#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# PythonLinux – Installer & Workspace
# - Spiegelt .py-Dateien aus START_DIR nach DEST_BASE (Ordnerstruktur bleibt)
# - Legt je Modul eine .venv an und installiert Pakete aus venv.txt
# - Erzeugt ausführbare Wrapper in WRAPPER_DIR
# - Optional: --clear für bereinigte Neuinstallation (bin/ & game/ + markierte Wrapper entfernen)
#
# Usage:
#   ./install.sh [--clear] [--yes|-y] [--dry-run] [--help]
#   START_DIR=/pfad DEST_BASE="$HOME/Apps/Python" WRAPPER_DIR="$HOME/.local/bin" ./install.sh --clear -y
# ==============================================================================

# ------------------------------------------------------------------------------
# Konfiguration (überschreibbar via Umgebungsvariablen)
# ------------------------------------------------------------------------------
START_DIR="${START_DIR:-$PWD}"
# DEST_BASE wird nach Argument-Parsing gesetzt, um sudo/SUDO_USER zu berücksichtigen.
DEST_BASE_ENV="${DEST_BASE:-}"
DEST_BASE="${DEST_BASE_ENV:-$HOME/Dokumente/Python}"
WRAPPER_DIR="${WRAPPER_DIR:-/usr/local/bin}"

# Optionen
CLEAR=0
ASSUME_YES=0
DRY_RUN=0
FORCE_ROOT=0

# ------------------------------------------------------------------------------
# Log-Helfer
# ------------------------------------------------------------------------------
if [[ -z "${PLAIN_LOGS:-}" ]]; then
  ICON_INFO="ℹ️"
  ICON_WARN="⚠️"
  ICON_ERR="❌"
  ICON_SUM="📊"
  ICON_MODE="⚙️"
  ICON_PY="📂"
  ICON_VENV="🐍"
  ICON_WRAP="🧩"
ICON_ROOT="🔒"
else
  ICON_INFO="[INFO]"
  ICON_WARN="[WARN]"
  ICON_ERR="[ERROR]"
  ICON_SUM="[SUM]"
  ICON_MODE="[MODE]"
  ICON_PY="[PY]"
  ICON_VENV="[VENV]"
  ICON_WRAP="[WRAP]"
  ICON_ROOT="[ROOT]"
fi

log()  { printf '%s %s\n' "$ICON_INFO" "$*"; }
warn() { printf '%s %s\n' "$ICON_WARN" "$*" >&2; }
err()  { printf '%s %s\n' "$ICON_ERR" "$*" >&2; }

print_help() {
  cat <<'HLP'
Usage: ./install.sh [--clear] [--yes|-y] [--dry-run] [--help]

--clear     Führt vor der Installation eine bereinigte Neuinstallation aus:
            - Löscht DEST_BASE/bin und DEST_BASE/game (falls vorhanden)
            - Entfernt markierte Wrapper im WRAPPER_DIR
--yes, -y   Bestätigt Rückfragen automatisch (non-interaktiv)
--dry-run   Zeigt nur an, was gelöscht/erstellt würde (keine Änderungen)
--root      Erzwingt Wrapper-Installation via sudo nach /usr/local/bin
--help      Diese Hilfe
HLP
}

# Argumente parsen
while [[ $# -gt 0 ]]; do
  case "$1" in
    --clear) CLEAR=1 ;;
    --yes|-y) ASSUME_YES=1 ;;
    --dry-run) DRY_RUN=1 ;;
    --root) FORCE_ROOT=1 ;;
    --help|-h) print_help; exit 0 ;;
    *) err "Unbekannte Option: $1"; print_help; exit 2 ;;
  esac
  shift
done

if (( FORCE_ROOT )); then
  WRAPPER_DIR="/usr/local/bin"
fi

# Effektives HOME bestimmen (für DEST_BASE-Default)
if (( FORCE_ROOT )); then
  EFFECTIVE_HOME="/root"
elif [[ -n "${SUDO_USER:-}" ]]; then
  # Home des ursprünglichen Users auflösen
  EFFECTIVE_HOME="$(eval echo "~${SUDO_USER}")"
  [[ -z "$EFFECTIVE_HOME" || "$EFFECTIVE_HOME" == "~${SUDO_USER}" ]] && EFFECTIVE_HOME="$HOME"
else
  EFFECTIVE_HOME="$HOME"
fi

# DEST_BASE nur überschreiben, wenn keine explizite Vorgabe
if [[ -z "$DEST_BASE_ENV" ]]; then
  DEST_BASE="$EFFECTIVE_HOME/Dokumente/Python"
fi

# ------------------------------------------------------------------------------
# Vorbedingungen
# ------------------------------------------------------------------------------
command -v python3 >/dev/null 2>&1 || { err "python3 nicht gefunden."; exit 1; }

log "Startordner: $START_DIR"
log "Zielbasis:   $DEST_BASE"
log "Wrapper:     $WRAPPER_DIR"
(( FORCE_ROOT )) && log "$ICON_ROOT Root-Modus aktiv: Wrapper werden mit sudo nach /usr/local/bin installiert."
(( DRY_RUN )) && log "Modus:       --dry-run (keine Änderungen)"

mkdir -p "$DEST_BASE"

# ------------------------------------------------------------------------------
# Gemeinsamer find-Prune-Block:
# - Ordner mit speziellen Namen werden ignoriert
# - Ordner, die eine Datei '.name' enthalten, werden komplett gepruned
# - Dateien/Ordner mit '.name' im Namen werden ignoriert
# ------------------------------------------------------------------------------
# Hinweis: Das Muster '*.name*' filtert Einträge, die '.name' im Namen enthalten.
# Für das "Ordner enthält Datei .name"-Kriterium nutzen wir -exec test -e "{}/.name" \;
PRUNE_DIRS=( -name ".git" -o -name "__pycache__" -o -name "venv" -o -name ".venv" -o -name ".archive" -o -name "*.name*" -o -exec test -e "{}/.name" \; )

# ------------------------------------------------------------------------------
# Hilfe-Funktionen für Clear
# ------------------------------------------------------------------------------
confirm() {
  local msg="$1"
  if (( ASSUME_YES )); then return 0; fi
  read -r -p "$msg [y/N] " ans
  [[ "$ans" == "y" || "$ans" == "Y" ]]
}

safe_rm_path() {
  local p="$1"
  [[ -z "$p" ]] && { err "Interner Fehler: leerer Pfad in safe_rm_path"; return 1; }
  case "$p" in
    "/"|"/root"|"$HOME") err "Abbruch: Schutzgeländer verhindern Löschen von '$p'."; return 1 ;;
  esac
  if [[ -e "$p" ]]; then
    if (( DRY_RUN )); then
      log "[dry-run] rm -rf -- $p"
    else
      rm -rf -- "$p"
      log "Gelöscht: $p"
    fi
  fi
}

safe_rm_file() {
  local f="$1"
  [[ -z "$f" ]] && return 0
  if [[ -e "$f" ]]; then
    if (( DRY_RUN )); then
      log "[dry-run] rm -f -- $f"
    else
      rm -f -- "$f"
      log "Entfernt: $f"
    fi
  fi
}

# Marker für Wrapper (nur markierte Wrapper werden beim Clear gelöscht)
WRAP_MARKER="# Managed by PythonLinux install.sh"

clear_install() {
  log "Starte bereinigte Neuinstallation (--clear)."

  # 1) Ziel-Unterbäume in DEST_BASE bereinigen (scoped, nicht DEST_BASE komplett!)
  local remove_paths=()
  [[ -d "$DEST_BASE/bin"  ]] && remove_paths+=( "$DEST_BASE/bin" )
  [[ -d "$DEST_BASE/game" ]] && remove_paths+=( "$DEST_BASE/game" )

  if (( ${#remove_paths[@]} )); then
    log "Zum Löschen vorgemerkt (DEST_BASE):"
    printf '  %s\n' "${remove_paths[@]}"
    if confirm "Diese Pfade löschen?"; then
      for p in "${remove_paths[@]}"; do safe_rm_path "$p"; done
    else
      warn "Löschen der Ziel-Unterbäume abgebrochen."
    fi
  else
    log "Keine bin/ oder game/ in DEST_BASE vorhanden – nichts zu löschen."
  fi

  # 2) Markierte Wrapper im WRAPPER_DIR entfernen
  if [[ -d "$WRAPPER_DIR" ]]; then
    log "Prüfe Wrapper in '$WRAPPER_DIR' (nur markierte werden gelöscht)..."
    # nur normale Dateien im Top-Level des WRAPPER_DIR betrachten
    while IFS= read -r -d '' f; do
      # nur ausführen, wenn Marker enthalten
      if grep -qF "$WRAP_MARKER" "$f" 2>/dev/null; then
        if confirm "Wrapper entfernen: $f?"; then
          safe_rm_file "$f"
        else
          warn "Übersprungen: $f"
        fi
      fi
    done < <(find "$WRAPPER_DIR" -maxdepth 1 -type f -perm -u+x -print0 2>/dev/null || true)
  else
    log "WRAPPER_DIR existiert (noch) nicht – keine Wrapper zu löschen."
  fi
}

# ------------------------------------------------------------------------------
# Optional: Vor dem Hauptlauf aufräumen
# ------------------------------------------------------------------------------
if (( CLEAR )); then
  clear_install
fi

# ------------------------------------------------------------------------------
# 1) Alle .py-Dateien ermitteln (unter Berücksichtigung der Ausschlüsse)
# ------------------------------------------------------------------------------
log "Suche nach .py-Dateien ..."
mapfile -t PY_FILES < <(
  find "$START_DIR" \
    -type d \( "${PRUNE_DIRS[@]}" \) -prune -o \
    -type f -name "*.py" ! -name "*.name*" -print
)

if (( ${#PY_FILES[@]} == 0 )); then
  warn "Keine .py-Dateien gefunden (nach Ausschlüssen)."
else
  log "Gefundene .py-Dateien: ${#PY_FILES[@]}"
fi

# ------------------------------------------------------------------------------
# 2) Dateien kopieren (Struktur erhalten)
# ------------------------------------------------------------------------------
COPIED=0
for SRC in "${PY_FILES[@]:-}"; do
  REL="${SRC#"$START_DIR"/}"
  DEST="$DEST_BASE/$REL"
  if (( DRY_RUN )); then
    log "[dry-run] mkdir -p -- $(dirname "$DEST")"
    log "[dry-run] cp -f -- $SRC $DEST"
  else
    mkdir -p "$(dirname "$DEST")"
    cp -f "$SRC" "$DEST"
  fi
  ((COPIED++)) || true
done
log "Kopiert: $COPIED .py-Dateien nach '$DEST_BASE'."

# ------------------------------------------------------------------------------
# 3) venv.txt verarbeiten -> .venv pro Ordner
# ------------------------------------------------------------------------------
log "Suche nach venv.txt ..."
mapfile -t VENV_TXT < <(
  find "$START_DIR" \
    -type d \( "${PRUNE_DIRS[@]}" \) -prune -o \
    -type f -name "venv.txt" ! -name "*.name*" -print
)

if (( ${#VENV_TXT[@]} > 0 )); then
  log "Gefundene venv.txt-Dateien: ${#VENV_TXT[@]}"
else
  log "Keine venv.txt gefunden. Überspringe venv-Erstellung."
fi

VENVS_CREATED=0
for VFILE in "${VENV_TXT[@]:-}"; do
  SRC_DIR="$(dirname "$VFILE")"
  REL_DIR="${SRC_DIR#"$START_DIR"/}"
  TGT_DIR="$DEST_BASE/$REL_DIR"
  VENV_DIR="$TGT_DIR/.venv"

  if (( DRY_RUN )); then
    log "[dry-run] mkdir -p -- $TGT_DIR"
  else
    mkdir -p "$TGT_DIR"
  fi

  if [[ ! -d "$VENV_DIR" ]]; then
    log "Erstelle venv: $VENV_DIR"
    if (( DRY_RUN )); then
      log "[dry-run] python3 -m venv \"$VENV_DIR\""
    else
      if ! python3 -m venv "$VENV_DIR"; then
        err "Konnte venv nicht erstellen (ggf. python3-venv Paket installieren)."
        continue
      fi
    fi
    ((VENVS_CREATED++)) || true
  else
    log "venv existiert bereits: $VENV_DIR"
  fi

  # Pakete aus venv.txt filtern (ohne Leerzeilen/Kommentare)
  TMP_REQ="$(mktemp)"
  grep -vE '^\s*(#|$)' "$VFILE" > "$TMP_REQ" || true

  # pip aktualisieren und ggf. Pakete installieren
  if (( DRY_RUN )); then
    log "[dry-run] \"$VENV_DIR/bin/python\" -m pip install --upgrade pip"
    if [[ -s "$TMP_REQ" ]]; then
      log "[dry-run] \"$VENV_DIR/bin/pip\" install -r \"$TMP_REQ\""
    else
      log "Keine Pakete in $(command -v realpath >/dev/null 2>&1 && realpath --relative-to="$START_DIR" "$VFILE" || echo "$VFILE") – leere venv."
    fi
  else
    "$VENV_DIR/bin/python" -m pip install --upgrade pip >/dev/null
    if [[ -s "$TMP_REQ" ]]; then
      log "Installiere Pakete aus $(command -v realpath >/dev/null 2>&1 && realpath --relative-to="$START_DIR" "$VFILE" || echo "$VFILE")"
      "$VENV_DIR/bin/pip" install -r "$TMP_REQ"
    else
      log "Keine Pakete in $(command -v realpath >/dev/null 2>&1 && realpath --relative-to="$START_DIR" "$VFILE" || echo "$VFILE") – leere venv."
    fi
  fi
  rm -f "$TMP_REQ"
done
(( VENVS_CREATED > 0 )) && log "Angelegte venvs: $VENVS_CREATED"

# ------------------------------------------------------------------------------
# 4) Wrapper anlegen
#    - Name = Basisname der .py-Datei (ohne .py)
#    - Wrapper nutzt .venv, falls in Skript-Ordner oder darüber vorhanden
#    - Marker-Zeile WRAP_MARKER zur sicheren Identifikation
# ------------------------------------------------------------------------------
create_wrapper() {
  local SCRIPT_ABS="$1"
  local NAME="$2"
  local WRAP_PATH="$WRAPPER_DIR/$NAME"

  # Inhalt mit robuster venv-Suche nach oben
  local TMP_WRAP
  TMP_WRAP="$(mktemp)"
  {
    echo '#!/usr/bin/env bash'
    echo 'set -euo pipefail'
    echo "$WRAP_MARKER"
    # robustes Escaping des Skriptpfads:
    printf 'SCRIPT_PATH=%q\n' "$SCRIPT_ABS"
    cat <<'EOS'
dir="$(dirname "$SCRIPT_PATH")"
py="python3"
while [[ "$dir" != "/" ]]; do
  if [[ -x "$dir/.venv/bin/python" ]]; then
    py="$dir/.venv/bin/python"
    break
  fi
  dir="$(dirname "$dir")"
done
exec "$py" "$SCRIPT_PATH" "$@"
EOS
  } > "$TMP_WRAP"

  # Installation: bevorzugt ohne sudo, wenn WRAPPER_DIR schreibbar ist
  if (( DRY_RUN )); then
    log "[dry-run] install -m 0755 \"$TMP_WRAP\" \"$WRAP_PATH\""
  else
    # Sicherstellen, dass das Zielverzeichnis existiert (falls Benutzerpfad)
    if [[ ! -d "$WRAPPER_DIR" ]]; then
      if mkdir -p "$WRAPPER_DIR" 2>/dev/null; then
        :
      else
        warn "Konnte '$WRAPPER_DIR' nicht anlegen (ohne sudo)."
      fi
    fi

    if [[ -w "$WRAPPER_DIR" && ! $FORCE_ROOT -eq 1 ]]; then
      install -m 0755 "$TMP_WRAP" "$WRAP_PATH"
    else
      # Falls nicht schreibbar: sudo versuchen (mit/ohne TTY)
      if sudo -n true 2>/dev/null || sudo -v; then
        sudo install -m 0755 "$TMP_WRAP" "$WRAP_PATH"
        sudo chown root:root "$WRAP_PATH" || true
      else
        warn "Keine Schreibrechte für '$WRAPPER_DIR' und keine sudo-Rechte – Wrapper '$NAME' wurde NICHT installiert."
        rm -f "$TMP_WRAP"
        return 1
      fi
    fi
  fi

  rm -f "$TMP_WRAP"
  log "Wrapper installiert: $WRAP_PATH"
}

write_wrapper_log() {
  local LOG_DIR="$DEST_BASE/.log"
  local LOG_FILE="$LOG_DIR/logs.txt"

  if (( DRY_RUN )); then
    log "[dry-run] Würde Wrapper-Protokoll schreiben nach $LOG_FILE"
    return
  fi

  if (( ${#WRAPPER_LINES[@]} == 0 )); then
    log "Keine Wrapper zum Protokollieren."
    return
  fi

  if ! mkdir -p "$LOG_DIR" 2>/dev/null; then
    warn "Kann Protokollordner nicht anlegen: $LOG_DIR"
    return
  fi

  {
    echo "Wrapper-Protokoll"
    echo "Zielbasis: $DEST_BASE"
    echo "Wrapper-Verzeichnis: $WRAPPER_DIR"
    echo
    printf '%s\n' "${WRAPPER_LINES[@]}"
  } >"$LOG_FILE" || { warn "Konnte Wrapper-Protokoll nicht schreiben: $LOG_FILE"; return; }

  log "Wrapper-Protokoll geschrieben: $LOG_FILE"
}

log "Erzeuge Wrapper ..."
WRAPPERS=0
WRAPPER_LINES=()
# Ziel-.py-Dateien (nicht in .venv/venv/__pycache__)
mapfile -t DEST_PY < <(
  find "$DEST_BASE" \
    -type d \( -name ".venv" -o -name "venv" -o -name "__pycache__" \) -prune -o \
    -type f -name "*.py" -print
)

for FILE in "${DEST_PY[@]:-}"; do
  NAME="$(basename "${FILE%.py}")"
  # Hinweis: Kollisionen (gleicher Name aus verschiedenen Pfaden) sind möglich
  if create_wrapper "$FILE" "$NAME"; then
    ((WRAPPERS++)) || true
    REL="${FILE#"$DEST_BASE"/}"
    [[ "$REL" == "$FILE" ]] && REL="$FILE"
    WRAPPER_LINES+=( "$NAME -> $REL" )
  else
    warn "Wrapper für '$FILE' konnte nicht erstellt werden."
  fi
done
log "Wrapper erstellt: $WRAPPERS"
write_wrapper_log

COPIED_COUNT="${COPIED:-0}"
VENVS_COUNT="${VENVS_CREATED:-0}"
log "Fertig."
printf '%s Übersicht:\n' "$ICON_SUM"
printf '  %s Modus: %s\n' "$ICON_MODE" "$([ "$DRY_RUN" -eq 1 ] && echo "Dry-Run (keine Änderungen)" || echo "Ausgeführt")"
printf '  %s .py-Dateien kopiert: %s\n' "$ICON_PY" "$COPIED_COUNT"
printf '  %s Neue venvs: %s\n' "$ICON_VENV" "$VENVS_COUNT"
printf '  %s Wrapper erstellt: %s\n' "$ICON_WRAP" "$WRAPPERS"
