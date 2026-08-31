#!/bin/bash
# Ownership tests — native compiler only (bin/virc stable or dist/virc-next). NO C-VM.
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=tools/virc_bin.sh
source tools/virc_bin.sh

VIRC_BIN="$(virc_resolve)"
echo "Using: $VIRC_BIN"
echo ""

OK=0
BAD=0
for t in tests/semantic_ownership/test_*.vri; do
    name=$(basename "$t")
    expect_fail=0
    case "$name" in *_fail.vri) expect_fail=1;; esac
    out=$(mktemp)
    if "$VIRC_BIN" "$t" -o /tmp/own_out >/dev/null 2>"$out"; then
        rc=0
    else
        rc=$?
    fi
    if grep -q "compilation aborted" "$out" 2>/dev/null; then
        rc=1
    fi
    rm -f "$out"
    if [ "$expect_fail" -eq 1 ]; then
        if [ "$rc" -ne 0 ]; then
            echo "PASS (reject): $name"
            OK=$((OK + 1))
        else
            echo "FAIL (should reject): $name"
            BAD=$((BAD + 1))
        fi
    else
        if [ "$rc" -eq 0 ]; then
            echo "PASS (compile): $name"
            OK=$((OK + 1))
        else
            echo "FAIL (should compile): $name"
            BAD=$((BAD + 1))
        fi
    fi
done

echo ""
echo "Ownership: $OK/13 correct, $BAD wrong"
[ "$BAD" -eq 0 ]
