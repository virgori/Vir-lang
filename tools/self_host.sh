#!/bin/bash
# Self-Hosting Lifecycle: Compile Vir using Vir native compiler
set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== Vir Self-Hosting Cycle ==="

CURRENT_COMPILER="./bin/virc"
if [ ! -f "$CURRENT_COMPILER" ]; then
    echo "Current compiler $CURRENT_COMPILER not found. Using dist/virc-stage2..."
    cp dist/virc-stage2 bin/virc
fi

echo "Step 1: Compiling new virc from virc_stage1.vri using current $CURRENT_COMPILER..."
"$CURRENT_COMPILER" virc_stage1.vri -o dist/virc-next

echo "Step 2: Signing newly compiled binary..."
codesign -s - -f dist/virc-next >/dev/null 2>&1 || true
chmod +x dist/virc-next

echo "Step 3: Smoke testing dist/virc-next..."
dist/virc-next tests/bootstrap_codegen/cg_arith.vri -o /tmp/smoke_test
codesign -s - -f /tmp/smoke_test >/dev/null 2>&1 || true
/tmp/smoke_test >/dev/null 2>&1

echo "Step 4: Installing new binary to bin/virc..."
cp dist/virc-next bin/virc
codesign -s - -f bin/virc >/dev/null 2>&1 || true
chmod +x bin/virc

echo "Step 5: Verifying full test suite with new bin/virc..."
bash tools/test_native.sh

echo ""
echo ">>> SELF-HOSTING CYCLE COMPLETE: 100% Native Vir Success! <<<"
