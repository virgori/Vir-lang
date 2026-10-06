#!/bin/bash
set -e
cd "$(dirname "$0")/.."

echo "=== Running Vir Tensor Spec v2.0 Negative Tests ==="
FAIL_COUNT=0

run_neg_test() {
    local name="$1"
    local code="$2"
    local expected_pattern="$3"
    local tmp_file="dist/neg_${name}.vri"
    echo "$code" > "$tmp_file"

    local output
    set +e
    output=$(./bin/virc "$tmp_file" 2>&1)
    local rc=$?
    set -e

    if [ "$rc" -eq 0 ]; then
        echo "FAIL [expected error, got exit 0]: $name"
        FAIL_COUNT=$((FAIL_COUNT + 1))
        return
    fi

    if echo "$output" | grep -q "$expected_pattern"; then
        echo "PASS: $name (matched '$expected_pattern')"
    else
        echo "FAIL: $name (exit $rc, but output did not match '$expected_pattern')"
        echo "Output was:"
        echo "$output"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
}

# 1. Parser negative: unexpected comma at start of index a[, 0]
run_neg_test "comma_at_start" \
    "func main() -> int: var a: tensor<int>[2, 2]; var x = a[, 0]; out 0 end." \
    "unexpected ',' at start of index"

# 2. Parser negative: unexpected comma before ] a[0, ]
run_neg_test "trailing_comma" \
    "func main() -> int: var a: tensor<int>[2, 2]; var x = a[0, ]; out 0 end." \
    "unexpected ',' before ']'"

# 3. Parser negative: missing closing bracket
run_neg_test "missing_rbracket" \
    "func main() -> int: var a: tensor<int>[2, 2]; var x = a[0, 1; out 0 end." \
    "expected ']' after index"

# 4. Semantic negative: rank mismatch (rank 2 tensor accessed with 1 index)
run_neg_test "rank_mismatch_1" \
    "func main() -> int: var a: tensor<int>[2, 2]; var x = a[0]; out 0 end." \
    "semantic pass"

# 5. Semantic negative: rank mismatch in assign (rank 2 assigned with 3 indices)
run_neg_test "rank_mismatch_3" \
    "func main() -> int: var a: tensor<int>[2, 2]; a[0, 1, 2] = 5; out 0 end." \
    "semantic pass"

# 6. Semantic negative: non-integer index (string literal)
run_neg_test "non_int_index" \
    "func main() -> int: var a: tensor<int>[2, 2]; var x = a[0, \"bad\"]; out 0 end." \
    "semantic pass"

# 7. Semantic negative: inner dimension mismatch in matmul [2, 3] ** [2, 2] (3 != 2)
run_neg_test "matmul_dim_mismatch" \
    "func main() -> int: var a: tensor<int>[2, 3]; var b: tensor<int>[2, 2]; var c = a ** b; out 0 end." \
    "semantic pass"

echo ""
if [ "$FAIL_COUNT" -eq 0 ]; then
    echo "=== ALL NEGATIVE TESTS PASSED ==="
    exit 0
else
    echo "=== $FAIL_COUNT NEGATIVE TESTS FAILED ==="
    exit 1
fi
