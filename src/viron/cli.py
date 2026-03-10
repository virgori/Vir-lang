"""
Viron CLI — Điểm vào chính cho công cụ quản lý hệ thống Vir.
===============================================================
Viron là CLI chính, điều phối tất cả lệnh hệ thống:
- maha (quyền tối cao, thay sudo)
- net (mạng, thay ifconfig)
- proc (tiến trình, thay ps)
- fs (tệp, thay ls/cp/mv)
- svc (dịch vụ, thay systemctl)
- pkg (gói, thay apt/brew)
- user (người dùng, mahavir = tối cao)
- sys (thông tin hệ thống)

Alias engine cho phép ánh xạ zero-cost sang bộ lệnh khác.
"""

from __future__ import annotations

import sys
from typing import Sequence

from . import __version__
from .registry import get_registry, CommandRegistry
from .alias_engine import load_aliases, register_default_aliases

# Import và đăng ký tất cả commands
from .commands.maha import register_maha_commands
from .commands.net import register_net_commands
from .commands.proc import register_proc_commands
from .commands.fs_cmd import register_fs_commands
from .commands.svc import register_svc_commands
from .commands.pkg import register_pkg_commands
from .commands.user import register_user_commands
from .commands.sys_info import register_sys_commands


def _register_all_commands() -> None:
    """Đăng ký tất cả lệnh built-in."""
    register_maha_commands()
    register_net_commands()
    register_proc_commands()
    register_fs_commands()
    register_svc_commands()
    register_pkg_commands()
    register_user_commands()
    register_sys_commands()


def _print_banner() -> None:
    print(f"""
╔══════════════════════════════════════════╗
║           V I R O N  v{__version__:<17}║
║   Hệ thống quản lý — Vir OS CLI Tool    ║
╚══════════════════════════════════════════╝
""")


def _print_help() -> None:
    """In trợ giúp chung."""
    _print_banner()
    
    registry = get_registry()
    categories = registry.list_by_category()
    
    category_names = {
        "auth": "🔐 Xác thực & Quyền",
        "network": "🌐 Mạng",
        "process": "⚙️  Tiến trình",
        "filesystem": "📁 Hệ thống tệp",
        "service": "🔧 Dịch vụ",
        "package": "📦 Gói phần mềm",
        "user": "👤 Người dùng",
        "system": "💻 Hệ thống",
    }
    
    for cat, commands in categories.items():
        cat_name = category_names.get(cat, cat.title())
        print(f"  {cat_name}:")
        for cmd in commands:
            aliases = registry.get_aliases(cmd.name)
            alias_str = f" (alias: {', '.join(aliases)})" if aliases else ""
            maha_str = " [cần maha]" if cmd.requires_maha else ""
            print(f"    {cmd.name:<16} {cmd.description}{alias_str}{maha_str}")
        print()
    
    print("Cú pháp: viron <lệnh> [tham số...]")
    print("         viron help           Trợ giúp")
    print("         viron alias          Liệt kê alias")
    print("         viron version        Phiên bản")
    print()
    print("Ví dụ:")
    print("  viron net list              Liệt kê interface mạng")
    print("  viron maha proc kill 1234   Dừng tiến trình với quyền maha")
    print("  viron user whoami           Xem user hiện tại")
    print("  viron fs list /home         Liệt kê tệp")
    print()
    print("User tối cao: mahavir | Quyền tối cao: maha")


def _print_aliases() -> None:
    """Liệt kê tất cả alias."""
    registry = get_registry()
    commands = registry.list_commands()
    
    print("Alias đã đăng ký:")
    print(f"  {'Alias':<20} {'→'} {'Lệnh gốc'}")
    print("  " + "-" * 45)
    
    for cmd in commands:
        aliases = registry.get_aliases(cmd.name)
        for alias in aliases:
            print(f"  {alias:<20} → {cmd.name}")


def run_cli(argv: Sequence[str] | None = None) -> int:
    """
    Điểm vào chính cho Viron CLI.
    
    Quy trình:
    1. Đăng ký tất cả commands
    2. Load aliases từ config + defaults
    3. Parse argv và dispatch đến handler
    """
    args = list(argv) if argv is not None else sys.argv[1:]
    
    # Bước 1: Đăng ký commands
    _register_all_commands()
    
    # Bước 2: Load aliases (zero-cost — chỉ thêm dict entries)
    register_default_aliases()
    load_aliases()
    
    # Bước 3: Dispatch
    if not args:
        _print_help()
        return 0
    
    command_name = args[0]
    command_args = args[1:]
    
    # Built-in meta commands
    if command_name in ("help", "--help", "-h"):
        _print_help()
        return 0
    if command_name in ("version", "--version", "-v"):
        print(f"Viron v{__version__}")
        return 0
    if command_name == "alias":
        _print_aliases()
        return 0
    
    # Tra cứu registry O(1)
    registry = get_registry()
    meta = registry.resolve(command_name)
    
    if meta is None:
        print(f"viron: lệnh không tìm thấy: '{command_name}'")
        print(f"Dùng 'viron help' để xem danh sách lệnh.")
        return 127
    
    # Check quyền maha nếu cần
    if meta.requires_maha:
        from .auth.identity import get_identity_manager
        user = get_identity_manager().get_current_user()
        if not user.can_maha and not user.is_mahavir:
            print(f"⛔ Lệnh '{command_name}' cần quyền maha.")
            print(f"Thử: viron maha {command_name} {' '.join(command_args)}")
            return 1
    
    # Thực thi handler
    try:
        return meta.handler(command_args)
    except KeyboardInterrupt:
        print("\nĐã hủy.")
        return 130
    except Exception as e:
        print(f"⛔ Lỗi: {e}")
        return 1


def main() -> None:
    """Entry point cho pyproject.toml console_scripts."""
    sys.exit(run_cli())
