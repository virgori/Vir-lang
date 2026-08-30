#!/bin/bash
# Pure Native Test Runner for Vir (Zero Python, Zero C VM)
set -euo pipefail
cd "$(dirname "$0")/.."

VIRC="${1:-./bin/virc}"
if [ ! -f "$VIRC" ]; then
    echo "Compiler $VIRC not found."
    exit 1
fi

TMP_BIN="/tmp/vir_test_out"
PASS=0
FAIL=0

echo "=== Vir Native Test Suite ==="
echo "Using compiler: $VIRC ($(stat -f%z "$VIRC") bytes)"
echo ""

# Run all bootstrap tests
for t in tests/bootstrap_codegen/cg_*.vri; do
    name=$(basename "$t" .vri)
    test_bin="/tmp/vtest_${name}"
    if ! "$VIRC" "$t" -o "$test_bin" >/dev/null 2>&1; then
        echo "FAIL (compile): ${name}.vri"
        FAIL=$((FAIL+1))
        continue
    fi
    codesign -s - -f "$test_bin" >/dev/null 2>&1 || true
    if "$test_bin" >/dev/null 2>&1; then
        echo "PASS: ${name}.vri"
        PASS=$((PASS+1))
    else
        echo "FAIL (exec): ${name}.vri"
        FAIL=$((FAIL+1))
    fi
    rm -f "$test_bin"
done

echo ""
echo "=============================="
echo "Total: $((PASS+FAIL)) | PASSED: $PASS | FAILED: $FAIL"
echo "=============================="

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
