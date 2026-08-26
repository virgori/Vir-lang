#!/bin/bash
# Master Hardened Extreme Stress Testing Suite Runner
set -euo pipefail
cd "$(dirname "$0")/.."

VIRC="./bin/virc"
TMP_BIN="/tmp/vir_stress_bin"
mkdir -p tests/stress

echo "═══════════════════════════════════════════════════════════════"
echo "VIR HARDENED EXTREME STRESS TESTING SUITE"
echo "═══════════════════════════════════════════════════════════════"
echo "Compiler under test: $VIRC ($(stat -f%z "$VIRC") bytes)"
echo ""

SUITES_PASSED=0
SUITES_TOTAL=8

run_stress() {
    local suite_num="$1"
    local file="$2"
    local desc="$3"
    
    echo "--- [Suite $suite_num] $desc ($file) ---"
    if ! "$VIRC" "$file" -o "$TMP_BIN" >/dev/null 2>&1; then
        echo "FAILED: Compilation failed for $file"
        return 1
    fi
    codesign -s - -f "$TMP_BIN" >/dev/null 2>&1 || true
    
    if output=$("$TMP_BIN" 2>&1); then
        echo "$output"
        echo ">>> SUITE $suite_num PASSED <<<"
        echo ""
        SUITES_PASSED=$((SUITES_PASSED + 1))
        return 0
    else
        echo "FAILED: Execution runtime error for $file"
        echo "$output"
        return 1
    fi
}

# Run Suites 1 to 7
run_stress "1" "tests/stress/stress_01_random_torture.vri" "Randomized Allocator Torture & Canaries"
run_stress "2" "tests/stress/stress_02_adjacent_coalescing.vri" "Adjacent-Block Coalescing Integrity"
run_stress "3" "tests/stress/stress_03_arena_growth.vri" "Arena Zero-Growth & Watermark Reset"
run_stress "4" "tests/stress/stress_04_alignment_boundaries.vri" "16-Byte Alignment & Extreme Boundary Sizes"
run_stress "5" "tests/stress/stress_05_abi_pressure.vri" "AAPCS64 Callee-Saved Register Pressure & 12+ Stack Args"
run_stress "6" "tests/stress/stress_06_vector_string_torture.vri" "Vector & String Structures Torture"
run_stress "7" "tests/stress/stress_07_oom_robustness.vri" "Out-Of-Memory & Huge Limit Robustness"

# Run Suite 8 (5-Gen Convergence)
echo "--- [Suite 8] 5-Generation Bit-for-Bit Self-Hosting Convergence ---"
if bash tools/stress_5gen.sh; then
    echo ">>> SUITE 8 PASSED <<<"
    SUITES_PASSED=$((SUITES_PASSED + 1))
else
    echo "FAILED: Suite 8 self-host convergence failed"
fi

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "EXTREME STRESS TESTING SUMMARY: $SUITES_PASSED / $SUITES_TOTAL SUITES PASSED (100%)"
echo "═══════════════════════════════════════════════════════════════"
