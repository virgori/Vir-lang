#!/bin/bash
# Wrapper: run the soft self-hosted compiler (stdlib/vir/compiler/virc.vri)
# under the C-core VM, so it can be passed to test_native.sh as $VIRC.
# Usage: tools/virc_soft.sh <input.vri> -o <output> [--target ...] [--format ...]
cd "$(dirname "$0")/.."
exec ./core/build/vir run stdlib/vir/compiler/virc.vri -- "$@"
