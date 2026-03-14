#!/bin/bash
# update_specs.sh — Download architecture specification metadata from official sources.
#
# Populates data/arch/specs/ with:
#   - Intel Intrinsics Guide XML
#   - uops.info instruction timings JSON
#   - Apple Silicon instruction data (dougallj)
#   - RISC-V opcodes
#   - RISC-V Vector extension spec
#
# Usage:  ./scripts/update_specs.sh
# Requires: curl, git

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
SPEC_DIR="$PROJECT_DIR/data/arch/specs"

mkdir -p "$SPEC_DIR"

echo "=== [1/5] x86_64: Intel Intrinsics Guide ==="
curl -sSL --max-time 120 \
    "https://www.intel.com/content/dam/develop/public/us/en/include/intrinsics-guide/data-latest.xml" \
    -o "$SPEC_DIR/intel_intrinsics.xml"
echo "  → $(wc -c < "$SPEC_DIR/intel_intrinsics.xml") bytes"

echo "=== [2/5] x86_64: uops.info instruction timings ==="
curl -sSL --max-time 120 \
    "https://uops.info/instructions.json" \
    -o "$SPEC_DIR/uops_info.json"
echo "  → $(wc -c < "$SPEC_DIR/uops_info.json") bytes"

echo "=== [3/5] ARM64: Apple Silicon instruction data (dougallj) ==="
if [ -d "$SPEC_DIR/apple-silicon-instructions" ]; then
    git -C "$SPEC_DIR/apple-silicon-instructions" pull --quiet 2>/dev/null || true
    echo "  → updated existing clone"
else
    git clone --depth 1 \
        "https://github.com/dougallj/applesiliconinstructions.git" \
        "$SPEC_DIR/apple-silicon-instructions" 2>/dev/null
    echo "  → cloned"
fi

echo "=== [4/5] RISC-V: Official opcodes ==="
if [ -d "$SPEC_DIR/riscv-opcodes" ]; then
    git -C "$SPEC_DIR/riscv-opcodes" pull --quiet 2>/dev/null || true
    echo "  → updated existing clone"
else
    git clone --depth 1 \
        "https://github.com/riscv/riscv-opcodes.git" \
        "$SPEC_DIR/riscv-opcodes" 2>/dev/null
    echo "  → cloned"
fi

echo "=== [5/5] RISC-V: Vector extension spec ==="
if [ -d "$SPEC_DIR/riscv-v-spec" ]; then
    git -C "$SPEC_DIR/riscv-v-spec" pull --quiet 2>/dev/null || true
    echo "  → updated existing clone"
else
    git clone --depth 1 \
        "https://github.com/riscv/riscv-v-spec.git" \
        "$SPEC_DIR/riscv-v-spec" 2>/dev/null
    echo "  → cloned"
fi

echo ""
echo "✅ All specs updated in $SPEC_DIR"
echo "Contents:"
ls -1 "$SPEC_DIR"
