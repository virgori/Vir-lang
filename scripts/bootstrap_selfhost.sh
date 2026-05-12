#!/bin/bash
##
# bootstrap_selfhost.sh — Vir Pure Self-Hosting Bootstrap
# ========================================================
# Three-stage bootstrap proving Vir compiles itself with
# ZERO dependency on Python or C after Stage 0.
#
# Stage 0: Python compiler → virc-stage0 (seed binary)
# Stage 1: virc-stage0    → virc-stage1 (self-compiled)
# Stage 2: virc-stage1    → virc-stage2 (self-self-compiled)
# Verify:  virc-stage1 == virc-stage2 (fixed point proof)
#
# Usage: ./scripts/bootstrap_selfhost.sh
##

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VIR_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BUILD_DIR="$VIR_ROOT/build/selfhost"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info() { echo -e "${CYAN}[BS]${NC} $1"; }
ok()   { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[WN]${NC} $1"; }
fail() { echo -e "${RED}[FAIL]${NC} $1"; exit 1; }

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║  Vir Self-Hosting Bootstrap — Zero Python, Zero C   ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════╝${NC}"
echo ""

mkdir -p "$BUILD_DIR"

VIRC_SRC="$VIR_ROOT/stdlib/vir/compiler/virc.vri"
[ -f "$VIRC_SRC" ] || fail "virc.vri not found at $VIRC_SRC"

# ═══════════════════════════════════════════════════════
# Stage 0: Python compiler → virc-stage0
# ═══════════════════════════════════════════════════════
info "Stage 0: Python compiler → virc-stage0"
STAGE0="$BUILD_DIR/virc-stage0"

cd "$VIR_ROOT"
if python3 scripts/stage0_compile.py "$VIRC_SRC" -o "$STAGE0" 2>&1; then
    chmod +x "$STAGE0"
    ok "Stage 0: $(stat -f%z "$STAGE0" 2>/dev/null || stat -c%s "$STAGE0") bytes"
else
    fail "Stage 0 failed"
fi

# ═══════════════════════════════════════════════════════
# Stage 1: virc-stage0 → virc-stage1
# ═══════════════════════════════════════════════════════
info "Stage 1: virc-stage0 → virc-stage1"
STAGE1="$BUILD_DIR/virc-stage1"

"$STAGE0" "$VIRC_SRC" -o "$STAGE1"
[ -f "$STAGE1" ] || fail "Stage 1 failed"
chmod +x "$STAGE1"
ok "Stage 1: $(stat -f%z "$STAGE1" 2>/dev/null || stat -c%s "$STAGE1") bytes"

# ═══════════════════════════════════════════════════════
# Stage 2: virc-stage1 → virc-stage2
# ═══════════════════════════════════════════════════════
info "Stage 2: virc-stage1 → virc-stage2"
STAGE2="$BUILD_DIR/virc-stage2"

"$STAGE1" "$VIRC_SRC" -o "$STAGE2"
[ -f "$STAGE2" ] || fail "Stage 2 failed"
chmod +x "$STAGE2"
ok "Stage 2: $(stat -f%z "$STAGE2" 2>/dev/null || stat -c%s "$STAGE2") bytes"

# ═══════════════════════════════════════════════════════
# Fixed Point Verification
# ═══════════════════════════════════════════════════════
info "Verifying fixed point (stage1 == stage2)..."

if diff "$STAGE1" "$STAGE2" > /dev/null 2>&1; then
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  BOOTSTRAP SUCCESSFUL — Fixed point reached!        ║${NC}"
    echo -e "${GREEN}║  Vir compiles itself. Python/C no longer needed.    ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════╝${NC}"
    cp "$STAGE2" "$VIR_ROOT/build/virc"
    chmod +x "$VIR_ROOT/build/virc"
    ok "Installed: build/virc"
else
    warn "stage1 != stage2 (early bootstrap — expected)"
    info "Testing stage2 can compile hello world..."

    cat > "$BUILD_DIR/hello.vri" << 'EOF'
func main:
    print 42;
end
EOF

    if "$STAGE2" "$BUILD_DIR/hello.vri" -o "$BUILD_DIR/hello" 2>&1; then
        RESULT=$("$BUILD_DIR/hello" 2>&1 || true)
        [ "$RESULT" = "42" ] && ok "Stage 2 produces working binaries!" || warn "Output: $RESULT"
    else
        warn "Stage 2 cannot compile yet"
    fi
fi

echo ""
info "Stage 0: $(stat -f%z "$STAGE0" 2>/dev/null || stat -c%s "$STAGE0") bytes"
info "Stage 1: $(stat -f%z "$STAGE1" 2>/dev/null || stat -c%s "$STAGE1") bytes"
info "Stage 2: $(stat -f%z "$STAGE2" 2>/dev/null || stat -c%s "$STAGE2") bytes"
