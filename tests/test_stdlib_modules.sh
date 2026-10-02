#!/bin/bash
# ==============================================================================
# tests/test_stdlib_modules.sh — Automated Standard Library Module Verification
# ==============================================================================
# Verifies that standard library modules parse, typecheck, and reach LIR
# cleanly without frontend syntax, semantic, or ownership errors.
# ==============================================================================

set -e
cd "$(dirname "$0")/.."

VIRC="${VIRC:-./bin/virc}"

if [ ! -x "$VIRC" ]; then
    echo "Error: Compiler executable not found at $VIRC"
    exit 1
fi

echo "=== Verifying Standard Library Modules with $VIRC ==="

MODULES=(
    "stdlib/vir/core/types.vri"
    "stdlib/vir/core/option.vri"
    "stdlib/vir/core/result.vri"
    "stdlib/vir/core/ops.vri"
    "stdlib/vir/mem/buffer.vri"
    "stdlib/vir/str/string.vri"
    "stdlib/vir/str/builder.vri"
    "stdlib/vir/error/error.vri"
    "stdlib/vir/io/stdio.vri"
    "stdlib/vir/math/basic.vri"
)

PASS_COUNT=0
FAIL_COUNT=0
FAILED_MODULES=()

for mod in "${MODULES[@]}"; do
    if [ ! -f "$mod" ]; then
        echo "FAIL [File not found]: $mod"
        FAIL_COUNT=$((FAIL_COUNT + 1))
        FAILED_MODULES+=("$mod")
        continue
    fi

    set +e
    out=$("$VIRC" "$mod" -q 2>&1)
    rc=$?
    set -e

    # Clean compilation to LIR yields 0 if main is present, or "has no main function in LIR"
    if [ "$rc" -eq 0 ] || echo "$out" | grep -q "has no main function in LIR"; then
        echo "PASS: $mod"
        PASS_COUNT=$((PASS_COUNT + 1))
    else
        echo "FAIL: $mod"
        echo "$out" | head -n 25
        FAIL_COUNT=$((FAIL_COUNT + 1))
        FAILED_MODULES+=("$mod")
    fi
done

echo ""
echo "=============================================================================="
echo "Stdlib Verification Summary: $PASS_COUNT passed, $FAIL_COUNT failed"
echo "=============================================================================="

if [ "$FAIL_COUNT" -gt 0 ]; then
    echo "Failed modules:"
    for f in "${FAILED_MODULES[@]}"; do
        echo "  - $f"
    done
    exit 1
fi

echo "All tested standard library modules compiled cleanly!"
exit 0
