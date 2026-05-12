"""
maha — Lệnh nâng quyền tối cao.
==================================
Thay thế sudo. Chạy lệnh với quyền mahavir.

Cú pháp:
    maha <lệnh> [tham số...]       → Chạy lệnh với quyền tối cao
    maha -u <user> <lệnh>          → Chạy lệnh dưới quyền user khác
    maha -su                        → Chuyển sang phiên mahavir
    maha -k                         → Hủy session xác thực
    maha -l                         → Liệt kê quyền hiện tại
"""

from __future__ import annotations

import getpass
import hashlib
import os
import sys
from typing import Sequence

from ..auth.identity import get_identity_manager, UserRole
from ..auth.privilege import get_maha_engine, MahaLevel, MahaPolicy
from ..registry import register_command, register_alias


def _hash_password(password: str) -> str:
    """Hash mật khẩu với salt. Không bao giờ lưu plaintext."""
    salt = "viron_maha"  # Trong production dùng random salt
    return hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()


def cmd_maha(args: Sequence[str]) -> int:
    """Handler chính cho lệnh maha."""
    if not args:
        print("Cú pháp: maha <lệnh> [tham số...]")
        print("         maha -su          → Chuyển sang mahavir")
        print("         maha -k           → Hủy session")
        print("         maha -l           → Liệt kê quyền")
        return 1
    
    engine = get_maha_engine()
    identity = get_identity_manager()
    current_user = identity.get_current_user()
    
    # Xử lý flags
    if args[0] == "-su":
        return _maha_switch_user(current_user.username, args[1:])
    if args[0] == "-k":
        engine.invalidate_session(current_user.username)
        print("Session maha đã được hủy.")
        return 0
    if args[0] == "-l":
        return _maha_list_perms(current_user.username)
    
    # Flag -u <user>
    target_user = "mahavir"
    cmd_args = list(args)
    if len(cmd_args) >= 2 and cmd_args[0] == "-u":
        target_user = cmd_args[1]
        cmd_args = cmd_args[2:]
    
    if not cmd_args:
        print("Thiếu lệnh cần chạy.")
        return 1
    
    command = cmd_args[0]
    command_args = cmd_args[1:]
    
    # Kiểm tra user có quyền dùng maha không
    if not current_user.can_maha:
        print(f"⛔ {current_user.username} không thuộc nhóm maha.")
        print("Liên hệ mahavir để thêm vào nhóm maha.")
        return 1
    
    # Xác thực nếu chưa có session
    level = engine.get_current_level(current_user.username)
    if level == MahaLevel.USER:
        # Cần xác thực
        if current_user.is_mahavir:
            engine.authenticate(current_user.username)
        else:
            try:
                password = getpass.getpass(f"[maha] mật khẩu cho {current_user.username}: ")
            except (EOFError, KeyboardInterrupt):
                print("\nHủy.")
                return 1
            pw_hash = _hash_password(password)
            if not engine.authenticate(current_user.username, pw_hash):
                print("⛔ Xác thực thất bại.")
                return 1
    
    # Thực thi
    success, message = engine.execute_as_maha(
        current_user.username, command, command_args, target_user
    )
    if not success:
        print(f"⛔ {message}")
        return 1
    
    print(f"✓ Đã chạy '{command}' với quyền {target_user}")
    return 0


def _maha_switch_user(current_username: str, args: Sequence[str]) -> int:
    """Chuyển sang session mahavir (tương tự su)."""
    engine = get_maha_engine()
    target = args[0] if args else "mahavir"
    
    # Xác thực
    level = engine.get_current_level(current_username)
    if level == MahaLevel.USER:
        try:
            password = getpass.getpass(f"[maha] mật khẩu cho {current_username}: ")
        except (EOFError, KeyboardInterrupt):
            print("\nHủy.")
            return 1
        pw_hash = _hash_password(password)
        if not engine.authenticate(current_username, pw_hash):
            print("⛔ Xác thực thất bại.")
            return 1
    
    print(f"✓ Chuyển sang phiên {target}")
    os.environ["VIRON_USER"] = target
    return 0


def _maha_list_perms(username: str) -> int:
    """Liệt kê quyền maha của user."""
    engine = get_maha_engine()
    level = engine.get_current_level(username)
    
    level_names = {
        MahaLevel.USER: "Người dùng thường",
        MahaLevel.ELEVATED: "Quyền nâng cao",
        MahaLevel.SUPREME: "Quyền tối cao (mahavir)",
    }
    
    print(f"Người dùng: {username}")
    print(f"Cấp quyền:  {level_names.get(level, 'Không xác định')}")
    
    identity = get_identity_manager()
    user = identity.get_user(username)
    if user:
        print(f"Nhóm:       {', '.join(user.groups) if user.groups else '(không)'}")
        print(f"Quyền maha: {'Có' if user.can_maha else 'Không'}")
    return 0


def register_maha_commands() -> None:
    """Đăng ký tất cả lệnh maha vào registry."""
    register_command(
        name="maha",
        description="Chạy lệnh với quyền tối cao (thay sudo)",
        usage="maha [-u <user>] <lệnh> [tham số...]",
        handler=cmd_maha,
        category="auth",
        requires_maha=False,
    )
    register_command(
        name="maha-su",
        description="Chuyển sang phiên mahavir (thay su)",
        usage="maha -su [<user>]",
        handler=lambda args: _maha_switch_user(
            get_identity_manager().get_current_user().username, args
        ),
        category="auth",
    )
    
    # Alias tương thích
    register_alias("sudo", "maha")
    register_alias("su", "maha-su")
