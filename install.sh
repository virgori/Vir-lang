#!/usr/bin/env bash
# ═════════════════════════════════════════════════════════════════════
# Vir Language & Toolchain — Global GitHub Installer
# ═════════════════════════════════════════════════════════════════════
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/virgori/vir/main/install.sh | bash
# ═════════════════════════════════════════════════════════════════════
set -euo pipefail

# ANSI color codes
BOLD="\033[1m"
GREEN="\033[32m"
BLUE="\033[34m"
YELLOW="\033[33m"
CYAN="\033[36m"
RED="\033[31m"
RESET="\033[0m"

REPO_URL="https://github.com/virgori/vir.git"
DEFAULT_BRANCH="main"
VIR_HOME="${VIR_INSTALL_DIR:-$HOME/.vir}"
VIR_BIN="${VIR_HOME}/bin"

echo -e "${CYAN}${BOLD}"
echo "╔══════════════════════════════════════════════════════════╗"
echo "║          VIR LANGUAGE & TOOLCHAIN INSTALLER              ║"
echo "║       Pure Native AOT • Zero-Libc • Self-Hosted          ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${RESET}"

# 1. Detect System Architecture & OS
OS="$(uname -s)"
ARCH="$(uname -m)"
echo -e "${BLUE}==>${RESET} ${BOLD}Detected platform:${RESET} ${OS} (${ARCH})"

if [ "${OS}" != "Darwin" ] && [ "${OS}" != "Linux" ]; then
    echo -e "${RED}Error: Unsupported operating system: ${OS}. Vir currently supports macOS and Linux.${RESET}"
    exit 1
fi

# 2. Setup Installation Directory (~/.vir)
echo -e "${BLUE}==>${RESET} ${BOLD}Target installation directory:${RESET} ${VIR_HOME}"
mkdir -p "${VIR_HOME}" "${VIR_BIN}"

# 3. Obtain Source Code (Clone or update from GitHub if running via curl)
TEMP_SRC=""
if [ -f "stdlib/vir/compiler/virc.vri" ] && [ -f "dist/virc-stage2" ]; then
    # Local execution inside workspace
    BUILD_DIR="$(pwd)"
    echo -e "${BLUE}==>${RESET} ${BOLD}Using local workspace files:${RESET} ${BUILD_DIR}"
else
    # Remote execution (curl | bash)
    echo -e "${BLUE}==>${RESET} ${BOLD}Fetching latest Vir source from GitHub (${REPO_URL})...${RESET}"
    if ! command -v git >/dev/null 2>&1; then
        echo -e "${RED}Error: 'git' is required to clone the repository. Please install git first.${RESET}"
        exit 1
    fi
    TEMP_SRC="$(mktemp -d -t vir_install_XXXXXX)"
    git clone --depth 1 --branch "${DEFAULT_BRANCH}" "${REPO_URL}" "${TEMP_SRC}" > /dev/null 2>&1 || git clone --depth 1 "${REPO_URL}" "${TEMP_SRC}" > /dev/null 2>&1
    BUILD_DIR="${TEMP_SRC}"
fi

# 4. Bootstrap and Build Toolchain Binaries
echo -e "${BLUE}==>${RESET} ${BOLD}Compiling standalone native toolchain...${RESET}"
BOOTSTRAP_COMPILER="${BUILD_DIR}/dist/virc-stage2"

if [ ! -f "${BOOTSTRAP_COMPILER}" ]; then
    if [ -f "${BUILD_DIR}/bin/virc" ]; then
        BOOTSTRAP_COMPILER="${BUILD_DIR}/bin/virc"
    else
        echo -e "${RED}Error: Bootstrap binary not found in ${BOOTSTRAP_COMPILER}.${RESET}"
        exit 1
    fi
fi

# Ensure bootstrap compiler is executable & signed
chmod +x "${BOOTSTRAP_COMPILER}"
if [ "${OS}" = "Darwin" ]; then
    codesign -s - -f "${BOOTSTRAP_COMPILER}" >/dev/null 2>&1 || true
fi

# Build Compiler (bin/virc)
"${BOOTSTRAP_COMPILER}" "${BUILD_DIR}/virc_stage1.vri" -o "${VIR_BIN}/virc"
chmod +x "${VIR_BIN}/virc"
if [ "${OS}" = "Darwin" ]; then codesign -s - -f "${VIR_BIN}/virc" >/dev/null 2>&1 || true; fi
echo -e "  ${GREEN}✓${RESET} virc     (Native Self-Hosted Compiler: $(stat -f%z "${VIR_BIN}/virc" 2>/dev/null || stat -c%s "${VIR_BIN}/virc" 2>/dev/null || echo "ok") bytes)"

# Build Master CLI (bin/vir)
"${VIR_BIN}/virc" "${BUILD_DIR}/apps/vir/main.vri" -o "${VIR_BIN}/vir"
chmod +x "${VIR_BIN}/vir"
if [ "${OS}" = "Darwin" ]; then codesign -s - -f "${VIR_BIN}/vir" >/dev/null 2>&1 || true; fi
echo -e "  ${GREEN}✓${RESET} vir      (Unified Toolchain CLI: $(stat -f%z "${VIR_BIN}/vir" 2>/dev/null || stat -c%s "${VIR_BIN}/vir" 2>/dev/null || echo "ok") bytes)"

# Build Package Manager (bin/viron)
"${VIR_BIN}/virc" "${BUILD_DIR}/apps/viron/main.vri" -o "${VIR_BIN}/viron"
chmod +x "${VIR_BIN}/viron"
if [ "${OS}" = "Darwin" ]; then codesign -s - -f "${VIR_BIN}/viron" >/dev/null 2>&1 || true; fi
echo -e "  ${GREEN}✓${RESET} viron    (Package Manager & Build System)"

# Build Language Server Protocol Daemon (bin/vir-lsp)
"${VIR_BIN}/virc" "${BUILD_DIR}/apps/vir-lsp/main.vri" -o "${VIR_BIN}/vir-lsp"
chmod +x "${VIR_BIN}/vir-lsp"
if [ "${OS}" = "Darwin" ]; then codesign -s - -f "${VIR_BIN}/vir-lsp" >/dev/null 2>&1 || true; fi
echo -e "  ${GREEN}✓${RESET} vir-lsp  (Language Server for VS Code & Antigravity IDE)"

# Copy Standard Library
echo -e "${BLUE}==>${RESET} ${BOLD}Installing standard library to ${VIR_HOME}/stdlib...${RESET}"
mkdir -p "${VIR_HOME}/stdlib"
cp -R "${BUILD_DIR}/stdlib/"* "${VIR_HOME}/stdlib/" 2>/dev/null || true

# Cleanup temp files if created
if [ -n "${TEMP_SRC}" ] && [ -d "${TEMP_SRC}" ]; then
    rm -rf "${TEMP_SRC}"
fi

# 5. Setup Shell PATH Configuration
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

# Try to automatically add to RC file if writable
if [ -n "${DETECTED_RC}" ] && [ -w "${DETECTED_RC}" ]; then
    if grep -q "${VIR_BIN}" "${DETECTED_RC}" 2>/dev/null; then
        echo -e "${BLUE}==>${RESET} ${GREEN}PATH is already configured in ${DETECTED_RC}.${RESET}"
    else
        echo "" >> "${DETECTED_RC}" 2>/dev/null || true
        echo "# Vir Programming Language Toolchain" >> "${DETECTED_RC}" 2>/dev/null || true
        echo "${EXPORT_LINE}" >> "${DETECTED_RC}" 2>/dev/null || true
        echo -e "${BLUE}==>${RESET} ${GREEN}Added ${VIR_BIN} to ${DETECTED_RC}.${RESET}"
    fi
fi

# 6. Verification and Summary
echo ""
echo -e "${GREEN}${BOLD}🎉 CÀI ĐẶT VIR TOOLCHAIN TỪ GITHUB HOÀN TẤT THÀNH CÔNG!${RESET}"
echo "============================================================"
echo -e "Để kích hoạt lệnh ${CYAN}vir${RESET} ngay trong terminal hiện tại, hãy chạy:"
echo ""
if [ -n "${DETECTED_RC}" ]; then
    echo -e "    ${YELLOW}${BOLD}echo '${EXPORT_LINE}' >> ${DETECTED_RC} && source ${DETECTED_RC}${RESET}"
else
    echo -e "    ${YELLOW}${BOLD}${EXPORT_LINE}${RESET}"
fi
echo ""
echo "============================================================"
echo -e "${BOLD}Lệnh khởi đầu nhanh:${RESET}"
echo -e "  • ${CYAN}vir --version${RESET}           : Kiểm tra phiên bản hệ thống"
echo -e "  • ${CYAN}vir new my_app${RESET}          : Tạo dự án Vir mới"
echo -e "  • ${CYAN}cd my_app && vir run${RESET}    : Biên dịch và chạy ứng dụng"
echo -e "  • ${CYAN}vir help${RESET}                : Xem tài liệu các lệnh đầy đủ"
echo "============================================================"
