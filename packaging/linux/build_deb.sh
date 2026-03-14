#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# Vir — Build .deb package (Debian/Ubuntu)
# ═══════════════════════════════════════════════════════════════════
# Usage:
#   ./packaging/linux/build_deb.sh                  # native arch
#   ./packaging/linux/build_deb.sh --arch arm64     # cross-compile
#   ./packaging/linux/build_deb.sh --arch amd64     # x86_64
#
# Requirements: dpkg-deb, python3, make, fakeroot
# ═══════════════════════════════════════════════════════════════════
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VIR_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
VERSION="0.3.0"
REVISION="1"

# ── Parse args ────────────────────────────────────────────
ARCH=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --arch) ARCH="$2"; shift 2 ;;
        --version) VERSION="$2"; shift 2 ;;
        *) echo "Unknown arg: $1"; exit 1 ;;
    esac
done

# ── Detect architecture ──────────────────────────────────
if [[ -z "$ARCH" ]]; then
    case "$(uname -m)" in
        x86_64|amd64) ARCH="amd64" ;;
        aarch64|arm64) ARCH="arm64" ;;
        *) echo "Unsupported arch: $(uname -m)"; exit 1 ;;
    esac
fi

DEB_ARCH="$ARCH"
PKG_NAME="vir-lang_${VERSION}-${REVISION}_${DEB_ARCH}"
BUILD_DIR="${VIR_ROOT}/dist/deb-build/${PKG_NAME}"

echo "═══ Building .deb package: ${PKG_NAME} ═══"
echo "  Arch: ${DEB_ARCH}"
echo "  Version: ${VERSION}"

# ── Build native library ─────────────────────────────────
echo "─── Building native library ───"
cd "${VIR_ROOT}/core"

if [[ "$DEB_ARCH" == "arm64" && "$(uname -m)" != "aarch64" ]]; then
    echo "  Cross-compiling for arm64..."
    export CC=aarch64-linux-gnu-gcc
    export AR=aarch64-linux-gnu-ar
    export UNAME_M=aarch64
fi

make clean && make all

# ── Create package structure ──────────────────────────────
echo "─── Creating package layout ───"
rm -rf "${BUILD_DIR}"
mkdir -p "${BUILD_DIR}/DEBIAN"
mkdir -p "${BUILD_DIR}/usr/local/bin"
mkdir -p "${BUILD_DIR}/usr/local/lib"
mkdir -p "${BUILD_DIR}/usr/local/share/vir/stdlib"
mkdir -p "${BUILD_DIR}/usr/lib/systemd/system"
mkdir -p "${BUILD_DIR}/usr/lib/tmpfiles.d"
mkdir -p "${BUILD_DIR}/etc/vir"
mkdir -p "${BUILD_DIR}/usr/local/lib/python3/dist-packages"

# ── Copy files ────────────────────────────────────────────
# Native libraries
cp "${VIR_ROOT}/core/lib/libvir_core.so" "${BUILD_DIR}/usr/local/lib/" 2>/dev/null || true
cp "${VIR_ROOT}/core/lib/libvir_core.a"  "${BUILD_DIR}/usr/local/lib/" 2>/dev/null || true

# CLI binary
cp "${VIR_ROOT}/core/build/vir" "${BUILD_DIR}/usr/local/bin/vir-native" 2>/dev/null || true

# Python package (keep original module name 'src' for import compatibility)
cp -r "${VIR_ROOT}/src" "${BUILD_DIR}/usr/local/lib/python3/dist-packages/src"
cp -r "${VIR_ROOT}/stdlib" "${BUILD_DIR}/usr/local/lib/python3/dist-packages/stdlib" 2>/dev/null || true

# Stdlib
cp -r "${VIR_ROOT}/stdlib" "${BUILD_DIR}/usr/local/share/vir/stdlib/" 2>/dev/null || true

# Config + systemd
cp "${SCRIPT_DIR}/vir.conf"          "${BUILD_DIR}/etc/vir/"
cp "${SCRIPT_DIR}/vir.service"       "${BUILD_DIR}/usr/lib/systemd/system/"
cp "${SCRIPT_DIR}/vir-tmpfiles.conf" "${BUILD_DIR}/usr/lib/tmpfiles.d/vir.conf"

# ── Create wrapper scripts ────────────────────────────────
cat > "${BUILD_DIR}/usr/local/bin/vir" << 'WRAPPER'
#!/bin/bash
exec python3 -m src.runtime.lifecycle "$@"
WRAPPER
chmod 755 "${BUILD_DIR}/usr/local/bin/vir"

cat > "${BUILD_DIR}/usr/local/bin/viron" << 'WRAPPER'
#!/bin/bash
exec python3 -m src.viron.cli "$@"
WRAPPER
chmod 755 "${BUILD_DIR}/usr/local/bin/viron"

# ── DEBIAN control ────────────────────────────────────────
cat > "${BUILD_DIR}/DEBIAN/control" << EOF
Package: vir-lang
Version: ${VERSION}-${REVISION}
Section: devel
Priority: optional
Architecture: ${DEB_ARCH}
Depends: python3 (>= 3.11), python3-regex, libc6
Recommends: python3-pip
Maintainer: Vir Team <team@vir-lang.dev>
Homepage: https://github.com/vir-lang/vir
Description: Vir Programming Language — Multilingual syntax, JIT, self-patching binary
 Vir is a structured, block-scoped programming language with
 Vietnamese-first syntax and multilingual support (EN, ZH, JA, KO).
 Features include JIT compilation, Q-IR virtual machine,
 SIMD-accelerated native core, and self-patching binary backend.
EOF

# ── DEBIAN scripts ────────────────────────────────────────
cp "${SCRIPT_DIR}/postinstall.sh" "${BUILD_DIR}/DEBIAN/postinst"
chmod 755 "${BUILD_DIR}/DEBIAN/postinst"

cat > "${BUILD_DIR}/DEBIAN/prerm" << 'EOF'
#!/bin/bash
set -e
if command -v systemctl >/dev/null 2>&1; then
    systemctl stop vir.service 2>/dev/null || true
    systemctl disable vir.service 2>/dev/null || true
fi
EOF
chmod 755 "${BUILD_DIR}/DEBIAN/prerm"

cat > "${BUILD_DIR}/DEBIAN/conffiles" << EOF
/etc/vir/vir.conf
EOF

# ── Build .deb ────────────────────────────────────────────
echo "─── Building .deb ───"
cd "${VIR_ROOT}/dist"
fakeroot dpkg-deb --build "deb-build/${PKG_NAME}" "${PKG_NAME}.deb"

echo ""
echo "✓ Package built: dist/${PKG_NAME}.deb"
dpkg-deb --info "${PKG_NAME}.deb"
echo ""
echo "Install with: sudo dpkg -i dist/${PKG_NAME}.deb"
