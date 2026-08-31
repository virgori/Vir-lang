#!/bin/bash
# Audit include/module resolution for virc.vri (filesystem check, no C-VM).
set -euo pipefail
cd "$(dirname "$0")/.."

ROOT="$(pwd)"
SRC="$ROOT/stdlib/vir/compiler/virc.vri"
FAIL=0
OK=0

resolve_include() {
    local name="$1"
    local rel path

    # Dotted module → slash path (bash 3.2 safe)
    if [[ "$name" == *.* && "$name" != *.vri ]]; then
        rel="$(echo "$name" | tr '.' '/').vri"
    else
        rel="${name%.vri}.vri"
        if [[ "$name" == *.vri ]]; then rel="$name"; fi
    fi

    # vir/... under stdlib/vir
    if [[ "$rel" == vir/* ]]; then
        path="$ROOT/stdlib/${rel}"
        if [ -f "$path" ]; then echo "$path"; return 0; fi
    fi

    # stdlib search prefixes (mirror read_include_source)
    for prefix in \
        stdlib/vir/compiler \
        stdlib/vir/rt \
        stdlib/vir/collections \
        stdlib/vir/mem \
        stdlib/vir/str \
        stdlib/vir/io \
        stdlib/vir/error \
        stdlib/vir/core \
        stdlib/vir; do
        if [ -f "$ROOT/$prefix/$rel" ]; then
            echo "$ROOT/$prefix/$rel"
            return 0
        fi
    done

    if [ -f "$ROOT/$rel" ]; then
        echo "$ROOT/$rel"
        return 0
    fi
    return 1
}

echo "=== Include audit: $SRC ==="
echo ""

while IFS= read -r name; do
    [ -z "$name" ] && continue
    if path=$(resolve_include "$name"); then
        echo "OK   include $name"
        echo "     → ${path#$ROOT/}"
        OK=$((OK + 1))
    else
        echo "FAIL include $name"
        FAIL=$((FAIL + 1))
    fi
done < <(grep '^include ' "$SRC" | awk '{print $2}')

echo ""
echo "Direct includes: $OK ok, $FAIL fail"

# Transitive: scan compiler modules for more includes (depth 1)
echo ""
echo "=== Transitive includes (compiler/*.vri, depth 1) ==="
T_FAIL=0
T_OK=0
for f in stdlib/vir/compiler/*.vri; do
    while IFS= read -r name; do
        [ -z "$name" ] && continue
        if path=$(resolve_include "$name"); then
            T_OK=$((T_OK + 1))
        else
            echo "FAIL $(basename "$f"): include $name"
            T_FAIL=$((T_FAIL + 1))
        fi
    done < <(grep '^include ' "$f" 2>/dev/null | awk '{print $2}' || true)
done
echo "Transitive: $T_OK ok, $T_FAIL fail"
echo ""
[ "$FAIL" -eq 0 ] && [ "$T_FAIL" -eq 0 ]
