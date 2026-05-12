"""
user — Quản lý người dùng & nhóm.
====================================
mahavir là người dùng tối cao (thay root).

Cú pháp:
    user whoami             → Ai đang đăng nhập
    user list               → Liệt kê người dùng
    user add <name>         → Tạo người dùng mới
    user del <name>         → Xoá người dùng
    user passwd [<name>]    → Đổi mật khẩu
    user groups [<name>]    → Liệt kê nhóm
    user addgroup <name> <group>  → Thêm vào nhóm
    user info <name>        → Thông tin người dùng
    user maha-add <name>    → Thêm vào nhóm maha
"""

from __future__ import annotations

import os
from typing import Sequence

from ..auth.identity import (
    get_identity_manager, VirUser, UserRole,
    MAHAVIR_USER,
)
from ..registry import register_command, register_alias


def cmd_user(args: Sequence[str]) -> int:
    """Handler chính cho lệnh user."""
    if not args:
        return _user_whoami([])
    
    subcmd = args[0]
    subargs = args[1:]
    
    handlers = {
        "whoami": _user_whoami,
        "list": _user_list,
        "add": _user_add,
        "del": _user_del,
        "passwd": _user_passwd,
        "groups": _user_groups,
        "addgroup": _user_addgroup,
        "info": _user_info,
        "maha-add": _user_maha_add,
        "help": lambda _: _user_help(),
    }
    
    handler = handlers.get(subcmd)
    if handler is None:
        # Coi như user info <name>
        return _user_info([subcmd])
    
    return handler(subargs)


def _user_help() -> int:
    print("user — Quản lý người dùng")
    print()
    print("  user whoami              Ai đang đăng nhập")
    print("  user list                Liệt kê người dùng")
    print("  user add <name>          Tạo người dùng")
    print("  user del <name>          Xoá người dùng")
    print("  user passwd [<name>]     Đổi mật khẩu")
    print("  user groups [<name>]     Liệt kê nhóm")
    print("  user addgroup <u> <g>    Thêm vào nhóm")
    print("  user info <name>         Thông tin")
    print("  user maha-add <name>     Cấp quyền maha")
    print()
    print("Người dùng tối cao: mahavir (UID 0)")
    return 0


def _user_whoami(args: Sequence[str]) -> int:
    """Hiển thị người dùng hiện tại."""
    mgr = get_identity_manager()
    user = mgr.get_current_user()
    
    print(f"{user.username}")
    if user.is_mahavir:
        print("(mahavir — quyền tối cao)")
    return 0


def _user_list(args: Sequence[str]) -> int:
    """Liệt kê người dùng."""
    mgr = get_identity_manager()
    users = mgr.list_users()
    
    print(f"{'UID':>5}  {'Username':<20}  {'Role':<15}  {'Groups'}")
    print("-" * 65)
    
    role_names = {
        UserRole.GUEST: "Khách",
        UserRole.USER: "Người dùng",
        UserRole.MAHA_MEMBER: "Maha member",
        UserRole.ADMIN: "Quản trị",
        UserRole.MAHAVIR: "MAHAVIR ✦",
    }
    
    for user in users:
        groups = ", ".join(user.groups) if user.groups else "-"
        role = role_names.get(user.role, "?")
        print(f"{user.uid:>5}  {user.username:<20}  {role:<15}  {groups}")
    
    print(f"\nTổng: {len(users)} người dùng")
    return 0


def _user_add(args: Sequence[str]) -> int:
    """Tạo người dùng mới (cần quyền maha)."""
    if not args:
        print("Cú pháp: user add <username> [--maha] [--admin]")
        return 1
    
    username = args[0]
    mgr = get_identity_manager()
    
    role = UserRole.USER
    groups: list[str] = []
    
    if "--maha" in args:
        role = UserRole.MAHA_MEMBER
        groups.append("maha")
    if "--admin" in args:
        role = UserRole.ADMIN
        groups.append("maha")
    
    try:
        user = mgr.add_user(username, role=role, groups=groups)
        print(f"✓ Đã tạo người dùng '{username}'")
        print(f"  UID:  {user.uid}")
        print(f"  Home: {user.home_dir}")
        print(f"  Role: {user.role.name}")
    except ValueError as e:
        print(f"⛔ {e}")
        return 1
    return 0


def _user_del(args: Sequence[str]) -> int:
    """Xoá người dùng (cần quyền maha)."""
    if not args:
        print("Cú pháp: user del <username>")
        return 1
    
    username = args[0]
    mgr = get_identity_manager()
    
    if username == "mahavir":
        print("⛔ Không thể xoá mahavir!")
        return 1
    
    if mgr.remove_user(username):
        print(f"✓ Đã xoá người dùng '{username}'")
    else:
        print(f"Không tìm thấy người dùng '{username}'")
        return 1
    return 0


def _user_passwd(args: Sequence[str]) -> int:
    """Đổi mật khẩu."""
    import getpass
    target = args[0] if args else None
    mgr = get_identity_manager()
    
    if target is None:
        target = mgr.get_current_user().username
    
    user = mgr.get_user(target)
    if user is None:
        print(f"Không tìm thấy người dùng '{target}'")
        return 1
    
    try:
        new_pw = getpass.getpass(f"Mật khẩu mới cho {target}: ")
        confirm = getpass.getpass("Xác nhận mật khẩu: ")
    except (EOFError, KeyboardInterrupt):
        print("\nHủy.")
        return 1
    
    if new_pw != confirm:
        print("⛔ Mật khẩu không khớp")
        return 1
    
    if len(new_pw) < 6:
        print("⛔ Mật khẩu phải ít nhất 6 ký tự")
        return 1
    
    import hashlib
    pw_hash = hashlib.sha256(f"viron_maha:{new_pw}".encode()).hexdigest()
    mgr.change_password(target, pw_hash)
    print(f"✓ Đã đổi mật khẩu cho '{target}'")
    return 0


def _user_info(args: Sequence[str]) -> int:
    """Thông tin chi tiết về người dùng."""
    if not args:
        print("Cú pháp: user info <username>")
        return 1

    mgr = get_identity_manager()
    user = mgr.get_user(args[0])
    if user is None:
        print(f"Không tìm thấy '{args[0]}'")
        return 1

    role_names = {
        UserRole.GUEST: "Khách",
        UserRole.USER: "Người dùng",
        UserRole.MAHA_MEMBER: "Maha member",
        UserRole.ADMIN: "Quản trị",
        UserRole.MAHAVIR: "MAHAVIR ✦",
    }

    print(f"Username: {user.username}")
    print(f"UID:      {user.uid}")
    print(f"Role:     {role_names.get(user.role, user.role.name)}")
    print(f"Groups:   {', '.join(user.groups) if user.groups else '(không)'}")
    print(f"Home:     {user.home_dir}")
    print(f"Shell:    {user.shell}")
    print(f"Mahavir:  {'✓' if user.is_mahavir else '✗'}")
    print(f"Maha:     {'✓' if user.can_maha else '✗'}")
    return 0


def _user_groups(args: Sequence[str]) -> int:
    """Liệt kê nhóm."""
    mgr = get_identity_manager()
    
    if args:
        user = mgr.get_user(args[0])
        if user:
            print(f"Nhóm của {user.username}: {', '.join(user.groups) if user.groups else '(không)'}")
        else:
            print(f"Không tìm thấy '{args[0]}'")
            return 1
    else:
        groups = mgr.list_groups()
        print(f"{'GID':>5}  {'Group':<20}  {'Members'}")
        print("-" * 55)
        for g in groups:
            members = ", ".join(g.members) if g.members else "-"
            print(f"{g.gid:>5}  {g.name:<20}  {members}")
    return 0


def _user_addgroup(args: Sequence[str]) -> int:
    """Thêm user vào nhóm."""
    if len(args) < 2:
        print("Cú pháp: user addgroup <username> <group>")
        return 1
    
    username, group = args[0], args[1]
    mgr = get_identity_manager()
    
    if mgr.add_user_to_group(username, group):
        print(f"✓ Đã thêm '{username}' vào nhóm '{group}'")
    else:
        print(f"⛔ Không tìm thấy user hoặc nhóm")
        return 1
    return 0


def _user_maha_add(args: Sequence[str]) -> int:
    """Cấp quyền maha cho user."""
    if not args:
        print("Cú pháp: user maha-add <username>")
        return 1
    
    username = args[0]
    mgr = get_identity_manager()
    
    user = mgr.get_user(username)
    if user is None:
        print(f"Không tìm thấy '{username}'")
        return 1
    
    mgr.add_user_to_group(username, "maha")
    mgr.set_role(username, UserRole.MAHA_MEMBER)
    print(f"✓ Đã cấp quyền maha cho '{username}'")
    print(f"  {username} giờ có thể dùng 'maha' để nâng quyền")
    return 0


def register_user_commands() -> None:
    """Đăng ký lệnh user."""
    register_command(
        name="user",
        description="Quản lý người dùng (mahavir = user tối cao)",
        usage="user <subcommand> [args...]",
        handler=cmd_user,
        category="user",
    )
    register_command(name="user-add", description="Tạo người dùng",
                     usage="user add <name>", handler=lambda a: _user_add(a),
                     category="user", requires_maha=True)
    register_command(name="user-del", description="Xoá người dùng",
                     usage="user del <name>", handler=lambda a: _user_del(a),
                     category="user", requires_maha=True)
    register_command(name="user-passwd", description="Đổi mật khẩu",
                     usage="user passwd [name]", handler=lambda a: _user_passwd(a),
                     category="user")
    register_command(name="user-whoami", description="Ai đang đăng nhập",
                     usage="user whoami", handler=lambda a: _user_whoami(a),
                     category="user")
    
    register_alias("useradd", "user-add")
    register_alias("userdel", "user-del")
    register_alias("passwd", "user-passwd")
    register_alias("whoami", "user-whoami")
