#!/bin/bash
set -u

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
VIRC_BIN=${VIRC:-"$ROOT_DIR/bin/virc"}

check_diagnostic() {
    local fixture=$1
    local expected=$2
    local line=$3
    local column=$4
    local classic
    local json
    local rc

    set +e
    classic=$("$VIRC_BIN" "$ROOT_DIR/$fixture" --sysroot "$ROOT_DIR" 2>&1)
    rc=$?
    set -e
    if [ "$rc" -eq 0 ] || ! printf '%s\n' "$classic" | grep -Fq "$expected" \
        || ! printf '%s\n' "$classic" | grep -Eq "Line[[:space:]]*:[[:space:]]*$line" \
        || ! printf '%s\n' "$classic" | grep -Eq "Column[[:space:]]*:[[:space:]]*$column"; then
        echo "FAIL: classic diagnostic contract for $fixture" >&2
        printf '%s\n' "$classic" >&2
        return 1
    fi

    set +e
    json=$("$VIRC_BIN" "$ROOT_DIR/$fixture" --sysroot "$ROOT_DIR" --check --json 2>&1)
    rc=$?
    set -e
    if [ "$rc" -eq 0 ] || ! printf '%s\n' "$json" | grep -Fq "$expected" \
        || ! printf '%s\n' "$json" | grep -Fq "\"start_line\":$line,\"start_column\":$column"; then
        echo "FAIL: JSON diagnostic contract for $fixture" >&2
        printf '%s\n' "$json" >&2
        return 1
    fi
}

set -e
check_diagnostic tests/strict_v2/noncanonical_return_rejected.vri \
    "noncanonical keyword 'return'; use 'out'" 5 5
check_diagnostic tests/strict_v2/noncanonical_while_rejected.vri \
    "noncanonical keyword 'while'; use 'when condition loop'" 5 5
check_diagnostic tests/strict_v2/noncanonical_logical_and_rejected.vri \
    "noncanonical operator '&&'; use '&'" 5 13
check_diagnostic tests/strict_v2/noncanonical_bit_or_rejected.vri \
    "noncanonical operator '|'; use 'or' for bitwise OR" 5 19
check_diagnostic tests/strict_v2/noncanonical_prefix_tilde_rejected.vri \
    "prefix '~' is not bitwise NOT; use 'bnot(expr)'" 5 17
check_diagnostic tests/strict_v2/noncanonical_shift_left_rejected.vri \
    "noncanonical operator '<<'; use 'shl'" 5 19
check_diagnostic tests/strict_v2/noncanonical_shift_left_assign_rejected.vri \
    "noncanonical operator '<<='; use 'x = x shl value'" 6 11
check_diagnostic tests/strict_v2/noncanonical_shift_right_assign_rejected.vri \
    "noncanonical operator '>>='; use 'x = x shr value'" 6 11

"$ROOT_DIR/tools/check_noncanonical_vir_syntax.pl" \
    "$ROOT_DIR/compiler/src" "$ROOT_DIR/compiler/generated" \
    "$ROOT_DIR/stdlib/vir" "$ROOT_DIR/tests" "$ROOT_DIR/tools"

echo "PASS: noncanonical spellings fail in classic/JSON modes and source inventory is clean"
