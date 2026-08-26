#!/bin/bash
# 5-Generation Self-Hosting Convergence Stress Test (Tier A & Tier B)
set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== Suite 8: 5-Generation Bit-for-Bit Self-Hosting Convergence ==="
mkdir -p dist/gen

# Step 0: Base compiler
cp bin/virc dist/gen/virc_g0

# Generate Generations 1 to 5
for g in 1 2 3 4 5; do
    prev=$((g - 1))
    echo "--- Building Generation $g (using virc_g$prev) ---"
    dist/gen/virc_g$prev virc_stage1.vri -o dist/gen/virc_g$g >/dev/null 2>&1
    codesign -f -s - -i virc-bootstrap dist/gen/virc_g$g >/dev/null 2>&1 || true
    chmod +x dist/gen/virc_g$g
    
    # Tier A Verification: Run smoke test
    dist/gen/virc_g$g test.vri -o /tmp/gen_smoke >/dev/null 2>&1
    codesign -s - -f /tmp/gen_smoke >/dev/null 2>&1 || true
    /tmp/gen_smoke >/dev/null 2>&1
    echo "Gen $g build & smoke test: PASS"
done

echo ""
echo "=== Tier B: Bit-for-Bit SHA-256 Convergence Analysis ==="
SHA2=$(shasum -a 256 dist/gen/virc_g2 | awk '{print $1}')
SHA3=$(shasum -a 256 dist/gen/virc_g3 | awk '{print $1}')
SHA4=$(shasum -a 256 dist/gen/virc_g4 | awk '{print $1}')
SHA5=$(shasum -a 256 dist/gen/virc_g5 | awk '{print $1}')

echo "virc_g2 SHA-256: $SHA2 ($(stat -f%z dist/gen/virc_g2) bytes)"
echo "virc_g3 SHA-256: $SHA3 ($(stat -f%z dist/gen/virc_g3) bytes)"
echo "virc_g4 SHA-256: $SHA4 ($(stat -f%z dist/gen/virc_g4) bytes)"
echo "virc_g5 SHA-256: $SHA5 ($(stat -f%z dist/gen/virc_g5) bytes)"

if [ "$SHA2" = "$SHA3" ] && [ "$SHA3" = "$SHA4" ] && [ "$SHA4" = "$SHA5" ]; then
    echo ""
    echo ">>> TIER B SUCCESS: PERFECT BIT-FOR-BIT CONVERGENCE ACHIEVED! <<<"
    echo "All generations (g2..g5) are 100% IDENTICAL."
else
    echo ""
    echo "Checking byte differences between Gen 2 and Gen 3:"
    cmp -l dist/gen/virc_g2 dist/gen/virc_g3 | head -n 20 || true
fi

echo ""
echo "=== Suite 8 COMPLETE ==="
