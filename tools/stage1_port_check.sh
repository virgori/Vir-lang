#!/bin/bash
# Quick gate for stage1 porting: Stage-0 build + argv smoke + fixed-point.
# Usage: tools/stage1_port_check.sh
set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== Stage1 port check ==="
echo "Source: virc_stage1.vri ($(wc -c < virc_stage1.vri) bytes)"
echo ""

echo "[1/4] Stage-0 (C-VM → dist/virc-stage1)"
rm -f dist/virc-stage1
./core/build/vir run virc_boot.vri -- virc_stage1.vri -o dist/virc-stage1 > /tmp/stage1_port_s0.log 2>&1 || true
if ! grep -q "wrote output" /tmp/stage1_port_s0.log; then
  echo "FAIL: Stage-0 did not write output"
  tail -20 /tmp/stage1_port_s0.log
  exit 1
fi
file dist/virc-stage1 | grep -q "Mach-O" || { echo "FAIL: dist/virc-stage1 not Mach-O"; exit 1; }
echo "OK: dist/virc-stage1 ($(stat -f%z dist/virc-stage1) bytes)"

echo ""
echo "[2/4] argv smoke (output must land on -o path, not self)"
cp dist/virc-stage1 /tmp/stage1-argv-smoke
chmod +x /tmp/stage1-argv-smoke
codesign -f -s - -i virc-bootstrap /tmp/stage1-argv-smoke >/dev/null 2>&1
S1_SIZE_BEFORE=$(stat -f%z /tmp/stage1-argv-smoke)
rm -f /tmp/stage1-argv-out
/tmp/stage1-argv-smoke tests/bootstrap_codegen/cg_arith.vri -o /tmp/stage1-argv-out 2>&1 || true
S1_COPY_SIZE=$(stat -f%z /tmp/stage1-argv-smoke)
# Allow ±64 bytes (ad-hoc codesign metadata); large drift = self-overwrite bug
DRIFT=$(( S1_COPY_SIZE > S1_SIZE_BEFORE ? S1_COPY_SIZE - S1_SIZE_BEFORE : S1_SIZE_BEFORE - S1_COPY_SIZE ))
if [ "$DRIFT" -gt 64 ]; then
  echo "FAIL: stage1 binary drift $S1_SIZE_BEFORE → $S1_COPY_SIZE (likely self-overwrite / get_arg bug)"
  exit 2
fi
if [ ! -f /tmp/stage1-argv-out ]; then
  echo "FAIL: no output at /tmp/stage1-argv-out (get_arg likely broken)"
  exit 2
fi
file /tmp/stage1-argv-out | grep -q "Mach-O" || { echo "FAIL: cg_arith output not Mach-O"; exit 2; }
echo "OK: cg_arith → /tmp/stage1-argv-out"

echo ""
echo "[3/4] smoke tests (cg_call + cg_arith)"
codesign -f -s - -i virc-bootstrap dist/virc-stage1 >/dev/null 2>&1
for t in cg_call cg_arith; do
  OUT="/tmp/stage1-smoke-${t}"
  rm -f "$OUT"
  if ! dist/virc-stage1 "tests/bootstrap_codegen/${t}.vri" -o "$OUT" >/dev/null 2>&1; then
    echo "FAIL: compile ${t}.vri"
    exit 3
  fi
  codesign -f -s - "$OUT" >/dev/null 2>&1 || true
  if ! "$OUT" >/dev/null 2>&1; then
    echo "FAIL: exec ${t}.vri"
    exit 3
  fi
  echo "OK: ${t}.vri"
done

echo ""
echo "[4/4] fixed-point self-host"
bash tools/bootstrap_fixed_point.sh

echo ""
echo ">>> STAGE1_PORT_CHECK PASS <<<"
