#!/bin/bash

# 🛠️ Function to check if packages are already installed
check_packages() {
  local packages=("curl" "wget" "net-tools" "at")
  local missing_packages=()

  # 🔍 Check each package
  for pkg in "${packages[@]}"; do
    if ! dpkg -l | grep -q "^ii  $pkg "; then
      missing_packages+=("$pkg")
    fi
  done

  # 🔄 Install missing packages
  sleep 2
  if [ ${#missing_packages[@]} -eq 0 ]; then
    echo "📦 All packages are already installed."
  else
    sleep 2
    echo "📦 Installing missing packages: ${missing_packages[*]}"
    sleep 2
    sudo apt update && sudo apt upgrade -y || {
      echo "❌ Error during system update."
      exit 1
    }
    sudo apt install -y "${missing_packages[@]}" || {
      echo "❌ Error installing packages: ${missing_packages[*]}."
      exit 1
    }
  fi

  # 📋 Dynamic display of package status as ASCII table
  echo -e "\n+----------------------------------------------+"
  echo -e "| | ✅ | ❌ | Package Name    | Status            |"
  echo -e "+------------------------------------------------+"
  for pkg in "${packages[@]}"; do
    local status=$(dpkg -l | grep -q "^ii  $pkg " && echo "| ✅ Installed" || echo "| ❌ Missing")
    printf "| %-25s | %-18s |\n" "$pkg" "$status"
  done
  echo -e "+----------------------------------------------+\n"