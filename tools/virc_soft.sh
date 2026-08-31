#!/bin/bash
# Wrapper: run native Vir compiler (stable bin/virc or dist/virc-next). NO C-VM.
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=tools/virc_bin.sh
source tools/virc_bin.sh

EXTRA_ARGS=()
if [ "$(uname -s)" = "Linux" ]; then
    if [[ ! "$*" =~ "--format" ]]; then
        EXTRA_ARGS+=(--format elf)
    fi
fi

VIRC_BIN="$(virc_resolve)"
exec "$VIRC_BIN" "$@" "${EXTRA_ARGS[@]}"
