"""
pkg — Quản lý gói phần mềm Vir + OS.
=======================================
Vir-native (vir.toml):
    pkg init                → Tạo project mới (vir.toml)
    pkg add <name> [ver]    → Thêm dependency
    pkg rm <name>           → Xóa dependency
    pkg resolve             → Giải quyết & cài tất cả deps
    pkg publish             → Publish gói lên registry
    pkg vir-search <name>   → Tìm gói Vir
    pkg vir-list            → Liệt kê deps đã cài

OS package wrappers:
    pkg install <name>      → Cài đặt gói OS
    pkg remove <name>       → Gỡ gói OS
    pkg update              → Cập nhật danh sách gói
    pkg upgrade             → Nâng cấp tất cả gói
    pkg search <name>       → Tìm gói OS
    pkg list                → Liệt kê gói OS đã cài
    pkg info <name>         → Thông tin gói OS
"""

from __future__ import annotations

import platform
import subprocess
from pathlib import Path
from typing import Sequence

from ..registry import register_command, register_alias


def cmd_pkg(args: Sequence[str]) -> int:
    """Handler chính cho lệnh pkg."""
    if not args:
        return _pkg_help()
    
    subcmd = args[0]
    subargs = args[1:]
    
    handlers = {
        # Vir-native package management
        "init": _vir_init,
        "add": _vir_add,
        "rm": _vir_remove_dep,
        "resolve": _vir_resolve,
        "publish": _vir_publish,
        "vir-search": _vir_search,
        "vir-list": _vir_list_deps,
        # OS package wrappers
        "install": _pkg_install,
        "remove": _pkg_remove,
        "update": _pkg_update,
        "upgrade": _pkg_upgrade,
        "search": _pkg_search,
        "list": _pkg_list,
        "info": _pkg_info,
        "help": lambda _: _pkg_help(),
    }
    
    handler = handlers.get(subcmd)
    if handler is None:
        print(f"Lệnh con không hợp lệ: '{subcmd}'")
        return _pkg_help()
    
    return handler(subargs)


def _pkg_help() -> int:
    print("pkg — Quản lý gói phần mềm Vir + OS")
    print()
    print("  ── Vir-native ──────────────────────")
    print("  pkg init              Tạo project mới (vir.toml)")
    print("  pkg add <name> [ver]  Thêm dependency")
    print("  pkg rm <name>         Xóa dependency")
    print("  pkg resolve           Giải quyết & cài tất cả deps")
    print("  pkg publish           Publish gói lên registry")
    print("  pkg vir-search <q>    Tìm gói Vir")
    print("  pkg vir-list          Liệt kê deps đã cài")
    print()
    print("  ── OS wrappers ─────────────────────")
    print("  pkg install <name>    Cài đặt gói OS")
    print("  pkg remove <name>     Gỡ gói OS")
    print("  pkg update            Cập nhật danh sách")
    print("  pkg upgrade           Nâng cấp tất cả")
    print("  pkg search <name>     Tìm gói OS")
    print("  pkg list              Liệt kê gói OS đã cài")
    print("  pkg info <name>       Thông tin gói OS")
    return 0


# ═══════════════════════════════════════════════════════════
# Vir-native package commands
# ═══════════════════════════════════════════════════════════

def _vir_init(args: Sequence[str]) -> int:
    """pkg init [name] — Tạo vir.toml."""
    from src.pkg.manifest import init_manifest, SemVer
    project_dir = Path.cwd()
    name = args[0] if args else None
    manifest = init_manifest(project_dir, name)
    print(f"✓ Đã tạo vir.toml cho '{manifest.name}' v{manifest.version}")
    print(f"  → {project_dir / 'vir.toml'}")
    return 0


def _vir_add(args: Sequence[str]) -> int:
    """pkg add <name> [version_req] — Thêm dependency."""
    if not args:
        print("Cú pháp: pkg add <name> [version]")
        return 1
    name = args[0]
    ver = args[1] if len(args) > 1 else "^0.1.0"
    try:
        from src.pkg.installer import add_dependency
        add_dependency(Path.cwd(), name, ver)
        print(f"✓ Đã thêm {name} = \"{ver}\" vào vir.toml")
    except FileNotFoundError:
        print("⛔ Không tìm thấy vir.toml — chạy 'pkg init' trước")
        return 1
    return 0


def _vir_remove_dep(args: Sequence[str]) -> int:
    """pkg rm <name> — Xóa dependency."""
    if not args:
        print("Cú pháp: pkg rm <name>")
        return 1
    from src.pkg.installer import remove_dependency
    if remove_dependency(Path.cwd(), args[0]):
        print(f"✓ Đã xóa {args[0]} khỏi vir.toml")
    else:
        print(f"⚠ Không tìm thấy dependency '{args[0]}'")
    return 0


def _vir_resolve(args: Sequence[str]) -> int:
    """pkg resolve — Giải quyết & cài tất cả deps."""
    try:
        from src.pkg.installer import install_all
        print("Đang giải quyết dependencies...")
        resolved = install_all(Path.cwd(), include_dev="--dev" in args)
        if resolved:
            for pkg in resolved:
                print(f"  ✓ {pkg.name}@{pkg.version}")
            print(f"\n✓ Đã cài {len(resolved)} gói → vir_modules/")
        else:
            print("✓ Không có dependency nào cần cài")
    except FileNotFoundError:
        print("⛔ Không tìm thấy vir.toml — chạy 'pkg init' trước")
        return 1
    except Exception as e:
        print(f"⛔ Lỗi resolve: {e}")
        return 1
    return 0


def _vir_publish(args: Sequence[str]) -> int:
    """pkg publish — Publish gói lên local registry."""
    from src.pkg.manifest import load_manifest
    from src.pkg.registry import PackageInfo, publish_local
    project_dir = Path.cwd()
    try:
        manifest = load_manifest(project_dir / "vir.toml")
    except FileNotFoundError:
        print("⛔ Không tìm thấy vir.toml")
        return 1
    info = PackageInfo(
        name=manifest.name,
        version=manifest.version,
        description=manifest.description,
        authors=manifest.authors,
        license=manifest.license,
        dependencies=manifest.dependencies,
    )
    publish_local(project_dir, info)
    print(f"✓ Published {manifest.name}@{manifest.version} → ~/.vir/registry/")
    return 0


def _vir_search(args: Sequence[str]) -> int:
    """pkg vir-search <query> — Tìm gói Vir."""
    if not args:
        print("Cú pháp: pkg vir-search <query>")
        return 1
    from src.pkg.registry import search_local
    results = search_local(args[0])
    if results:
        for pkg in results:
            print(f"  {pkg.name} v{pkg.version}  — {pkg.description}")
    else:
        print(f"  Không tìm thấy gói nào khớp '{args[0]}'")
    return 0


def _vir_list_deps(args: Sequence[str]) -> int:
    """pkg vir-list — Liệt kê deps đã cài."""
    from src.pkg.registry import list_installed
    installed = list_installed(Path.cwd())
    if installed:
        for name, ver in installed:
            print(f"  {name} v{ver}")
        print(f"\nTổng: {len(installed)} gói")
    else:
        print("  Chưa có gói nào được cài (vir_modules/ trống)")
    return 0


def _get_pkg_backend() -> str:
    """Xác định package manager."""
    system = platform.system()
    if system == "Darwin":
        try:
            subprocess.run(["brew", "--version"], capture_output=True, timeout=5)
            return "brew"
        except FileNotFoundError:
            return "none"
    # Linux
    for pm, check in [("apt", "apt"), ("dnf", "dnf"), ("pacman", "pacman")]:
        try:
            subprocess.run([check, "--version"], capture_output=True, timeout=5)
            return pm
        except FileNotFoundError:
            continue
    return "none"


def _pkg_install(args: Sequence[str]) -> int:
    if not args:
        print("Cú pháp: pkg install <name>")
        return 1
    
    name = args[0]
    backend = _get_pkg_backend()
    
    cmd_map = {
        "brew": ["brew", "install", name],
        "apt": ["apt-get", "install", "-y", name],
        "dnf": ["dnf", "install", "-y", name],
        "pacman": ["pacman", "-S", "--noconfirm", name],
    }
    
    cmd = cmd_map.get(backend)
    if not cmd:
        print("Không tìm thấy package manager")
        return 1
    
    print(f"Đang cài đặt '{name}'...")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode == 0:
        print(f"✓ Đã cài đặt '{name}'")
    else:
        print(f"⛔ Lỗi: {result.stderr.strip()}")
        if backend != "brew":
            print(f"Thử: maha pkg install {name}")
    return result.returncode


def _pkg_remove(args: Sequence[str]) -> int:
    if not args:
        print("Cú pháp: pkg remove <name>")
        return 1
    
    name = args[0]
    backend = _get_pkg_backend()
    
    cmd_map = {
        "brew": ["brew", "uninstall", name],
        "apt": ["apt-get", "remove", "-y", name],
        "dnf": ["dnf", "remove", "-y", name],
        "pacman": ["pacman", "-R", "--noconfirm", name],
    }
    
    cmd = cmd_map.get(backend)
    if not cmd:
        return 1
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode == 0:
        print(f"✓ Đã gỡ '{name}'")
    else:
        print(f"⛔ Lỗi: {result.stderr.strip()}")
    return result.returncode


def _pkg_update(args: Sequence[str]) -> int:
    backend = _get_pkg_backend()
    
    cmd_map = {
        "brew": ["brew", "update"],
        "apt": ["apt-get", "update"],
        "dnf": ["dnf", "check-update"],
        "pacman": ["pacman", "-Sy"],
    }
    
    cmd = cmd_map.get(backend)
    if not cmd:
        return 1
    
    print("Đang cập nhật danh sách gói...")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    print("✓ Đã cập nhật")
    return 0


def _pkg_upgrade(args: Sequence[str]) -> int:
    backend = _get_pkg_backend()
    
    cmd_map = {
        "brew": ["brew", "upgrade"],
        "apt": ["apt-get", "upgrade", "-y"],
        "dnf": ["dnf", "upgrade", "-y"],
        "pacman": ["pacman", "-Syu", "--noconfirm"],
    }
    
    cmd = cmd_map.get(backend)
    if not cmd:
        return 1
    
    print("Đang nâng cấp gói...")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode == 0:
        print("✓ Đã nâng cấp xong")
    else:
        print(f"⛔ Lỗi: {result.stderr.strip()}")
    return result.returncode


def _pkg_search(args: Sequence[str]) -> int:
    if not args:
        print("Cú pháp: pkg search <name>")
        return 1
    
    name = args[0]
    backend = _get_pkg_backend()
    
    cmd_map = {
        "brew": ["brew", "search", name],
        "apt": ["apt-cache", "search", name],
        "dnf": ["dnf", "search", name],
        "pacman": ["pacman", "-Ss", name],
    }
    
    cmd = cmd_map.get(backend)
    if not cmd:
        return 1
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode == 0:
        lines = result.stdout.splitlines()
        for line in lines[:30]:
            print(f"  {line}")
        if len(lines) > 30:
            print(f"  ... và {len(lines) - 30} kết quả nữa")
    return result.returncode


def _pkg_list(args: Sequence[str]) -> int:
    backend = _get_pkg_backend()
    
    cmd_map = {
        "brew": ["brew", "list"],
        "apt": ["dpkg", "--list"],
        "dnf": ["dnf", "list", "installed"],
        "pacman": ["pacman", "-Q"],
    }
    
    cmd = cmd_map.get(backend)
    if not cmd:
        return 1
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    if result.returncode == 0:
        lines = result.stdout.splitlines()
        for line in lines[:40]:
            print(f"  {line}")
        if len(lines) > 40:
            print(f"  ... và {len(lines) - 40} gói nữa (tổng: {len(lines)})")
    return result.returncode


def _pkg_info(args: Sequence[str]) -> int:
    if not args:
        print("Cú pháp: pkg info <name>")
        return 1
    
    name = args[0]
    backend = _get_pkg_backend()
    
    cmd_map = {
        "brew": ["brew", "info", name],
        "apt": ["apt-cache", "show", name],
        "dnf": ["dnf", "info", name],
        "pacman": ["pacman", "-Qi", name],
    }
    
    cmd = cmd_map.get(backend)
    if not cmd:
        return 1
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    if result.returncode == 0:
        print(result.stdout)
    else:
        print(f"Không tìm thấy gói '{name}'")
    return result.returncode


def register_pkg_commands() -> None:
    """Đăng ký lệnh pkg."""
    register_command(
        name="pkg",
        description="Quản lý gói phần mềm (thay apt/brew/dnf)",
        usage="pkg <subcommand> [args...]",
        handler=cmd_pkg,
        category="package",
    )
    
    register_alias("apt", "pkg")
    register_alias("brew", "pkg")
    register_alias("dnf", "pkg")
    register_alias("pacman", "pkg")
