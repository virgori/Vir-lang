#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# Vir — Build .rpm package (Fedora/RHEL/Rocky/CentOS)
# ═══════════════════════════════════════════════════════════════════
# Usage:
#   ./packaging/linux/build_rpm.sh
#   ./packaging/linux/build_rpm.sh --arch x86_64
#   ./packaging/linux/build_rpm.sh --arch aarch64
#
# Requirements: rpmbuild, make, python3
# ═══════════════════════════════════════════════════════════════════
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VIR_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
VERSION="0.3.0"
ARCH=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --arch) ARCH="$2"; shift 2 ;;
        --version) VERSION="$2"; shift 2 ;;
        *) echo "Unknown arg: $1"; exit 1 ;;
    esac
done

if [[ -z "$ARCH" ]]; then
    ARCH="$(uname -m)"
fi

echo "═══ Building .rpm package: vir-lang-${VERSION} (${ARCH}) ═══"

# ── Setup rpmbuild tree ───────────────────────────────────
RPM_ROOT="${VIR_ROOT}/dist/rpm-build"
rm -rf "${RPM_ROOT}"
mkdir -p "${RPM_ROOT}"/{SOURCES,SPECS,BUILD,RPMS,SRPMS}

# ── Create source tarball ─────────────────────────────────
TARBALL_DIR="vir-lang-${VERSION}"
TARBALL="${RPM_ROOT}/SOURCES/${TARBALL_DIR}.tar.gz"

echo "─── Creating source tarball ───"
cd "${VIR_ROOT}/.."
tar czf "${TARBALL}" \
    --exclude='.git' \
    --exclude='dist' \
    --exclude='build' \
    --exclude='__pycache__' \
    --exclude='*.egg-info' \
    --exclude='.build' \
    --exclude='bench_rust*' \
    --transform="s|^$(basename "${VIR_ROOT}")|${TARBALL_DIR}|" \
    "$(basename "${VIR_ROOT}")"

# ── Copy spec file ────────────────────────────────────────
cp "${SCRIPT_DIR}/vir-lang.spec" "${RPM_ROOT}/SPECS/"

# ── Build RPM ─────────────────────────────────────────────
echo "─── Running rpmbuild ───"
rpmbuild --define "_topdir ${RPM_ROOT}" \
         --target "${ARCH}" \
         -ba "${RPM_ROOT}/SPECS/vir-lang.spec"

# ── Copy results ──────────────────────────────────────────
echo ""
echo "─── RPM packages built ───"
find "${RPM_ROOT}/RPMS" "${RPM_ROOT}/SRPMS" -name "*.rpm" -exec ls -la {} \;
cp "${RPM_ROOT}"/RPMS/*/*.rpm "${VIR_ROOT}/dist/" 2>/dev/null || true
cp "${RPM_ROOT}"/SRPMS/*.rpm  "${VIR_ROOT}/dist/" 2>/dev/null || true

echo ""
echo "✓ RPM build complete"
echo "Install with: sudo rpm -i dist/vir-lang-${VERSION}-*.rpm"
echo "    or:       sudo dnf install dist/vir-lang-${VERSION}-*.rpm"
