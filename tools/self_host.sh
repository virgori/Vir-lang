#!/bin/bash
# Self-host cycle: stable bin/virc → compile virc.vri full → dist/virc-next.
# Backs up bin/virc before any install. NO C-VM. NO virc_stage1.vri.
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=tools/virc_bin.sh
source tools/virc_bin.sh

echo "=== Vir Full Compiler Self-Host Cycle ==="

STABLE="$(virc_resolve)"
if [ ! -x "$STABLE" ]; then
    echo "ERROR: no stable compiler. Restore bin/virc or run install.sh"
    exit 1
fi

echo "Step 1: Backup stable bin/virc..."
virc_backup_stable

echo "Step 2: Compile virc.vri full → dist/virc-next (using $STABLE)..."
bash tools/promote_virc.sh

echo "Step 3: Verify bootstrap suite with experimental compiler..."
bash tools/test_native.sh dist/virc-next

echo "Step 4: Install experimental → bin/virc (backed up above)..."
cp dist/virc-next bin/virc
virc_sign bin/virc

echo "Step 5: Fixed-point check (re-compile with new bin)..."
bash tools/promote_virc.sh
NEW_SIZE=$(stat -f%z dist/virc-next 2>/dev/null || stat -c%s dist/virc-next)
OLD_SIZE=$(stat -f%z bin/virc 2>/dev/null || stat -c%s bin/virc)
echo "bin/virc=$OLD_SIZE bytes, dist/virc-next=$NEW_SIZE bytes"

echo ""
echo ">>> SELF-HOST CYCLE COMPLETE <<<"
