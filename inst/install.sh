#!/usr/bin/env bash
# install.sh – Installer/Updater für "PythonLinux"
# - Klont/aktualisiert nach /opt/PythonLinux
# - Erstellt venv NUR in Ordnern, die eine venv.txt enthalten (Pakete: eine pro Zeile, # = Kommentar)
# - Erzeugt Wrapper in /usr/local/bin für alle *.py unter bin/** und game/**
# - Wrapper wählen zur Laufzeit automatisch die nächste .venv, sonst System-Python
# - Emoji/Icons für klare, moderne Konsolenausgaben

set -Eeuo pipefail

# -----------------------------
# Feste Defaults (ohne manuelles Anpassen nötig)
# -----------------------------
REPO_URL="${REPO_URL:-https://github.com/kleiveist/PythonLinux.git}"
INSTALL_ROOT="${INSTALL_ROOT:-/opt}"
PROJECT_NAME="${PROJECT_NAME:-PythonLinux}"
PROJECT_DIR="${PROJECT_DIR:-${INSTALL_ROOT}/${PROJECT_NAME}}"
WRAPPER_DIR="${WRAPPER_DIR:-/usr/local/bin}"
WRAPPER_PREFIX="${WRAPPER_PREFIX:-pl-}"          # Präfix für Wrapper
VERIFY="${VERIFY:-1}"                             # 1 => Python-Syntaxprüfung; 0 => aus
PYTHON_SYS_BIN="${PYTHON_SYS_BIN:-/usr/bin/python3}"  # Fallback-Interpreter

# -----------------------------
# Helfer (mit Emojis)
# -----------------------------
msg()  { echo -e "🟢 $*"; }
warn() { echo -e "🟠 $*" >&2; }
err()  { echo -e "🔴 $*" >&2; exit 1; }

require_root() {
  if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
    err "Bitte als root ausführen (z. B. mit sudo)."
  fi
}

apt_install_deps() {
  msg "⚙️  Installiere Systemabhängigkeiten (git, python3-venv, pip)…"
  apt-get update -y
  DEBIAN_FRONTEND=noninteractive apt-get install -y git python3 python3-venv python3-pip findutils
}

clone_or_update_repo() {
  if [[ -d "${PROJECT_DIR}/.git" ]]; then
    msg "📥 Repo existiert – aktualisiere ${PROJECT_DIR}"
    git -C "${PROJECT_DIR}" fetch --all --prune
    if git -C "${PROJECT_DIR}" rev-parse --abbrev-ref --symbolic-full-name @{u} >/dev/null 2>&1; then
      git -C "${PROJECT_DIR}" pull --ff-only || true
    else
      DEFAULT_REF="$(git -C "${PROJECT_DIR}" symbolic-ref -q --short refs/remotes/origin/HEAD || true)"
      [[ -n "${DEFAULT_REF}" ]] && git -C "${PROJECT_DIR}" reset --hard "${DEFAULT_REF}"
    fi
  else
    msg "🧭 Klone nach ${PROJECT_DIR}"
    mkdir -p "${INSTALL_ROOT}"
    git clone "${REPO_URL}" "${PROJECT_DIR}"
  fi
}

# Markiert Repo-Root für Wrapper (damit die Suche nicht über das Repo hinausläuft)
mark_repo_root() {
  : > "${PROJECT_DIR}/.repo-root"
}

# Relativpfad zu PROJECT_DIR (für Meldungen/Namen)
relpath() {
  local target="$1"
  python3 - "$PROJECT_DIR" "$target" <<'PY'
import os,sys
base=os.path.abspath(sys.argv[1])
t=os.path.abspath(sys.argv[2])
print(os.path.relpath(t, base))
PY
}

# Nächste .venv/bin/python ab Startordner aufwärts bis Repo-Root
nearest_venv_python() {
  local start_dir="$1"
  local current="${start_dir}"
  while [[ "${current}" == /* ]]; do
    if [[ -x "${current}/.venv/bin/python" ]]; then
      echo "${current}/.venv/bin/python"
      return 0
    fi
    [[ -f "${current}/.repo-root" ]] && break
    local parent; parent="$(dirname "${current}")"
    [[ "${parent}" == "${current}" ]] && break
    current="${parent}"
  done
  return 1
}

# Nur dann venv, wenn venv.txt existiert
venv_marker_file() {
  local dir="$1"
  [[ -f "${dir}/venv.txt" ]] && echo "${dir}/venv.txt" || true
}

# venv in <dir>/.venv bauen/aktualisieren basierend auf venv.txt
ensure_venv_for_dir() {
  local dir="$1"
  local vfile; vfile="$(venv_marker_file "${dir}")" || true
  [[ -z "${vfile}" ]] && return 0

  local venv_dir="${dir}/.venv"
  if [[ ! -x "${venv_dir}/bin/python" ]]; then
    msg "🐍 Erstelle venv: $(relpath "${venv_dir}")"
    python3 -m venv "${venv_dir}"
  else
    msg "🔁 venv vorhanden: $(relpath "${venv_dir}")"
  fi

  local pip="${venv_dir}/bin/pip"
  "${pip}" install --upgrade pip wheel setuptools >/dev/null

  # Pakete aus venv.txt (Kommentare/Leerzeilen ignorieren)
  mapfile -t pkgs < <(grep -Ev '^\s*(#|$)' "${vfile}" || true)
  if (( ${#pkgs[@]} > 0 )); then
    msg "📦 Installiere Pakete aus venv.txt in $(relpath "${dir}")"
    "${pip}" install "${pkgs[@]}"
  else
    warn "🗒️  venv.txt in $(relpath "${dir}") ist leer – es wird nur eine Basis-venv bereitgestellt."
  fi
}

# Optional: Python-Syntaxprüfung
verify_python() {
  local py="$1"
  "${PYTHON_SYS_BIN}" - <<'PY' "$py"
import py_compile, sys
try:
    py_compile.compile(sys.argv[1], doraise=True)
except Exception as e:
    print(e, file=sys.stderr)
    raise
PY
}

# Wrapper-Namen generieren (Kollisionen vermeiden)
declare -A SEEN_NAMES
make_wrapper_name() {
  local script="$1"
  local base; base="$(basename "${script}" .py)"
  if [[ -z "${SEEN_NAMES[$base]:-}" ]]; then
    SEEN_NAMES[$base]=1
    echo "${WRAPPER_PREFIX}${base}"
    return 0
  fi
  local rel; rel="$(relpath "${script}")"
  rel="${rel%.py}"
  rel="${rel//\//-}"; rel="${rel//_/-}"; rel="${rel// /-}"
  echo "${WRAPPER_PREFIX}${rel}"
}

# Wrapper schreibt sich fest auf das Zielskript und sucht zur Laufzeit die nächste .venv
write_wrapper() {
  local script_abs="$1"
  local wrapper_path="$2"

  install -m 0755 /dev/stdin "${wrapper_path}" <<EOF
#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_PATH="${script_abs}"
PY_SYS="${PYTHON_SYS_BIN}"

# 🔎 Suche nächste .venv/bin/python vom Skriptordner aufwärts
start_dir="\$(dirname "\${SCRIPT_PATH}")"
current="\${start_dir}"
while [[ "\${current}" == /* ]]; do
  if [[ -x "\${current}/.venv/bin/python" ]]; then
    exec "\${current}/.venv/bin/python" "\${SCRIPT_PATH}" "\$@"
  fi
  # Stoppe am Repo-Root (Marker)
  if [[ -f "\${current}/.repo-root" ]]; then
    break
  fi
  parent="\$(dirname "\${current}")"
  [[ "\${parent}" == "\${current}" ]] && break
  current="\${parent}"
done

# ↩️ Fallback: System-Python
exec "\${PY_SYS}" "\${SCRIPT_PATH}" "\$@"
EOF
}

# Python-Skripte einsammeln
collect_scripts() {
  [[ -d "${PROJECT_DIR}/bin"  ]] && find "${PROJECT_DIR}/bin"  -type f -name "*.py" -print0
  [[ -d "${PROJECT_DIR}/game" ]] && find "${PROJECT_DIR}/game" -type f -name "*.py" -print0
  true
}

# Kandidaten-Ordner (die Ordner, in denen .py liegen)
collect_candidate_dirs_for_venv() {
  [[ -d "${PROJECT_DIR}/bin"  ]] && find "${PROJECT_DIR}/bin"  -type f -name "*.py" -printf '%h\0'
  [[ -d "${PROJECT_DIR}/game" ]] && find "${PROJECT_DIR}/game" -type f -name "*.py" -printf '%h\0'
  true
}

# -----------------------------
# Main
# -----------------------------
require_root
apt_install_deps
clone_or_update_repo
mark_repo_root

# Spezifisch: venv.txt für PyPDF anlegen, falls nicht vorhanden
PYPDF_DIR="${PROJECT_DIR}/bin/PyDate/PyPDF"
if [[ -d "${PYPDF_DIR}" && ! -f "${PYPDF_DIR}/venv.txt" ]]; then
  msg "🧩 Erzeuge venv.txt für PyPDF (Erstinstallation)"
  cat > "${PYPDF_DIR}/venv.txt" <<'TXT'
# Pakete für das PyPDF-Modul
pymupdf4llm
PyPDF2
rich
tqdm
TXT
fi

# 1) venvs gem. venv.txt anlegen/aktualisieren
msg "🔧 Prüfe Ordner auf venv.txt und installiere Pakete…"
while IFS= read -r -d '' d; do
  ensure_venv_for_dir "$d"
done < <(collect_candidate_dirs_for_venv)

# 2) Rechte setzen (read-only Code, ausführbare Shells)
msg "🛡️  Setze Dateirechte…"
find "${PROJECT_DIR}" -type f -name "*.py" -exec chmod 0644 {} \; 2>/dev/null || true
find "${PROJECT_DIR}" -type f -name "*.sh" -exec chmod 0755 {} \; 2>/dev/null || true

# 3) Wrapper erzeugen/aktualisieren
msg "🧪 Prüfe Skripte und erzeuge Wrapper in ${WRAPPER_DIR}…"
mkdir -p "${WRAPPER_DIR}"

while IFS= read -r -d '' script; do
  if [[ "${VERIFY}" == "1" ]]; then
    if ! verify_python "${script}"; then
      warn "❗ Syntaxfehler in $(relpath "${script}") – Wrapper wird trotzdem erstellt."
    fi
  fi
  name="$(make_wrapper_name "${script}")"
  wrapper_path="${WRAPPER_DIR}/${name}"
  write_wrapper "${script}" "${wrapper_path}"
  msg "🪄 Wrapper: ${wrapper_path} → $(relpath "${script}")"
done < <(collect_scripts)

# 4) Abschluss
msg "✅ Installation abgeschlossen."
echo "📁 Repo: ${PROJECT_DIR}"
echo "🚀 Wrapper: ${WRAPPER_DIR}/${WRAPPER_PREFIX}*"
echo "ℹ️  Hinweise:"
echo "- Neue .py unter bin/ oder game/ erhalten bei erneutem Lauf automatisch Wrapper."
echo "- Eine venv wird NUR erstellt, wenn im Skriptordner eine venv.txt liegt."
echo "- venv.txt: jeweils eine Paketzeile, optional Kommentare mit #."
echo "- Wrapper wählen automatisch die nächste .venv; Fallback ist ${PYTHON_SYS_BIN}."
