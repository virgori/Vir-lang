#!/bin/bash
# Canonical native compiler paths. NO C-VM.
#   bin/virc          — stable production compiler (do not overwrite casually)
#   dist/virc-stable  — backup of last known-good bin/virc
#   dist/virc-next    — experimental build from virc.vri (promote candidate)
#   dist/virc-full    — alias output name used by some scripts
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export VIR_ROOT="$ROOT"
export VIRC_STABLE="${VIRC_STABLE:-$ROOT/bin/virc}"
export VIRC_BACKUP="${VIRC_BACKUP:-$ROOT/dist/virc-stable}"
export VIRC_EXPERIMENTAL="${VIRC_EXPERIMENTAL:-$ROOT/dist/virc-next}"

virc_resolve() {
    if [ -n "${VIRC:-}" ] && [ -x "${VIRC}" ]; then
        echo "$VIRC"
        return 0
    fi
    if [ -x "$VIRC_EXPERIMENTAL" ]; then
        echo "$VIRC_EXPERIMENTAL"
        return 0
    fi
    if [ -x "$VIRC_STABLE" ]; then
        echo "$VIRC_STABLE"
        return 0
    fi
    if [ -x "$VIRC_BACKUP" ]; then
        echo "$VIRC_BACKUP"
        return 0
    fi
    return 1
}

virc_backup_stable() {
    local ts
    ts="$(date +%Y%m%d-%H%M%S)"
    mkdir -p "$ROOT/dist"
    if [ -x "$VIRC_STABLE" ]; then
        cp "$VIRC_STABLE" "$VIRC_BACKUP"
        cp "$VIRC_STABLE" "$ROOT/dist/virc-stable.$ts"
        echo "Backed up bin/virc → dist/virc-stable (+ dist/virc-stable.$ts)"
    fi
}

virc_sign() {
    local bin="$1"
    chmod +x "$bin"
    if [ "$(uname -s)" = "Darwin" ]; then
        codesign -s - -f "$bin" >/dev/null 2>&1 || true
    fi
}

# When sourced: expose functions. When executed: print resolved compiler path.
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
    virc_resolve
fi
