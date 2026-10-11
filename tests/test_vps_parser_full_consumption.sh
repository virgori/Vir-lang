#!/bin/bash
set -u

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
VIRC_BIN=${VIRC:-"$ROOT_DIR/bin/virc"}
OUT_DIR="$ROOT_DIR/scratch/vps_parser_full_consumption.$$"
PROBE="$OUT_DIR/vps_parser_compile_probe"

cleanup() {
    if [ -d "$OUT_DIR" ]; then
        rm -r -- "$OUT_DIR"
    fi
}
trap cleanup EXIT
mkdir -p "$OUT_DIR"

if ! "$VIRC_BIN" "$ROOT_DIR/tests/strict_v2/vps_parser_compile_probe.vri" \
    --sysroot "$ROOT_DIR" -q -o "$PROBE"; then
    echo "FAIL: compile VPS parser probe" >&2
    exit 1
fi

check_rejected() {
    local pattern=$1
    local output
    output=$("$PROBE" "$pattern" "A" 2>&1)
    local rc=$?
    if [ "$rc" -eq 0 ]; then
        echo "FAIL: malformed VPS pattern was accepted: $pattern" >&2
        return 1
    fi
    case "$output" in
        *"Invalid VPS pattern:"*) ;;
        *)
            echo "FAIL: malformed VPS pattern lacked compile diagnostic: $pattern" >&2
            echo "$output" >&2
            return 1
            ;;
    esac
}

check_match() {
    local pattern=$1
    local text=$2
    local expected=$3
    local actual
    actual=$("$PROBE" "$pattern" "$text") || return 1
    if [ "$actual" != "$expected" ]; then
        echo "FAIL: VPS pattern '$pattern' on '$text' expected $expected, got $actual" >&2
        return 1
    fi
}

check_rejected '@AZ | @0' || exit $?
check_rejected '!2' || exit $?
check_rejected '@AZ!2!3' || exit $?
check_rejected '?' || exit $?
check_rejected '? |' || exit $?
check_rejected '| @AZ | @0' || exit $?

check_match '| @AZ |' 'A' 1 || exit $?
check_match '| @AZ |' 'a' 0 || exit $?
check_match '$|' '|' 1 || exit $?
check_match ':( A | B :)' 'B' 1 || exit $?

echo "PASS: VPS parser rejects unconsumed top-level syntax and preserves valid forms"
