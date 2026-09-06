#!/bin/bash
# Build an experimental full compiler using bin/virc (normally the C-VM
# wrapper) or an explicitly supplied VIRC native seed.
# Pre-expands includes offline (Python) so C-VM skips the hot expand loop.
# Output: dist/virc-next (never overwrites bin/virc without explicit --install).
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=tools/virc_bin.sh
source tools/virc_bin.sh

OUT="$VIRC_EXPERIMENTAL"
EXPANDED=dist/virc-expanded.vri
INSTALL=0
if [ "${1:-}" = "--install" ]; then
    INSTALL=1
fi

STABLE="$VIRC_STABLE"
if [ -n "${VIRC:-}" ] && [ -x "${VIRC}" ]; then
    STABLE="$VIRC"
elif [ ! -x "$STABLE" ]; then
    STABLE="$VIRC_BACKUP"
fi
if [ ! -x "$STABLE" ]; then
    echo "ERROR: no stable compiler found."
    echo "Restore: cp dist/virc-stable bin/virc"
    exit 1
fi

echo "=== Promote virc.vri (experimental) ==="
echo "Compiler driver: $STABLE ($(stat -f%z "$STABLE" 2>/dev/null || stat -c%s "$STABLE") bytes)"
echo "Output:          $OUT"
echo ""

mkdir -p dist
rm -f "$OUT"

SRC="stdlib/vir/compiler/virc.vri"
echo "Source:          $SRC ($(stat -f%z "$SRC" 2>/dev/null || stat -c%s "$SRC") bytes, compiler self-expands includes)"
echo ""
echo "Compiling full compiler (progress on; set VIRC_PROMOTE_QUIET=1 to silence)..."
echo "Tip: VIRC_NICE=10 lowers CPU priority; VIRC_PROMOTE_OPTS='-O0' speeds debug builds."

QUIET="${VIRC_PROMOTE_QUIET:-0}"
NICE_LVL="${VIRC_NICE:-5}"
EXTRA_OPTS=()
if [ "$QUIET" = "1" ]; then
    EXTRA_OPTS+=(-q)
fi
if [ -n "${VIRC_PROMOTE_OPTS:-}" ]; then
    # shellcheck disable=SC2206
    EXTRA_OPTS+=($VIRC_PROMOTE_OPTS)
fi

run_compiler() {
    (
        while sleep 60; do
            echo "[promote] still compiling $(date '+%H:%M:%S') — check virc: lines above for current stage"
        done
    ) &
    local watcher=$!
    set +e
    if [ -n "$NICE_LVL" ]; then
        if [ ${#EXTRA_OPTS[@]} -gt 0 ]; then
            nice -n "$NICE_LVL" "$STABLE" "$SRC" -o "$OUT" "${EXTRA_OPTS[@]}"
        else
            nice -n "$NICE_LVL" "$STABLE" "$SRC" -o "$OUT"
        fi
    else
        if [ ${#EXTRA_OPTS[@]} -gt 0 ]; then
            "$STABLE" "$SRC" -o "$OUT" "${EXTRA_OPTS[@]}"
        else
            "$STABLE" "$SRC" -o "$OUT"
        fi
    fi
    local rc=$?
    kill "$watcher" 2>/dev/null || true
    wait "$watcher" 2>/dev/null || true
    set -e
    return "$rc"
}

if run_compiler; then
    :
else
    rc=$?
    echo "FAIL: compile $SRC (rc=$rc)"
    exit 1
fi
if [ ! -f "$OUT" ]; then
    echo "FAIL: no output at $OUT"
    exit 1
fi
virc_sign "$OUT"

echo "Smoke: cg_arith..."
SMOKE=dist/virc_promote_smoke
rm -f "$SMOKE"
if "$OUT" tests/bootstrap_codegen/cg_arith.vri -o "$SMOKE"; then
    :
else
    rc=$?
    echo "FAIL: promoted compiler cannot compile cg_arith (rc=$rc)"
    exit 1
fi
if [ ! -f "$SMOKE" ]; then
    echo "FAIL: promoted compiler exited 0 but produced no smoke output"
    echo "      (the selected native seed likely supports only the thin subset)"
    exit 1
fi
virc_sign "$SMOKE"
RESULT="$("$SMOKE" 2>&1 | tr '\n' ' ')"
if ! echo "$RESULT" | grep -q "30"; then
    echo "FAIL: smoke output='$RESULT' (expected 30)"
    exit 1
fi
echo "Smoke OK: $RESULT"

if [ "$INSTALL" -eq 1 ]; then
    virc_backup_stable
    cp "$OUT" "$VIRC_STABLE"
    virc_sign "$VIRC_STABLE"
    echo "Installed dist/virc-next → bin/virc"
else
    echo ""
    echo "Built $OUT ($(stat -f%z "$OUT" 2>/dev/null || stat -c%s "$OUT") bytes)"
    echo "To install: bash tools/promote_virc.sh --install"
fi
