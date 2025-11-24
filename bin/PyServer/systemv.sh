#!/bin/bash
# ────────────────────────────────────────────────────────────────────────
# systemv.sh – central definition and display of your system variables
# ────────────────────────────────────────────────────────────────────────
# Variables
SERVER_IP="$(hostname -I | awk '{print $1}')"
OS_DESCRIPTION="$(lsb_release -d | awk -F'\t' '{print $2}')"
HOSTNAME_VAR="$(hostname)"
USER_VAR="$(whoami)"
CURRENT_TIME="$(date '+%Y-%m-%d %H:%M:%S')"

# Simple log helper
log_message() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

# Function for structured output
show_system_info() {
  local width=62
  local border
  border=$(printf '%*s' "$width" '' | tr ' ' '-')

  echo "+$border+"
  printf "| %-62s |\n" "SYSTEM INFORMATION"
  echo "+$border+"
  printf "| Operating System: %-44s |\n" "$OS_DESCRIPTION"
  printf "| Hostname:         %-44s |\n" "$HOSTNAME_VAR"
  printf "| User:             %-44s |\n" "$USER_VAR"
  printf "| Current Time:     %-44s |\n" "$CURRENT_TIME"
  echo "+$border+"
}
# Only on direct execution: log and display
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  log_message "🔧 Installation server IP determined: $SERVER_IP"
  show_system_info
fi