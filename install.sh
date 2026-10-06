#!/bin/sh

set -eu

VIR_VERSION=${VIR_VERSION:-2026.1.0}
VIR_LSP_VERSION=${VIR_LSP_VERSION:-1.3.0}
VIR_REPOSITORY=${VIR_REPOSITORY:-virgori/Vir-lang}
VIR_PREFIX=${VIR_PREFIX:-${HOME:-}/.local}

install_virc=1
install_lsp=1

say() {
    printf '%s\n' "$*"
}

die() {
    printf 'vir installer: error: %s\n' "$*" >&2
    exit 1
}

usage() {
    cat <<'EOF'
Install the Vir compiler, language server, and standard-library sysroot.

Usage: sh install.sh [options]

Options:
  --prefix DIR          Install under DIR (default: $HOME/.local)
  --version VERSION     Compiler release version (default: 2026.1.0)
  --lsp-version VERSION vir-lsp version (default: 1.3.0)
  --compiler-only       Install virc without vir-lsp
  --lsp-only            Install vir-lsp without virc
  -h, --help            Show this help

Environment overrides:
  VIR_PREFIX, VIR_VERSION, VIR_LSP_VERSION, VIR_REPOSITORY

Supported platforms:
  macOS ARM64, Linux ARM64, Linux x86_64
EOF
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --prefix)
            [ "$#" -ge 2 ] || die "--prefix requires a directory"
            VIR_PREFIX=$2
            shift 2
            ;;
        --version)
            [ "$#" -ge 2 ] || die "--version requires a value"
            VIR_VERSION=$2
            shift 2
            ;;
        --lsp-version)
            [ "$#" -ge 2 ] || die "--lsp-version requires a value"
            VIR_LSP_VERSION=$2
            shift 2
            ;;
        --compiler-only)
            install_lsp=0
            shift
            ;;
        --lsp-only)
            install_virc=0
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            die "unknown option: $1"
            ;;
    esac
done

[ "$install_virc" -eq 1 ] || [ "$install_lsp" -eq 1 ] || \
    die "--compiler-only and --lsp-only cannot be combined"
[ -n "$VIR_PREFIX" ] || die "install prefix is empty; set HOME or VIR_PREFIX"
VIR_VERSION=${VIR_VERSION#v}
VIR_LSP_VERSION=${VIR_LSP_VERSION#v}

case "$VIR_VERSION" in
    ''|*[!0-9.]*) die "invalid compiler version: $VIR_VERSION" ;;
esac
case "$VIR_LSP_VERSION" in
    ''|*[!0-9.]*) die "invalid vir-lsp version: $VIR_LSP_VERSION" ;;
esac

os=$(uname -s)
arch=$(uname -m)

case "$os:$arch" in
    Darwin:arm64|Darwin:aarch64)
        platform=macos-arm64
        ;;
    Linux:x86_64|Linux:amd64)
        platform=linux-x86_64
        ;;
    Linux:aarch64|Linux:arm64)
        platform=linux-arm64
        ;;
    *)
        die "unsupported platform: $os $arch"
        ;;
esac

command -v tar >/dev/null 2>&1 || die "tar is required"

download() {
    source_url=$1
    destination=$2

    if command -v curl >/dev/null 2>&1; then
        curl --fail --location --proto '=https' --tlsv1.2 \
            --retry 3 --silent --show-error \
            --output "$destination" "$source_url"
    elif command -v wget >/dev/null 2>&1; then
        wget -q -O "$destination" "$source_url"
    else
        die "curl or wget is required"
    fi
}

sha256_file() {
    checksum_path=$1
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$checksum_path" | awk '{print $1}'
    elif command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "$checksum_path" | awk '{print $1}'
    elif command -v openssl >/dev/null 2>&1; then
        openssl dgst -sha256 "$checksum_path" | awk '{print $NF}'
    else
        die "sha256sum, shasum, or openssl is required"
    fi
}

verify_asset() {
    asset_path=$1
    asset_name=$2
    checksum_manifest=$3
    expected=$(awk -v name="$asset_name" '$2 == name {print $1; exit}' "$checksum_manifest")
    [ -n "$expected" ] || die "checksum is missing for $asset_name"
    actual=$(sha256_file "$asset_path")
    [ "$actual" = "$expected" ] || die "checksum mismatch for $asset_name"
}

temp_dir=$(mktemp -d "${TMPDIR:-/tmp}/vir-install.XXXXXX") || die "cannot create temporary directory"
cleanup() {
    rm -rf "$temp_dir"
}
trap cleanup 0 1 2 3 15

release_base="https://github.com/$VIR_REPOSITORY/releases/download/v$VIR_VERSION"
checksum_manifest="$temp_dir/SHA256SUMS.txt"
stdlib_asset="vir-stdlib-$VIR_VERSION.tar.gz"
virc_asset="virc-$VIR_VERSION-$platform"
lsp_asset="vir-lsp-$VIR_LSP_VERSION-$platform"

say "Installing Vir $VIR_VERSION for $platform"
download "$release_base/SHA256SUMS.txt" "$checksum_manifest"
download "$release_base/$stdlib_asset" "$temp_dir/$stdlib_asset"
verify_asset "$temp_dir/$stdlib_asset" "$stdlib_asset" "$checksum_manifest"

if [ "$install_virc" -eq 1 ]; then
    download "$release_base/$virc_asset" "$temp_dir/virc"
    verify_asset "$temp_dir/virc" "$virc_asset" "$checksum_manifest"
fi

if [ "$install_lsp" -eq 1 ]; then
    download "$release_base/$lsp_asset" "$temp_dir/vir-lsp"
    verify_asset "$temp_dir/vir-lsp" "$lsp_asset" "$checksum_manifest"
fi

extract_dir="$temp_dir/extract"
mkdir -p "$extract_dir"
tar -xzf "$temp_dir/$stdlib_asset" -C "$extract_dir"
[ -f "$extract_dir/stdlib/stdlib.vri" ] || die "stdlib archive has an invalid layout"

bin_dir="$VIR_PREFIX/bin"
lib_root="$VIR_PREFIX/lib/vir"
versioned_stdlib="$lib_root/stdlib-$VIR_VERSION"
active_stdlib="$lib_root/stdlib"

mkdir -p "$bin_dir" "$lib_root"
if [ ! -d "$versioned_stdlib" ]; then
    staged_stdlib="$lib_root/.stdlib-$VIR_VERSION.$$"
    mkdir "$staged_stdlib"
    cp -R "$extract_dir/stdlib/." "$staged_stdlib/"
    mv "$staged_stdlib" "$versioned_stdlib"
fi

if [ -e "$active_stdlib" ] && [ ! -L "$active_stdlib" ]; then
    die "$active_stdlib exists and is not a symlink; refusing to replace it"
fi
ln -sfn "stdlib-$VIR_VERSION" "$active_stdlib"

install_executable() {
    source_path=$1
    destination=$2
    if command -v install >/dev/null 2>&1; then
        install -m 0755 "$source_path" "$destination"
    else
        cp "$source_path" "$destination"
        chmod 0755 "$destination"
    fi
}

if [ "$install_virc" -eq 1 ]; then
    install_executable "$temp_dir/virc" "$bin_dir/virc"
    "$bin_dir/virc" --version
    "$bin_dir/virc" --print-sysroot >/dev/null
fi

if [ "$install_lsp" -eq 1 ]; then
    install_executable "$temp_dir/vir-lsp" "$bin_dir/vir-lsp"
    "$bin_dir/vir-lsp" --version
fi

say "Installed Vir tools under $VIR_PREFIX"
case ":${PATH:-}:" in
    *":$bin_dir:"*) ;;
    *) say "Add $bin_dir to PATH to run virc and vir-lsp." ;;
esac
