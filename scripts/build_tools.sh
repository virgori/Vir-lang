#!/bin/bash
# Build standalone native CLI tools for Vir Ecosystem (vir, virc, viron & vir-lsp)
set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== Building Vir Native CLI Toolchain ==="

VIRC="./bin/virc"
if [ ! -f "$VIRC" ]; then
    echo "Error: $VIRC not found. Please build the compiler first."
    exit 1
fi

mkdir -p bin

echo "1. Compiling apps/vir/main.vri -> bin/vir..."
"$VIRC" apps/vir/main.vri -o bin/vir
codesign -s - -f bin/vir >/dev/null 2>&1 || true
chmod +x bin/vir
echo "   ✓ bin/vir created ($(stat -f%z bin/vir) bytes)"

echo "2. Compiling apps/viron/main.vri -> bin/viron..."
"$VIRC" apps/viron/main.vri -o bin/viron
codesign -s - -f bin/viron >/dev/null 2>&1 || true
chmod +x bin/viron
echo "   ✓ bin/viron created ($(stat -f%z bin/viron) bytes)"

echo "3. Compiling apps/vir-lsp/main.vri -> bin/vir-lsp..."
"$VIRC" apps/vir-lsp/main.vri -o bin/vir-lsp
codesign -s - -f bin/vir-lsp >/dev/null 2>&1 || true
chmod +x bin/vir-lsp
echo "   ✓ bin/vir-lsp created ($(stat -f%z bin/vir-lsp) bytes)"

echo ""
echo "=== Smoke Testing Native Binaries ==="
./bin/vir --version
echo ""
echo ">>> SUCCESS: All Vir CLI tools compiled to standalone native binaries! <<<"
