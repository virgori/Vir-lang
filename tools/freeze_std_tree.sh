
#!/usr/bin/env bash
# Freeze Vir std/compiler trees to a versioned directory snapshot.
# Filesystem freeze — complementary to git tags (not a substitute for history).
#
# Usage:
#   bash tools/freeze_std_tree.sh release v2.2.0
#   bash tools/freeze_std_tree.sh experimental heap-2gb
#   bash tools/freeze_std_tree.sh release v2.2.0 --with-bin --with-expanded
#   bash tools/freeze_std_tree.sh list
#   bash tools/freeze_std_tree.sh verify frozen/release/v2.2.0
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p dist
export TMPDIR="$(pwd)/dist"

ROOT_FREEZE="${VIR_FREEZE_ROOT:-frozen}"
IDENT_CODESIGN="${VIR_FREEZE_IDENT:-virc-bootstrap}"

usage() {
  cat <<'EOF'
freeze_std_tree.sh — versioned filesystem freeze for std + compiler trees

  bash tools/freeze_std_tree.sh release <semver> [options]
  bash tools/freeze_std_tree.sh experimental <slug> [options]
  bash tools/freeze_std_tree.sh list
  bash tools/freeze_std_tree.sh verify <freeze-dir>

Options:
  --with-bin         Build a versioned compiler, smoke-test it, then freeze it
  --version <semver> Compiler version for experimental freezes (release: inferred)
  --with-expanded    Copy dist/virc-expanded.vri
  --with-stage1      Copy virc_stage1.vri + dist/virc-stage1 if present
  --readonly         chmod -R a-w on the freeze tree after write
  --force            Replace existing freeze dir

Env:
  VIR_FREEZE_ROOT    Root dir (default: frozen/)
  VIR_STDLIB_SRC     Source stdlib directory (default: stdlib)
  VIRC               Native compiler seed used to build --with-bin
EOF
}

die() { echo "ERROR: $*" >&2; exit 1; }

sha_file() {
  if command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$1" | awk '{print $1}'
  else
    sha256sum "$1" | awk '{print $1}'
  fi
}

git_meta() {
  local commit branch dirty
  commit="$(git rev-parse HEAD 2>/dev/null || echo unknown)"
  branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
  if git diff --quiet --ignore-submodules 2>/dev/null && git diff --cached --quiet --ignore-submodules 2>/dev/null; then
    dirty=0
  else
    dirty=1
  fi
  printf '%s\t%s\t%s' "$commit" "$branch" "$dirty"
}

copy_tree() {
  local src="$1" dst="$2"
  mkdir -p "$(dirname "$dst")"
  # Prefer rsync; fall back to cp -a
  if command -v rsync >/dev/null 2>&1; then
    rsync -a --delete \
      --exclude '.git/' \
      --exclude '__pycache__/' \
      --exclude '*.pyc' \
      --exclude '.DS_Store' \
      "$src"/ "$dst"/
  else
    rm -rf "$dst"
    mkdir -p "$dst"
    cp -a "$src"/. "$dst"/
  fi
}

write_manifest() {
  local dest="$1" kind="$2" name="$3" compiler_version="$4"
  local meta commit branch dirty
  meta="$(git_meta)"
  commit="$(printf '%s' "$meta" | cut -f1)"
  branch="$(printf '%s' "$meta" | cut -f2)"
  dirty="$(printf '%s' "$meta" | cut -f3)"
  local ts
  ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

  # Collect file hashes for key roots
  local tmp_hashes
  tmp_hashes="$(mktemp)"
  (
    cd "$dest"
    find . -type f ! -name MANIFEST.json ! -name SHA256SUMS 2>/dev/null \
      | sed 's#^./##' | LC_ALL=C sort | while read -r f; do
      printf '%s  %s\n' "$(sha_file "$f")" "$f"
    done
  ) >"$tmp_hashes"

  local stdlib_files compiler_files
  stdlib_files="$(find "$dest/stdlib" -type f 2>/dev/null | wc -l | tr -d ' ')"
  compiler_files="$(find "$dest/compiler_src" -type f 2>/dev/null | wc -l | tr -d ' ')"

  cat >"$dest/MANIFEST.json" <<EOF
{
  "schema": 1,
  "kind": "$kind",
  "name": "$name",
  "created_utc": "$ts",
  "git_commit": "$commit",
  "git_branch": "$branch",
  "git_dirty": $dirty,
  "compiler_version": "v$compiler_version",
  "paths": {
    "stdlib": "stdlib/",
    "compiler_src": "compiler_src/",
    "bin": "bin/",
    "expanded": "virc-expanded.vri"
  },
  "counts": {
    "stdlib_files": $stdlib_files,
    "compiler_src_files": $compiler_files
  },
  "note": "Filesystem freeze for release/experiment isolation. Git remains source of history; this tree is the runnable pin."
}
EOF

  cp "$tmp_hashes" "$dest/SHA256SUMS"
  rm -f "$tmp_hashes"
  echo "MANIFEST: $dest/MANIFEST.json"
  echo "SHA256SUMS: $dest/SHA256SUMS ($stdlib_files stdlib files, $compiler_files compiler_src files)"
}

source_version() {
  sed -nE 's/.*v([0-9]+\.[0-9]+\.[0-9]+).*Multi-Target Matrix.*/\1/p' "$1" | head -n 1
  sed -nE 's/.*v([0-9]+\.[0-9]+\.[0-9]+).*/\1/p' "$1" | head -n 1
}

set_source_version() {
  local src="$1" version="$2" tmp
  tmp="$(mktemp)"
  sed -E \
    -e "s/(const VERSION: \"virc )[0-9]+\.[0-9]+\.[0-9]+/\\1$version/" \
    -e "s/(print_ln\(\"  )v[0-9]+\.[0-9]+\.[0-9]+( — Multi-Target Matrix & LIR Pipeline\"\))/\\1v$version\\2/" \
    -e "s/(print_ln\(\"  )v[0-9]+\.[0-9]+\.[0-9]+( — .*\")/\\1v$version\\2/" \
    "$src" >"$tmp"
  mv "$tmp" "$src"
  [ "$(source_version "$src")" = "$version" ] || \
    die "failed to stamp compiler source version v$version: $src"
}

build_freeze_bin() {
  local dest="$1" version="$2" seed src output smoke_src smoke_bin banner
  seed="${VIRC:-bin/virc}"
  if [ ! -x "$seed" ]; then
    seed="dist/virc-next"
  fi
  [ -x "$seed" ] || die "--with-bin: no executable native seed (set VIRC or provide bin/virc)"
  seed="$(cd "$(dirname "$seed")" && pwd -P)/$(basename "$seed")"

  src="$dest/stdlib/vir/compiler/virc.vri"
  output="$dest/bin/virc"
  [ -f "$src" ] || die "--with-bin: missing compiler source: $src"
  set_source_version "$src" "$version"
  set_source_version "$dest/compiler_src/stdlib_vir_compiler/virc.vri" "$version"

  echo "Building bin/virc v$version with seed $seed ..."
  (cd "$dest" && "$seed" stdlib/vir/compiler/virc.vri -o bin/virc -q)
  [ -x "$output" ] || die "--with-bin: build succeeded but produced no executable: $output"
  if command -v codesign >/dev/null 2>&1; then
    codesign -f -s - -i "$IDENT_CODESIGN" "$output" >/dev/null 2>&1 || true
  fi

  banner="$("$output" --version 2>&1 || true)"
  grep -Eq "v${version}[[:space:]]+Multi-Target Matrix & LIR Pipeline" <<<"$banner" || \
  grep -Eq "v${version}[[:space:]]+" <<<"$banner" || \
    die "--with-bin: built compiler banner does not contain v$version"

  smoke_src="$dest/.virc-freeze-smoke.vri"
  smoke_bin="$dest/.virc-freeze-smoke"
  cat >"$smoke_src" <<'EOF'
func main:
    print 30
    print 90
    out 0
end.
EOF
  "$output" "$smoke_src" -o "$smoke_bin" >/dev/null
  [ -x "$smoke_bin" ] || die "--with-bin: smoke compile produced no executable"
  if command -v codesign >/dev/null 2>&1; then
    codesign -f -s - "$smoke_bin" >/dev/null 2>&1 || true
  fi
  [ "$("$smoke_bin" 2>&1 | tr '\n' ' ' | sed -E 's/[[:space:]]+$//')" = "30 90" ] || \
    die "--with-bin: frozen compiler smoke test failed"
  rm -f "$smoke_src" "$smoke_bin"

  echo "✓ bin/virc v$version ($(stat -f%z "$output" 2>/dev/null || stat -c%s "$output") bytes, built + smoke-tested)"
}

cmd_list() {
  if [ ! -d "$ROOT_FREEZE" ]; then
    echo "(no freezes yet under $ROOT_FREEZE/)"
    return 0
  fi
  find "$ROOT_FREEZE" -mindepth 2 -maxdepth 2 -type d | LC_ALL=C sort | while read -r d; do
    if [ -f "$d/MANIFEST.json" ]; then
      echo "$d"
    fi
  done
}

cmd_verify() {
  local dest="$1"
  [ -d "$dest" ] || die "missing freeze dir: $dest"
  [ -f "$dest/SHA256SUMS" ] || die "missing SHA256SUMS in $dest"
  if command -v shasum >/dev/null 2>&1; then
    (cd "$dest" && shasum -a 256 -c SHA256SUMS)
  else
    (cd "$dest" && sha256sum -c SHA256SUMS)
  fi
}

do_freeze() {
  local kind="$1" name="$2"
  shift 2
  local with_bin=0 with_expanded=0 with_stage1=0 readonly=0 force=0 requested_version=""
  while [ $# -gt 0 ]; do
    case "$1" in
      --with-bin) with_bin=1 ;;
      --with-expanded) with_expanded=1 ;;
      --with-stage1) with_stage1=1 ;;
      --version)
        [ $# -ge 2 ] || die "--version needs a semver"
        requested_version="${2#v}"
        shift
        ;;
      --readonly) readonly=1 ;;
      --force) force=1 ;;
      -h|--help) usage; exit 0 ;;
      *) die "unknown option: $1" ;;
    esac
    shift
  done

  case "$kind" in
    release)
      [[ "$name" =~ ^v?[0-9]+\.[0-9]+(\.[0-9]+)?([.-].*)?$ ]] || \
        die "release name should look like v2.2.0 (got: $name)"
      ;;
    experimental)
      [[ "$name" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] || \
        die "experimental slug must be [A-Za-z0-9._-]+ (got: $name)"
      ;;
    *) die "kind must be release|experimental" ;;
  esac

  local compiler_version
  if [ "$kind" = release ]; then
    compiler_version="${name#v}"
    if [ -n "$requested_version" ] && [ "$requested_version" != "$compiler_version" ]; then
      die "--version v$requested_version does not match release $name"
    fi
  elif [ -n "$requested_version" ]; then
    compiler_version="$requested_version"
  else
    compiler_version="$(source_version "${VIR_STDLIB_SRC:-stdlib}/vir/compiler/virc.vri")"
    [ -n "$compiler_version" ] || die "cannot detect compiler version; pass --version"
  fi
  [[ "$compiler_version" =~ ^[0-9]+\.[0-9]+\.[0-9]+([.-].*)?$ ]] || \
    die "compiler version must be semver-like (got: $compiler_version)"

  local dest="$ROOT_FREEZE/$kind/$name"
  if [ -e "$dest" ] && [ "$force" -ne 1 ]; then
    die "exists: $dest (pass --force to replace)"
  fi
  if [ -e "$dest" ]; then
    chmod -R u+w "$dest" 2>/dev/null || true
  fi
  rm -rf "$dest"
  mkdir -p "$dest"

  echo "=== Freeze $kind/$name → $dest ==="

  # Working-tree stdlib (full tree under stdlib/)
  local std_src="${VIR_STDLIB_SRC:-stdlib}"
  [ -d "$std_src" ] || die "missing $std_src/"
  copy_tree "$std_src" "$dest/stdlib"
  echo "✓ stdlib/"

  # Compiler sources as a focused pin (stdlib/vir/compiler + entrypoints)
  mkdir -p "$dest/compiler_src"
  if [ -d "$std_src/vir/compiler" ]; then
    copy_tree "$std_src/vir/compiler" "$dest/compiler_src/stdlib_vir_compiler"
    echo "✓ compiler_src/stdlib_vir_compiler/"
  fi
  for f in virc_stage1.vri virc_boot.vri; do
    if [ -f "$f" ]; then
      cp -a "$f" "$dest/compiler_src/$f"
      echo "✓ compiler_src/$f"
    fi
  done

  mkdir -p "$dest/bin"
  if [ "$with_bin" -eq 1 ]; then
    build_freeze_bin "$dest" "$compiler_version"
  fi

  if [ "$with_expanded" -eq 1 ]; then
    [ -f dist/virc-expanded.vri ] || die "--with-expanded: missing dist/virc-expanded.vri"
    cp -a dist/virc-expanded.vri "$dest/virc-expanded.vri"
    echo "✓ virc-expanded.vri"
  fi

  if [ "$with_stage1" -eq 1 ]; then
    [ -f virc_stage1.vri ] || die "--with-stage1: missing virc_stage1.vri"
    mkdir -p "$dest/stage1"
    cp -a virc_stage1.vri "$dest/stage1/"
    if [ -x dist/virc-stage1 ]; then
      cp -a dist/virc-stage1 "$dest/stage1/virc-stage1"
    fi
    echo "✓ stage1/"
  fi

  cat >"$dest/README.md" <<EOF
# Vir freeze: $kind / $name

Filesystem pin of stdlib + compiler sources for **$kind**.

- Use this tree for release packaging or isolated experiments.
- Do **not** edit in place for ongoing development — work in the live repo, then freeze again.
- Verify integrity: \`bash tools/freeze_std_tree.sh verify $dest\`

Created by \`tools/freeze_std_tree.sh\`.
EOF

  if [ -f "$std_src/../BOOTSTRAP_REPORT.md" ]; then
    cp -a "$std_src/../BOOTSTRAP_REPORT.md" "$dest/BOOTSTRAP_REPORT.md"
    echo "✓ BOOTSTRAP_REPORT.md"
  elif [ -f BOOTSTRAP_REPORT.md ]; then
    cp -a BOOTSTRAP_REPORT.md "$dest/BOOTSTRAP_REPORT.md"
    echo "✓ BOOTSTRAP_REPORT.md"
  fi

  write_manifest "$dest" "$kind" "$name" "$compiler_version"

  if [ "$readonly" -eq 1 ]; then
    chmod -R a-w "$dest"
    echo "✓ marked read-only"
  fi

  echo ""
  echo "FREEZE_OK $dest"
}

main() {
  if [ $# -lt 1 ]; then
    usage
    exit 1
  fi
  case "$1" in
    -h|--help) usage; exit 0 ;;
    list) cmd_list ;;
    verify)
      [ $# -ge 2 ] || die "verify needs a path"
      cmd_verify "$2"
      ;;
    release|experimental)
      [ $# -ge 2 ] || die "$1 needs a name"
      local kind="$1" name="$2"
      shift 2
      do_freeze "$kind" "$name" "$@"
      ;;
    *) usage; die "unknown command: $1" ;;
  esac
}

main "$@"
