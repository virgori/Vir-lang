#!/usr/bin/env bash
set -euo pipefail

fail() {
    printf 'release validation failed: %s\n' "$1" >&2
    exit 1
}

if [ "$#" -ne 1 ]; then
    fail "usage: tools/validate_official_release_tag.sh <tag>"
fi

tag="$1"
repo_root="$(git rev-parse --show-toplevel 2>/dev/null)" || fail "not inside a Git repository"
version_file="$repo_root/compiler/version.json"

[ -f "$version_file" ] || fail "missing compiler/version.json"
command -v jq >/dev/null 2>&1 || fail "jq is required"

if [[ ! "$tag" =~ ^v([0-9]{4})\.([1-9][0-9]*)\.0$ ]]; then
    fail "tag '$tag' is not canonical vYYYY.R.0"
fi

tag_year="${BASH_REMATCH[1]}"
tag_release="${BASH_REMATCH[2]}"

schema="$(jq -er '.schema' "$version_file")" || fail "invalid version schema"
year="$(jq -er '.year' "$version_file")" || fail "missing release year"
release="$(jq -er '.release' "$version_file")" || fail "missing release number"
internal_patch="$(jq -er '.internal_patch' "$version_file")" || fail "missing internal patch"
channel="$(jq -er '.channel | strings' "$version_file")" || fail "missing release channel"
public_version="$(jq -er '.public_version | strings' "$version_file")" || fail "missing public version"

[ "$schema" = "1" ] || fail "unsupported version schema '$schema'"
[ "$channel" = "official" ] || fail "compiler channel '$channel' is not official"
[ "$internal_patch" = "0" ] || fail "official release requires internal_patch 0"
[[ "$public_version" =~ ^[0-9]{4}\.[1-9][0-9]*$ ]] || fail "invalid public version '$public_version'"
[ "$public_version" = "$year.$release" ] || fail "public version does not match year/release metadata"
[ "$tag_year" = "$year" ] || fail "tag year does not match compiler metadata"
[ "$tag_release" = "$release" ] || fail "tag release does not match compiler metadata"

expected_tag="v${public_version}.0"
[ "$tag" = "$expected_tag" ] || fail "expected tag '$expected_tag', received '$tag'"

notes_file="docs/releases/${public_version}.0.md"
[ -f "$repo_root/$notes_file" ] || fail "missing release notes '$notes_file'"

printf '%s\n%s\n' "$public_version" "$notes_file"
