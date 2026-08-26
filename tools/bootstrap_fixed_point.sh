#!/bin/zsh
# Prove thin Stage-1 self-host fixed-point: unsigned stage2 == stage3,
# and signed with a fixed codesign Identifier also match.
# Usage: tools/bootstrap_fixed_point.sh
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p dist

IDENT=virc-bootstrap
S1=dist/virc-stage1
S2U=dist/virc-stage2.unsigned
S3U=dist/virc-stage3.unsigned
S2=dist/virc-stage2
S3=dist/virc-stage3

echo "[fp] Stage-0 → $S1"
./core/build/vir run virc_boot.vri -- virc_stage1.vri -o "$S1" > /tmp/fp_stage0.log 2>&1 || true
if ! grep -q "wrote output" /tmp/fp_stage0.log; then
  echo "STAGE0_BUILD_FAILED"
  tail -40 /tmp/fp_stage0.log
  exit 2
fi
file "$S1" | grep -q "Mach-O" || { echo "NOT_MACHO"; exit 3; }
codesign -f -s - -i "$IDENT" "$S1" >/dev/null

echo "[fp] Stage-1 → $S2U"
rm -f "$S2U" "$S3U" "$S2" "$S3"
./"$S1" virc_stage1.vri -o "$S2U"
file "$S2U" | grep -q "Mach-O" || { echo "STAGE2_NOT_MACHO"; exit 4; }

# Sign a working copy so we can run it (ad-hoc requires signature on Apple Silicon).
cp "$S2U" "$S2"
chmod +x "$S2"
codesign -f -s - -i "$IDENT" "$S2" >/dev/null

echo "[fp] Stage-2 → $S3U"
./"$S2" virc_stage1.vri -o "$S3U"
file "$S3U" | grep -q "Mach-O" || { echo "STAGE3_NOT_MACHO"; exit 5; }

echo "[fp] cmp unsigned"
if ! cmp -s "$S2U" "$S3U"; then
  echo "FIXED_POINT_FAIL: unsigned stage2 != stage3"
  cmp -l "$S2U" "$S3U" | head -20
  exit 6
fi
echo "[fp] unsigned OK ($(stat -f%z "$S2U") bytes)"

cp "$S3U" "$S3"
chmod +x "$S3"
codesign -f -s - -i "$IDENT" "$S2" >/dev/null
codesign -f -s - -i "$IDENT" "$S3" >/dev/null

echo "[fp] cmp signed (Identifier=$IDENT)"
if ! cmp -s "$S2" "$S3"; then
  echo "FIXED_POINT_FAIL: signed stage2 != stage3 (check codesign -i)"
  cmp -l "$S2" "$S3" | head -20
  exit 7
fi
echo "[fp] signed OK"
echo "FIXED_POINT_PASS"
