#!/bin/bash
# Pure Native Test Runner for Vir (Zero Python, Zero C VM)
set -euo pipefail
cd "$(dirname "$0")/.."

VIRC="./bin/virc"
if [ ! -f "$VIRC" ]; then
    echo "Compiler $VIRC not found. Run: cp dist/virc-stage2 bin/virc"
    exit 1
fi

TMP_BIN="/tmp/vir_test_out"
PASS=0
FAIL=0

echo "=== Vir Native Test Suite ==="
echo "Using compiler: $VIRC ($(stat -f%z "$VIRC") bytes)"
echo ""

# Run all 102 bootstrap tests
for t in tests/bootstrap_codegen/cg_*.vri; do
    name=$(basename "$t")
    if ! "$VIRC" "$t" -o "$TMP_BIN" >/dev/null 2>&1; then
        echo "FAIL (compile): $name"
        FAIL=$((FAIL+1))
        continue
    fi
    codesign -s - -f "$TMP_BIN" >/dev/null 2>&1 || true
    if "$TMP_BIN" >/dev/null 2>&1; then
        echo "PASS: $name"
        PASS=$((PASS+1))
    else
        echo "FAIL (exec): $name"
        FAIL=$((FAIL+1))
    fi
done

echo ""
echo "=============================="
echo "Total: $((PASS+FAIL)) | PASSED: $PASS | FAILED: $FAIL"
echo "=============================="

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
