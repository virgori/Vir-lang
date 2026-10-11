#!/bin/bash
set -u

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
VIRC_BIN=${VIRC:-"$ROOT_DIR/bin/virc"}
OUT_DIR="$ROOT_DIR/scratch/x86_quantization_contract.$$"

cleanup() {
    if [ -d "$OUT_DIR" ]; then
        rm -r -- "$OUT_DIR"
    fi
}
trap cleanup EXIT
mkdir -p "$OUT_DIR"

run_x86() {
    local binary_name=$1
    if [ "$(uname -s)" = "Linux" ] && [ "$(uname -m)" = "x86_64" ]; then
        "$OUT_DIR/$binary_name"
        return
    fi
    if ! command -v docker >/dev/null 2>&1; then
        echo "BLOCKED: Docker is required to execute linux-x86_64 artifacts on this host" >&2
        return 77
    fi
    docker run --rm --pull=never --platform linux/amd64 \
        -v "$OUT_DIR:/work:ro" alpine:latest "/work/$binary_name"
}

check_fixture() {
    local fixture=$1
    local expected=$2
    local opt
    for opt in 0 1 2 3; do
        local binary_name="$(basename "$fixture" .vri)_o$opt"
        if ! "$VIRC_BIN" "$ROOT_DIR/$fixture" --sysroot "$ROOT_DIR" \
            --target linux-x86_64 "-O$opt" -q -o "$OUT_DIR/$binary_name"; then
            echo "FAIL: compile $fixture -O$opt" >&2
            return 1
        fi
        local actual
        actual=$(run_x86 "$binary_name")
        local run_rc=$?
        if [ "$run_rc" -ne 0 ]; then
            echo "FAIL: execute $fixture -O$opt (exit $run_rc)" >&2
            return 1
        fi
        if [ "$actual" != "$expected" ]; then
            echo "FAIL: stdout $fixture -O$opt" >&2
            printf 'expected:\n%s\nactual:\n%s\n' "$expected" "$actual" >&2
            return 1
        fi
    done
}

check_trap_fixture() {
    local fixture=$1
    local opt
    for opt in 0 1 2 3; do
        local binary_name="$(basename "$fixture" .vri)_o$opt"
        if ! "$VIRC_BIN" "$ROOT_DIR/$fixture" --sysroot "$ROOT_DIR" \
            --target linux-x86_64 "-O$opt" -q -o "$OUT_DIR/$binary_name"; then
            echo "FAIL: compile $fixture -O$opt" >&2
            return 1
        fi
        run_x86 "$binary_name" >/dev/null 2>&1
        local run_rc=$?
        if [ "$run_rc" -ne 133 ]; then
            echo "FAIL: expected native-trap exit 133 for $fixture -O$opt, got $run_rc" >&2
            return 1
        fi
    done
}

check_fixture \
    "tests/strict_v2/test_quantize_f16_input.vri" \
    "PASS: quantize f16 source input and formats" || exit $?
check_fixture \
    "tests/strict_v2/test_quantize_e2e.vri" \
    "PASS: quantize E2E all tests (INT8 + INT4 + negative + scale)" || exit $?
check_fixture \
    "tests/strict_v2/test_quantize_f16_infer.vri" \
    $'3.0\n7.0' || exit $?
check_fixture \
    "tests/strict_v2/test_quantize_all_widths_infer.vri" \
    $'3.0\n7.0\n3.0\n7.0\n3.0\n7.0\n3.0\n7.0' || exit $?
check_fixture \
    "tests/spec_gap_contract/quantize_odd_int4_edge.vri" \
    $'6.0\n15.0' || exit $?
check_fixture \
    "tests/strict_v2/test_quantize_edge_policy.vri" \
    "PASS: quantize edge policy" || exit $?
check_trap_fixture \
    "tests/strict_v2/quantize_nan_integer_trap_e2e.vri" || exit $?
check_trap_fixture \
    "tests/strict_v2/quantize_infinity_integer_trap_e2e.vri" || exit $?

echo "PASS: linux-x86_64 quantization runtime and edge policy O0-O3"
