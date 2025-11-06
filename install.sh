#!/usr/bin/env bash
set -euo pipefail

# Konfiguration (überschreibbar via Umgebungsvariablen)
START_DIR="${START_DIR:-$PWD}"
DEST_BASE="${DEST_BASE:-$HOME/Dokumente/Python}"
WRAPPER_DIR="${WRAPPER_DIR:-/usr/local/bin}"

# Log-Helfer
log() { printf '%s\n' "[INFO] $*"; }
warn() { printf '%s\n' "[WARN] $*" >&2; }
err() { printf '%s\n' "[ERROR] $*" >&2; }

# Vorbedingungen
command -v python3 >/dev/null 2>&1 || { err "python3 nicht gefunden."; exit 1; }

log "Startordner: $START_DIR"
log "Zielbasis:   $DEST_BASE"
log "Wrapper:     $WRAPPER_DIR"

mkdir -p "$DEST_BASE"

# Gemeinsamer find-Prune-Block:
# - Ordner mit speziellen Namen werden ignoriert
# - Ordner, die eine Datei '.name' enthalten, werden komplett gepruned
# - Dateien/Ordner mit '.name' im Namen werden ignoriert
PRUNE_DIRS=( -name ".git" -o -name "__pycache__" -o -name "venv" -o -name ".venv" -o -name "*.*name*" -o -exec test -e "{}/.name" \; )

# 1) Alle .py-Dateien ermitteln (unter Berücksichtigung der Ausschlüsse)
log "Suche nach .py-Dateien ..."
mapfile -t PY_FILES < <(
  find "$START_DIR" \
    -type d \( "${PRUNE_DIRS[@]}" \) -prune -o \
    -type f -name "*.py" ! -name "*.*name*" -print
)

if (( ${#PY_FILES[@]} == 0 )); then
  warn "Keine .py-Dateien gefunden (nach Ausschlüssen)."
else
  log "Gefundene .py-Dateien: ${#PY_FILES[@]}"
fi

# 2) Dateien kopieren (Struktur erhalten)
COPIED=0
for SRC in "${PY_FILES[@]:-}"; do
  REL="${SRC#"$START_DIR"/}"
  DEST="$DEST_BASE/$REL"
  mkdir -p "$(dirname "$DEST")"
  cp -f "$SRC" "$DEST"
  ((COPIED++)) || true
done
log "Kopiert: $COPIED .py-Dateien nach '$DEST_BASE'."

# 3) venv.txt verarbeiten -> .venv pro Ordner
log "Suche nach venv.txt ..."
mapfile -t VENV_TXT < <(
  find "$START_DIR" \
    -type d \( "${PRUNE_DIRS[@]}" \) -prune -o \
    -type f -name "venv.txt" ! -name "*.*name*" -print
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

  mkdir -p "$TGT_DIR"

  if [[ ! -d "$VENV_DIR" ]]; then
    log "Erstelle venv: $VENV_DIR"
    if ! python3 -m venv "$VENV_DIR"; then
      err "Konnte venv nicht erstellen (ggf. python3-venv Paket installieren)."
      continue
    fi
    ((VENVS_CREATED++)) || true
  else
    log "venv existiert bereits: $VENV_DIR"
  fi

  # Pakete aus venv.txt filtern (ohne Leerzeilen/Kommentare)
  TMP_REQ="$(mktemp)"
  grep -vE '^\s*(#|$)' "$VFILE" > "$TMP_REQ" || true

  # pip aktualisieren und ggf. Pakete installieren
  "$VENV_DIR/bin/python" -m pip install --upgrade pip >/dev/null
  if [[ -s "$TMP_REQ" ]]; then
    log "Installiere Pakete aus $(realpath --relative-to="$START_DIR" "$VFILE")"
    "$VENV_DIR/bin/pip" install -r "$TMP_REQ"
  else
    log "Keine Pakete in $(realpath --relative-to="$START_DIR" "$VFILE") – leere venv."
  fi
  rm -f "$TMP_REQ"
done
(( VENVS_CREATED > 0 )) && log "Angelegte venvs: $VENVS_CREATED"

# 4) Wrapper unter /usr/local/bin anlegen
#    - Name = Basisname der .py-Datei (ohne .py)
#    - Wrapper nutzt .venv, falls in Skript-Ordner oder darüber vorhanden
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

  # Installation mit sudo (Rechte setzen)
  if sudo -n true 2>/dev/null || sudo -v; then
    sudo install -m 0755 "$TMP_WRAP" "$WRAP_PATH"
    sudo chown root:root "$WRAP_PATH"
  else
    warn "Keine sudo-Rechte – Wrapper '$NAME' wurde NICHT installiert."
    rm -f "$TMP_WRAP"
    return 1
  fi
  rm -f "$TMP_WRAP"
  log "Wrapper installiert: $WRAP_PATH"
}

log "Erzeuge Wrapper ..."
WRAPPERS=0
# Ziel-.py-Dateien (nicht in .venv/venv/__pycache__)
mapfile -t DEST_PY < <(
  find "$DEST_BASE" \
    -type d \( -name ".venv" -o -name "venv" -o -name "__pycache__" \) -prune -o \
    -type f -name "*.py" -print
)

for FILE in "${DEST_PY[@]:-}"; do
  NAME="$(basename "${FILE%.py}")"
  # Hinweis: Kollisionen (gleicher Name aus verschiedenen Pfaden) sind möglich
  # – entsprechend Spezifikation wird derselbe Name verwendet.
  if ! create_wrapper "$FILE" "$NAME"; then
    warn "Wrapper für '$FILE' konnte nicht erstellt werden."
    continue
  fi
  ((WRAPPERS++)) || true
done
log "Wrapper erstellt: $WRAPPERS"

log "Fertig."
