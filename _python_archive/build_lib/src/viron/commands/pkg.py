"""
pkg — Quản lý gói phần mềm.
==============================
Cú pháp:
    pkg install <name>      → Cài đặt gói
    pkg remove <name>       → Gỡ gói
    pkg update              → Cập nhật danh sách gói
    pkg upgrade             → Nâng cấp tất cả gói
    pkg search <name>       → Tìm gói
    pkg list                → Liệt kê gói đã cài
    pkg info <name>         → Thông tin gói
"""

from __future__ import annotations

import platform
import subprocess
from typing import Sequence

from ..registry import register_command, register_alias


def cmd_pkg(args: Sequence[str]) -> int:
    """Handler chính cho lệnh pkg."""
    if not args:
        return _pkg_help()
    
    subcmd = args[0]
    subargs = args[1:]
    
    handlers = {
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
    print("pkg — Quản lý gói phần mềm")
    print()
    print("  pkg install <name>    Cài đặt gói")
    print("  pkg remove <name>     Gỡ gói")
    print("  pkg update            Cập nhật danh sách")
    print("  pkg upgrade           Nâng cấp tất cả")
    print("  pkg search <name>     Tìm gói")
    print("  pkg list              Liệt kê gói đã cài")
    print("  pkg info <name>       Thông tin gói")
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
