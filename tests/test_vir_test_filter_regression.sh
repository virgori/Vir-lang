#!/bin/bash
# ═════════════════════════════════════════════════════════════════════
# test_vir_test_filter_regression.sh — Virgex / VPS Filter Regressions
# ═════════════════════════════════════════════════════════════════════
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

RUNNER="./bin/vir-test"
MANIFEST="tests/memory_contract/manifest.tsv"
FIXTURES="tests/memory_contract"
VIRC="./bin/virc"

if [ ! -x "$RUNNER" ]; then
    echo "Lỗi: $RUNNER không tồn tại hoặc không executable" >&2
    exit 1
fi

echo "=== Running Virgex Filter Regression Tests ==="

# 1. Anchor: '| MEM $- BOR $- @0!3 |' (exactly 28 tests)
echo -n "Test 1: Anchor syntax... "
out=$("$RUNNER" --manifest "$MANIFEST" --fixtures "$FIXTURES" --virc "$VIRC" --filter '| MEM $- BOR $- @0!3 |' 2>&1)
cnt=$(echo "$out" | grep "TOTAL" | tail -n 1 | awk '{print $3}')
if [ "$cnt" -ne 28 ]; then
    echo "FAIL: expected 28 tests, got $cnt"
    echo "$out"
    exit 1
fi
echo "PASS (matched $cnt tests)"

# 2. Alternation: '| MEM $- :( WASM | STRUCT :) $- @0!3 |' (exactly 3 tests)
echo -n "Test 2: Alternation syntax... "
out=$("$RUNNER" --manifest "$MANIFEST" --fixtures "$FIXTURES" --virc "$VIRC" --filter '| MEM $- :( WASM | STRUCT :) $- @0!3 |' 2>&1)
cnt=$(echo "$out" | grep "TOTAL" | tail -n 1 | awk '{print $3}')
if [ "$cnt" -ne 3 ]; then
    echo "FAIL: expected 3 tests, got $cnt"
    echo "$out"
    exit 1
fi
echo "PASS (matched $cnt tests)"

# 3. Group repetition: '| :( MEM $- :)!1 @AZ!3 $- @0!3 |'
echo -n "Test 3: Group repetition syntax... "
out=$("$RUNNER" --manifest "$MANIFEST" --fixtures "$FIXTURES" --virc "$VIRC" --filter '| :( MEM $- :)!1 @AZ!3 $- @0!3 |' 2>&1)
cnt=$(echo "$out" | grep "TOTAL" | tail -n 1 | awk '{print $3}')
if [ "$cnt" -le 0 ]; then
    echo "FAIL: expected >0 tests, got $cnt"
    echo "$out"
    exit 1
fi
echo "PASS (matched $cnt tests)"

# 4. Literal escape: '$-'
echo -n "Test 4: Literal escape syntax... "
out=$("$RUNNER" --manifest "$MANIFEST" --fixtures "$FIXTURES" --virc "$VIRC" --filter 'MEM $- HEAP' 2>&1)
cnt=$(echo "$out" | grep "TOTAL" | tail -n 1 | awk '{print $3}')
if [ "$cnt" -ne 8 ]; then
    echo "FAIL: expected 8 MEM-HEAP tests, got $cnt"
    echo "$out"
    exit 1
fi
echo "PASS (matched $cnt tests)"

# 5. Alphanumeric atoms: '@AZ!3 $- @AZ!3 $- @0!3'
echo -n "Test 5: Alphanumeric atoms (@AZ, @0)... "
out=$("$RUNNER" --manifest "$MANIFEST" --fixtures "$FIXTURES" --virc "$VIRC" --filter '| @AZ!3 $- @AZ!3 $- @0!3 |' 2>&1)
cnt=$(echo "$out" | grep "TOTAL" | tail -n 1 | awk '{print $3}')
if [ "$cnt" -le 0 ]; then
    echo "FAIL: expected >0 tests, got $cnt"
    echo "$out"
    exit 1
fi
echo "PASS (matched $cnt tests)"

# 6. Malformed patterns fail closed (exit code 2)
echo -n "Test 6: Malformed patterns fail closed... "
for bad_pat in ":( unclosed" ":) unmatched" "@unknown_atom" "!2~1" "@90"; do
    set +e
    err_out=$("$RUNNER" --filter "$bad_pat" 2>&1)
    rc=$?
    set -e
    if [ "$rc" -ne 2 ]; then
        echo "FAIL: '$bad_pat' should exit 2, got $rc"
        echo "$err_out"
        exit 1
    fi
    if ! echo "$err_out" | grep -q "invalid Virgex pattern"; then
        echo "FAIL: diagnostic missing 'invalid Virgex pattern' for '$bad_pat'"
        echo "$err_out"
        exit 1
    fi
done

# 7. Missing filter argument fails closed (exit code 2)
set +e
err_missing=$("$RUNNER" --filter 2>&1)
rc_missing=$?
set -e
if [ "$rc_missing" -ne 2 ]; then
    echo "FAIL: missing --filter argument should exit 2, got $rc_missing"
    exit 1
fi

echo "PASS (all 6 malformed patterns rejected with exit code 2)"

echo "=== All Virgex filter regression tests PASSED successfully ==="
