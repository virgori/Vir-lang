# Vir — Cross-Platform Binary Packaging Plan

## Overview

Vir ships **3 distributable components**, each with platform/architecture-specific binaries:

| Component | Type | Per-platform? | Format |
|-----------|------|---------------|--------|
| **libvir_core** | C/ASM native library | ✅ OS × Arch | `.dylib` / `.so` / `.dll` + `.a` |
| **vir-lang** wheel | Python package + bundled native lib | ✅ OS × Arch | `.whl` (platform-specific) |
| **Compiled stdlib** | `.vri` → `.sri` → `.vsib` | ✅ Arch only | `.vsib` bundles |

---

## Target Matrix

### Platforms × Architectures

| | x86_64 | ARM64 |
|---|--------|-------|
| **macOS** (13+) | ✅ `macosx_13_0_x86_64` | ✅ `macosx_14_0_arm64` |
| **Linux** (glibc 2.35+: Ubuntu 22.04, Debian 12, Rocky 9, Fedora 36+) | ✅ `manylinux_2_35_x86_64` | ✅ `manylinux_2_35_aarch64` |
| **Windows** (10+) | ✅ `win_amd64` | 🔶 cross-compile |

> Linux wheels target **glibc 2.35** — compatible with Ubuntu 22.04+, Debian 12+, Rocky 9+, Fedora 36+.
> For older distros (Ubuntu 20.04, Rocky 8), rebuild with `manylinux_2_31`.

---

## Architecture

### Build Pipeline

```
┌─────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  core/Makefile   │────▶│  libvir_core.so  │────▶│                  │
│  (C + ASM)       │     │  .dylib / .dll   │     │  vir_lang-*.whl  │
└─────────────────┘     └──────────────────┘     │  (platform wheel │
                                                  │   with native    │
┌─────────────────┐     ┌──────────────────┐     │   lib bundled)   │
│ scripts/         │────▶│  stdlib.vsib     │────▶│                  │
│ build_stdlib.py  │     │  (per-arch)      │     └──────────────────┘
└─────────────────┘     └──────────────────┘
```

### Native Library Search Order

`src/native/vir_native.py` searches for `libvir_core` in this order:
1. User-specified path (constructor argument)
2. **`src/native/lib/<lib_name>`** — bundled in wheel ← NEW
3. `core/lib/<lib_name>` — dev build
4. `core/build/<lib_name>` — dev build
5. Project root `/<lib_name>`

---

## Files Created/Modified

### New Files

| File | Purpose |
|------|---------|
| `.github/workflows/release.yml` | CI/CD: builds all 6 native targets, wheels, stdlib, tests, GitHub Release |
| `scripts/build_release.py` | Local release builder: native → inject → stdlib → wheel |
| `MANIFEST.in` | Ensures native libs + stdlib included in source distribution |
| `docs/packaging.md` | This document |

### Modified Files

| File | Change |
|------|--------|
| `pyproject.toml` | Fixed build backend, added package discovery + `package-data` for `.dylib/.so/.dll/.vsib` |
| `src/native/vir_native.py` | Added `src/native/lib/` as first search path for bundled libraries |

---

## Local Build

### Quick build (current platform only)

```bash
# Full release build: native + stdlib + wheel
python scripts/build_release.py

# Just native library
python scripts/build_release.py --native-only

# Just wheel (after native is built)
python scripts/build_release.py --wheel-only

# Force architecture
python scripts/build_release.py --arch arm64
```

### Manual steps

```bash
# 1. Build native library
cd core && make clean && make all && cd ..

# 2. Inject into package
mkdir -p src/native/lib
cp core/lib/libvir_core.dylib src/native/lib/   # macOS
# cp core/lib/libvir_core.so src/native/lib/    # Linux

# 3. Build stdlib
python -m scripts.build_stdlib --arch arm64

# 4. Build wheel
pip install build
python -m build --wheel
```

---

## CI/CD Pipeline (`.github/workflows/release.yml`)

### Trigger
- **Git tags**: push `v*` (e.g., `v0.1.0`, `v0.2.0-beta.1`)
- **Manual**: workflow_dispatch

### Jobs

```
build-native (6 parallel)            build-stdlib
  ├─ macos-arm64                       ├─ arm64
  ├─ macos-x86_64                      └─ x86_64
  ├─ linux-x86_64                         │
  ├─ linux-arm64 (cross)                  │
  ├─ windows-x86_64                       │
  └─ windows-arm64 (cross)               │
        │                                 │
        ▼                                 ▼
    build-wheel (5 parallel) ◄────────────┘
      ├─ macosx_14_0_arm64
      ├─ macosx_13_0_x86_64
      ├─ manylinux_2_35_x86_64
      ├─ manylinux_2_35_aarch64
      └─ win_amd64
              │
              ▼
          test (4 parallel)
            ├─ macos-14
            ├─ macos-13
            ├─ ubuntu-22.04
            └─ windows-latest
                  │
                  ▼
              release
              (GitHub Release + assets)
```

### Release Artifacts

Each release includes:
- **6 native archives**: `vir-{os}-{arch}.tar.gz` containing `libvir_core.*`, static lib, CLI binary
- **5 platform wheels**: `vir_lang-0.1.0-py3-none-{plat}.whl`
- **2 stdlib archives**: `stdlib-{arch}.tar.gz`

---

## Linux Distribution Compatibility

| glibc target | Compatible distros |
|---|---|
| `manylinux_2_35` (default) | Ubuntu 22.04+, Debian 12+, Rocky 9+, Fedora 36+, Arch current |
| `manylinux_2_31` (optional) | Ubuntu 20.04+, Debian 11+, Rocky 8+, CentOS Stream 8+ |
| `manylinux_2_28` (broad) | Most distros from 2020+ |

To target older distros, change the `plat` value in the CI workflow matrix.

---

## Release Process

```bash
# 1. Bump version in pyproject.toml
# 2. Commit and tag
git tag v0.1.0
git push origin v0.1.0

# 3. CI runs automatically:
#    build-native → build-stdlib → build-wheel → test → release

# 4. Artifacts appear at:
#    https://github.com/<org>/Vir/releases/tag/v0.1.0
```

### Publishing to PyPI (future)

Add a `publish` job after `release`:
```yaml
  publish:
    needs: test
    runs-on: ubuntu-22.04
    steps:
      - uses: actions/download-artifact@v4
        with: { pattern: 'wheel-*', path: wheels/, merge-multiple: true }
      - uses: pypa/gh-action-pypi-publish@release/v1
        with: { packages-dir: wheels/ }
```

---

## Platform-Specific Notes

### macOS
- Uses `clang` (Xcode CLT), builds `.dylib` with `@rpath` install name
- ARM64: `macos-14` (Apple Silicon runner), x86_64: `macos-13` (Intel runner)
- Universal binary possible via `lipo -create` (not implemented yet)

### Linux
- Uses `gcc`, builds `.so` with soname
- ARM64 cross-compiled via `aarch64-linux-gnu-gcc`
- Static links to `-lpthread -lrt`

### Windows
- Uses MinGW/GCC, builds `.dll` with import library (`.dll.a`)
- ARM64 cross-compiled via `clang --target=aarch64-pc-windows-msvc`
- Static links to `-lbcrypt`
