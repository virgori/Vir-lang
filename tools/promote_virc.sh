#!/bin/bash
# Build experimental full compiler (virc.vri) using STABLE bin/virc only. NO C-VM.
# Output: dist/virc-next (never overwrites bin/virc without explicit --install).
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=tools/virc_bin.sh
source tools/virc_bin.sh

SRC=stdlib/vir/compiler/virc.vri
OUT="$VIRC_EXPERIMENTAL"
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
    echo "ERROR: no stable native compiler found."
    echo "Restore: cp dist/virc-stable bin/virc"
    echo "Or:     curl -fsSL https://raw.githubusercontent.com/virgori/Vir-lang/main/install.sh | bash"
    exit 1
fi

echo "=== Promote virc.vri (experimental) ==="
echo "Stable compiler: $STABLE ($(stat -f%z "$STABLE" 2>/dev/null || stat -c%s "$STABLE") bytes)"
echo "Source:          $SRC"
echo "Output:          $OUT"
echo ""

mkdir -p dist
rm -f "$OUT"

if ! "$STABLE" "$SRC" -o "$OUT"; then
    echo "FAIL: compile $SRC (rc=$?)"
    exit 1
fi
if [ ! -f "$OUT" ]; then
    echo "FAIL: no output at $OUT"
    exit 1
fi
virc_sign "$OUT"

echo "Smoke: cg_arith..."
SMOKE=/tmp/virc_promote_smoke
"$OUT" tests/bootstrap_codegen/cg_arith.vri -o "$SMOKE"
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
