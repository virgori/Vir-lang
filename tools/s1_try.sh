#!/bin/zsh
# Build Stage-1 with Stage-0, then run it on a .vri and report exit code.
# Usage: tools/s1_try.sh [input.vri]
set -e
cd "$(dirname "$0")/.."
IN=${1:-tests/bootstrap_codegen/cg_call.vri}
./core/build/vir run virc_boot.vri -- virc_stage1.vri -o dist/virc-stage1 > /tmp/s1_try_stage0.log 2>&1 || true
rg -q "wrote output" /tmp/s1_try_stage0.log \
  || { echo "STAGE0_BUILD_FAILED"; tail -20 /tmp/s1_try_stage0.log; exit 2; }
file dist/virc-stage1 | rg -q "Mach-O" || { echo "NOT_MACHO"; exit 3; }
codesign -f -s - -i virc-bootstrap dist/virc-stage1 >/dev/null 2>&1
rm -f dist/from_s1
set +e
./dist/virc-stage1 "$IN" -o dist/from_s1 &
S1PID=$!
( sleep 8; kill -9 $S1PID 2>/dev/null ) &
WPID=$!
wait $S1PID
RC=$?
kill $WPID 2>/dev/null
[ $RC -eq 137 ] && echo "S1_TIMEOUT (hang)"
echo "S1_EXIT:$RC"
if [ -f dist/from_s1 ]; then
  chmod +x dist/from_s1
  codesign -f -s - -i virc-bootstrap dist/from_s1 >/dev/null 2>&1
  ./dist/from_s1
  echo "OUT_EXIT:$?"
fi
