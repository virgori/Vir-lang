#!/usr/bin/env bash
# ═════════════════════════════════════════════════════════════════════
# Vir Language & Toolchain — Official Global Installer
# Pure Native AOT • Zero-Libc • Self-Hosted Full Modular Compiler
# ═════════════════════════════════════════════════════════════════════
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/virgori/Vir-lang/main/install.sh | bash
# ═════════════════════════════════════════════════════════════════════
set -euo pipefail

# ANSI color codes & formatting
BOLD="\033[1m"
GREEN="\033[32m"
BLUE="\033[34m"
YELLOW="\033[33m"
CYAN="\033[36m"
RED="\033[31m"
DIM="\033[2m"
RESET="\033[0m"

REPO_URL="https://github.com/virgori/Vir-lang.git"
DEFAULT_BRANCH="main"
VIR_HOME="${VIR_INSTALL_DIR:-$HOME/.vir}"
VIR_BIN="${VIR_HOME}/bin"

# Visual progress bar helper
# Args: <percent> <step_text>
draw_progress() {
    local pct=$1
    local text=$2
    local width=28
    local filled=$(( pct * width / 100 ))
    local empty=$(( width - filled ))
    
    local bar=""
    for ((i=0; i<filled; i++)); do bar+="█"; done
    for ((i=0; i<empty; i++)); do bar+="░"; done
    
    printf "\r${CYAN}[${bar}]${RESET} ${BOLD}%3d%%${RESET} ${DIM}│${RESET} %s\033[K" "${pct}" "${text}"
}

print_step_done() {
    local text=$1
    local detail=${2:-""}
    if [ -n "${detail}" ]; then
        echo -e "\r  ${GREEN}✓${RESET} ${BOLD}${text}${RESET} ${DIM}(${detail})${RESET}\033[K"
    else
        echo -e "\r  ${GREEN}✓${RESET} ${BOLD}${text}${RESET}\033[K"
    fi
}

echo -e "${CYAN}${BOLD}"
echo "╔══════════════════════════════════════════════════════════╗"
echo "║          VIR LANGUAGE & TOOLCHAIN INSTALLER              ║"
echo "║       Pure Native AOT • Zero-Libc • Self-Hosted          ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${RESET}"

# 1. Platform Detection
draw_progress 10 "Detecting system platform and architecture..."
OS="$(uname -s)"
ARCH="$(uname -m)"
sleep 0.05

if [ "${OS}" != "Darwin" ] && [ "${OS}" != "Linux" ]; then
    echo -e "\n${RED}Error: Unsupported operating system: ${OS}. Vir supports macOS and Linux.${RESET}"
    exit 1
fi
print_step_done "Platform detected" "${OS} ${ARCH}"

# 2. Target Directory Setup
draw_progress 20 "Configuring installation workspace..."
mkdir -p "${VIR_HOME}" "${VIR_BIN}"
sleep 0.05
print_step_done "Workspace configured" "${VIR_HOME}"

# 3. Obtain Source / Binaries
TEMP_SRC=""
if [ -f "stdlib/vir/prelude.vri" ] || [ -f "stdlib/prelude.vri" ]; then
    BUILD_DIR="$(pwd)"
    draw_progress 30 "Using local repository files..."
    sleep 0.05
    print_step_done "Source located" "local workspace"
else
    draw_progress 25 "Fetching latest Vir release from GitHub..."
    if ! command -v git >/dev/null 2>&1; then
        echo -e "\n${RED}Error: 'git' is required to fetch files.${RESET}"
        exit 1
    fi
    TEMP_SRC="$(mktemp -d -t vir_install_XXXXXX)"
    git clone --depth 1 --branch "${DEFAULT_BRANCH}" "${REPO_URL}" "${TEMP_SRC}" > /dev/null 2>&1 || git clone --depth 1 "${REPO_URL}" "${TEMP_SRC}" > /dev/null 2>&1
    BUILD_DIR="${TEMP_SRC}"
    print_step_done "GitHub repository fetched" "virgori/Vir-lang"
fi

# 4. Deploy Toolchain Binaries
# Step 4.0: vir-core Native Execution Engine
draw_progress 35 "Installing Native Core Engine (vir-core)..."
if [ -f "${BUILD_DIR}/bin/vir-core" ]; then
    cp "${BUILD_DIR}/bin/vir-core" "${VIR_BIN}/vir-core"
elif [ -f "${BUILD_DIR}/core/build/vir" ]; then
    cp "${BUILD_DIR}/core/build/vir" "${VIR_BIN}/vir-core"
fi
if [ -f "${VIR_BIN}/vir-core" ]; then
    chmod +x "${VIR_BIN}/vir-core"
    if [ "${OS}" = "Darwin" ]; then codesign -s - -f "${VIR_BIN}/vir-core" >/dev/null 2>&1 || true; fi
    print_step_done "Native Engine (vir-core) installed" "AOT & JIT execution core"
fi

# Step 4.1: virc (Full Self-Hosted Modular Soft Compiler)
draw_progress 45 "Installing Full Soft Compiler (virc)..."
if [ -f "${BUILD_DIR}/bin/virc" ]; then
    cp "${BUILD_DIR}/bin/virc" "${VIR_BIN}/virc"
fi
chmod +x "${VIR_BIN}/virc"
if [ "${OS}" = "Darwin" ]; then codesign -s - -f "${VIR_BIN}/virc" >/dev/null 2>&1 || true; fi
print_step_done "Full Compiler (virc) installed" "HIR/MIR/LIR + 26 Passes + IRC RegAlloc"

# Step 4.2: vir Master CLI
draw_progress 58 "Installing Unified Master CLI (vir)..."
if [ -f "${BUILD_DIR}/bin/vir" ]; then
    cp "${BUILD_DIR}/bin/vir" "${VIR_BIN}/vir"
fi
chmod +x "${VIR_BIN}/vir"
if [ "${OS}" = "Darwin" ]; then codesign -s - -f "${VIR_BIN}/vir" >/dev/null 2>&1 || true; fi
print_step_done "Master CLI (vir) installed" "Toolchain entrypoint"

# Step 4.3: viron Package Manager
draw_progress 70 "Installing Package Manager (viron)..."
if [ -f "${BUILD_DIR}/bin/viron" ]; then
    cp "${BUILD_DIR}/bin/viron" "${VIR_BIN}/viron"
fi
chmod +x "${VIR_BIN}/viron"
if [ "${OS}" = "Darwin" ]; then codesign -s - -f "${VIR_BIN}/viron" >/dev/null 2>&1 || true; fi
print_step_done "Package Manager (viron) installed" "SemVer & DAG resolver"

# Step 4.4: vir-lsp Language Server
draw_progress 82 "Installing Language Server Protocol (vir-lsp)..."
if [ -f "${BUILD_DIR}/bin/vir-lsp" ]; then
    cp "${BUILD_DIR}/bin/vir-lsp" "${VIR_BIN}/vir-lsp"
fi
chmod +x "${VIR_BIN}/vir-lsp"
if [ "${OS}" = "Darwin" ]; then codesign -s - -f "${VIR_BIN}/vir-lsp" >/dev/null 2>&1 || true; fi
print_step_done "Language Server (vir-lsp) installed" "JSON-RPC 2.0 daemon"

# 5. Standard Library Setup (Including Full Self-Hosted Compiler Modules)
draw_progress 90 "Deploying full standard library & compiler modules..."
mkdir -p "${VIR_HOME}/stdlib"
if [ -d "${BUILD_DIR}/stdlib/vir" ]; then
    cp -R "${BUILD_DIR}/stdlib/vir/"* "${VIR_HOME}/stdlib/" 2>/dev/null || true
elif [ -d "${BUILD_DIR}/stdlib" ]; then
    cp -R "${BUILD_DIR}/stdlib/"* "${VIR_HOME}/stdlib/" 2>/dev/null || true
fi

# Ensure stdlib/vir/compiler/ is also in ~/.vir/stdlib/vir/compiler
mkdir -p "${VIR_HOME}/stdlib/vir"
if [ -d "${BUILD_DIR}/stdlib/vir/compiler" ]; then
    mkdir -p "${VIR_HOME}/stdlib/vir/compiler"
    cp -R "${BUILD_DIR}/stdlib/vir/compiler/"* "${VIR_HOME}/stdlib/vir/compiler/" 2>/dev/null || true
fi

MODULE_COUNT="$(find "${VIR_HOME}/stdlib" -maxdepth 2 -type d 2>/dev/null | wc -l | tr -d ' ')"
print_step_done "Standard Library deployed" "${MODULE_COUNT} modules (Full Compiler included)"

# Cleanup temp dir if created
if [ -n "${TEMP_SRC}" ] && [ -d "${TEMP_SRC}" ]; then
    rm -rf "${TEMP_SRC}"
fi

# 6. Shell PATH Configuration
draw_progress 96 "Configuring shell environment..."
DETECTED_RC=""
USER_SHELL="$(basename "${SHELL:-/bin/zsh}")"

if [ "${USER_SHELL}" = "zsh" ]; then
    DETECTED_RC="${HOME}/.zshrc"
elif [ "${USER_SHELL}" = "bash" ]; then
    if [ -f "${HOME}/.bash_profile" ]; then
        DETECTED_RC="${HOME}/.bash_profile"
    else
        DETECTED_RC="${HOME}/.bashrc"
    fi
elif [ "${USER_SHELL}" = "fish" ]; then
    DETECTED_RC="${HOME}/.config/fish/config.fish"
fi

if [ -z "${DETECTED_RC}" ] && [ -f "${HOME}/.zshrc" ]; then
    DETECTED_RC="${HOME}/.zshrc"
fi

EXPORT_LINE="export PATH=\"${VIR_BIN}:\$PATH\""

if [ -n "${DETECTED_RC}" ] && [ -w "${DETECTED_RC}" ]; then
    if grep -q "${VIR_BIN}" "${DETECTED_RC}" 2>/dev/null; then
        print_step_done "Shell PATH verified" "already configured in ${DETECTED_RC}"
    else
        echo "" >> "${DETECTED_RC}" 2>/dev/null || true
        echo "# Vir Programming Language Toolchain" >> "${DETECTED_RC}" 2>/dev/null || true
        echo "${EXPORT_LINE}" >> "${DETECTED_RC}" 2>/dev/null || true
        print_step_done "Shell PATH updated" "${DETECTED_RC}"
    fi
else
    print_step_done "Shell PATH ready" "${VIR_BIN}"
fi

draw_progress 100 "Installation completed!"
echo ""
echo ""

echo -e "${GREEN}${BOLD}🎉 VIR FULL TOOLCHAIN INSTALLED SUCCESSFULLY!${RESET}"
echo "============================================================"
echo -e "To activate the ${CYAN}vir${RESET} and ${CYAN}virc${RESET} commands in your current terminal session, run:"
echo ""
if [ -n "${DETECTED_RC}" ]; then
    echo -e "    ${YELLOW}${BOLD}echo '${EXPORT_LINE}' >> ${DETECTED_RC} && source ${DETECTED_RC}${RESET}"
else
    echo -e "    ${YELLOW}${BOLD}${EXPORT_LINE}${RESET}"
fi
echo ""
echo "============================================================"
echo -e "${BOLD}Installed Full Toolchain Suite:${RESET}"
echo -e "  • ${CYAN}virc --version${RESET}          : Official Vir Soft Full Modular Compiler (26 passes, IRC RegAlloc)"
echo -e "  • ${CYAN}vir --version${RESET}           : Master CLI toolchain router"
echo -e "  • ${CYAN}viron --version${RESET}         : Viron package manager (SemVer & DAG)"
echo -e "  • ${CYAN}vir-lsp --version${RESET}       : Language Server Protocol daemon"
echo "============================================================"
