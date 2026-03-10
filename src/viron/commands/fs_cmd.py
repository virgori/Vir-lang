"""
fs — Quản lý hệ thống tệp.
==============================
Cú pháp:
    fs list [path]         → Liệt kê tệp (thay ls)
    fs read <file>         → Đọc nội dung (thay cat)
    fs copy <src> <dst>    → Sao chép (thay cp)
    fs move <src> <dst>    → Di chuyển (thay mv)
    fs remove <path>       → Xoá (thay rm)
    fs mkdir <path>        → Tạo thư mục
    fs chmod <mode> <path> → Đổi quyền
    fs chown <user> <path> → Đổi chủ sở hữu
    fs disk                → Dung lượng đĩa (thay df)
    fs usage <path>        → Dung lượng sử dụng (thay du)
    fs find <name>         → Tìm tệp
    fs mount               → Liệt kê mount points
    fs info <path>         → Thông tin tệp
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path
from typing import Sequence

from ..registry import register_command, register_alias


def cmd_fs(args: Sequence[str]) -> int:
    """Handler chính cho lệnh fs."""
    if not args:
        return _fs_list(["."])
    
    subcmd = args[0]
    subargs = args[1:]
    
    handlers = {
        "list": _fs_list,
        "read": _fs_read,
        "copy": _fs_copy,
        "move": _fs_move,
        "remove": _fs_remove,
        "mkdir": _fs_mkdir,
        "chmod": _fs_chmod,
        "chown": _fs_chown,
        "disk": _fs_disk,
        "usage": _fs_usage,
        "find": _fs_find,
        "mount": _fs_mount,
        "umount": _fs_umount,
        "info": _fs_info,
        "help": lambda _: _fs_help(),
    }
    
    handler = handlers.get(subcmd)
    if handler is None:
        # Nếu là path → list
        if os.path.exists(subcmd):
            return _fs_list([subcmd])
        print(f"Lệnh con không hợp lệ: '{subcmd}'")
        return _fs_help()
    
    return handler(subargs)


def _fs_help() -> int:
    print("fs — Quản lý hệ thống tệp")
    print()
    print("  fs list [path]          Liệt kê tệp")
    print("  fs read <file>          Đọc nội dung")
    print("  fs copy <src> <dst>     Sao chép")
    print("  fs move <src> <dst>     Di chuyển")
    print("  fs remove <path>        Xoá")
    print("  fs mkdir <path>         Tạo thư mục")
    print("  fs chmod <mode> <path>  Đổi quyền")
    print("  fs chown <user> <path>  Đổi chủ sở hữu")
    print("  fs disk                 Dung lượng đĩa")
    print("  fs usage <path>         Dung lượng sử dụng")
    print("  fs find <name>          Tìm tệp")
    print("  fs info <path>          Thông tin tệp")
    return 0


def _fs_list(args: Sequence[str]) -> int:
    """Liệt kê tệp."""
    path = args[0] if args else "."
    target = Path(path)
    
    if not target.exists():
        print(f"Không tồn tại: {path}")
        return 1
    
    if target.is_file():
        st = target.stat()
        print(f"{_format_mode(st.st_mode)}  {st.st_size:>10}  {_format_time(st.st_mtime)}  {target.name}")
        return 0
    
    entries = sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    for entry in entries:
        st = entry.stat()
        indicator = "/" if entry.is_dir() else ""
        print(f"{_format_mode(st.st_mode)}  {st.st_size:>10}  {_format_time(st.st_mtime)}  {entry.name}{indicator}")
    
    print(f"\nTổng: {len(entries)} mục")
    return 0


def _fs_read(args: Sequence[str]) -> int:
    """Đọc nội dung tệp."""
    if not args:
        print("Cú pháp: fs read <file>")
        return 1
    
    path = Path(args[0])
    if not path.is_file():
        print(f"Không phải tệp: {args[0]}")
        return 1
    
    try:
        content = path.read_text(encoding="utf-8")
        print(content)
    except UnicodeDecodeError:
        print(f"Tệp nhị phân: {path.name} ({path.stat().st_size} bytes)")
    return 0


def _fs_copy(args: Sequence[str]) -> int:
    """Sao chép tệp/thư mục."""
    if len(args) < 2:
        print("Cú pháp: fs copy <nguồn> <đích>")
        return 1
    
    src, dst = Path(args[0]), Path(args[1])
    if not src.exists():
        print(f"Không tồn tại: {args[0]}")
        return 1
    
    try:
        if src.is_dir():
            shutil.copytree(str(src), str(dst))
        else:
            shutil.copy2(str(src), str(dst))
        print(f"✓ Đã sao chép {src} → {dst}")
    except (OSError, shutil.Error) as e:
        print(f"⛔ Lỗi: {e}")
        return 1
    return 0


def _fs_move(args: Sequence[str]) -> int:
    """Di chuyển tệp/thư mục."""
    if len(args) < 2:
        print("Cú pháp: fs move <nguồn> <đích>")
        return 1
    
    src, dst = args[0], args[1]
    try:
        shutil.move(src, dst)
        print(f"✓ Đã di chuyển {src} → {dst}")
    except (OSError, shutil.Error) as e:
        print(f"⛔ Lỗi: {e}")
        return 1
    return 0


def _fs_remove(args: Sequence[str]) -> int:
    """Xoá tệp/thư mục."""
    if not args:
        print("Cú pháp: fs remove <path>")
        return 1
    
    path = Path(args[0])
    if not path.exists():
        print(f"Không tồn tại: {args[0]}")
        return 1
    
    # Xác nhận nếu xoá thư mục
    if path.is_dir():
        confirm = "-f" in args
        if not confirm:
            print(f"Xoá thư mục '{path}' và tất cả nội dung? (dùng -f để xác nhận)")
            return 1
        shutil.rmtree(str(path))
    else:
        path.unlink()
    
    print(f"✓ Đã xoá {path}")
    return 0


def _fs_mkdir(args: Sequence[str]) -> int:
    """Tạo thư mục."""
    if not args:
        print("Cú pháp: fs mkdir <path>")
        return 1
    
    path = Path(args[0])
    try:
        path.mkdir(parents=True, exist_ok=True)
        print(f"✓ Đã tạo {path}")
    except OSError as e:
        print(f"⛔ Lỗi: {e}")
        return 1
    return 0


def _fs_chmod(args: Sequence[str]) -> int:
    """Đổi quyền tệp."""
    if len(args) < 2:
        print("Cú pháp: fs chmod <mode> <path>")
        print("Ví dụ:   fs chmod 755 script.sh")
        return 1
    
    mode_str, path = args[0], Path(args[1])
    if not path.exists():
        print(f"Không tồn tại: {args[1]}")
        return 1
    
    try:
        mode = int(mode_str, 8)
        path.chmod(mode)
        print(f"✓ Đã đổi quyền {path} → {mode_str}")
    except (ValueError, OSError) as e:
        print(f"⛔ Lỗi: {e}")
        return 1
    return 0


def _fs_chown(args: Sequence[str]) -> int:
    """Đổi chủ sở hữu (cần maha)."""
    if len(args) < 2:
        print("Cú pháp: fs chown <user>[:<group>] <path>")
        return 1
    
    # Delegate to system chown
    result = subprocess.run(
        ["chown", args[0], args[1]],
        capture_output=True, text=True, timeout=10
    )
    if result.returncode == 0:
        print(f"✓ Đã đổi chủ sở hữu {args[1]} → {args[0]}")
    else:
        print(f"⛔ Lỗi: {result.stderr.strip()}")
        print("Thử: maha fs chown " + " ".join(args))
    return result.returncode


def _fs_disk(args: Sequence[str]) -> int:
    """Dung lượng đĩa."""
    result = subprocess.run(
        ["df", "-h"], capture_output=True, text=True, timeout=10
    )
    if result.returncode == 0:
        print("Dung lượng đĩa:")
        print(result.stdout)
    return result.returncode


def _fs_usage(args: Sequence[str]) -> int:
    """Dung lượng sử dụng."""
    path = args[0] if args else "."
    result = subprocess.run(
        ["du", "-sh", path], capture_output=True, text=True, timeout=30
    )
    if result.returncode == 0:
        print(result.stdout.strip())
    return result.returncode


def _fs_find(args: Sequence[str]) -> int:
    """Tìm tệp."""
    if not args:
        print("Cú pháp: fs find <name> [path]")
        return 1
    
    name = args[0]
    search_path = args[1] if len(args) > 1 else "."
    
    result = subprocess.run(
        ["find", search_path, "-name", f"*{name}*", "-maxdepth", "5"],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode == 0:
        lines = result.stdout.strip().splitlines()
        for line in lines[:50]:
            print(f"  {line}")
        if len(lines) > 50:
            print(f"  ... và {len(lines) - 50} kết quả nữa")
        if not lines:
            print(f"Không tìm thấy '{name}'")
    return 0


def _fs_mount(args: Sequence[str]) -> int:
    """Liệt kê mount points."""
    result = subprocess.run(
        ["mount"], capture_output=True, text=True, timeout=10
    )
    if result.returncode == 0:
        print("Mount points:")
        print(result.stdout)
    return result.returncode


def _fs_umount(args: Sequence[str]) -> int:
    """Unmount (cần maha)."""
    if not args:
        print("Cú pháp: fs umount <mount-point>")
        return 1
    result = subprocess.run(
        ["umount", args[0]], capture_output=True, text=True, timeout=10
    )
    if result.returncode == 0:
        print(f"✓ Đã unmount {args[0]}")
    else:
        print(f"⛔ {result.stderr.strip()}")
    return result.returncode


def _fs_info(args: Sequence[str]) -> int:
    """Thông tin chi tiết tệp."""
    if not args:
        print("Cú pháp: fs info <path>")
        return 1
    
    path = Path(args[0])
    if not path.exists():
        print(f"Không tồn tại: {args[0]}")
        return 1
    
    st = path.stat()
    file_type = "Thư mục" if path.is_dir() else ("Symlink" if path.is_symlink() else "Tệp")
    
    print(f"  Đường dẫn:  {path.resolve()}")
    print(f"  Loại:       {file_type}")
    print(f"  Kích thước: {st.st_size:,} bytes")
    print(f"  Quyền:      {_format_mode(st.st_mode)}")
    print(f"  UID/GID:    {st.st_uid}/{st.st_gid}")
    print(f"  Sửa đổi:   {_format_time(st.st_mtime)}")
    print(f"  Truy cập:   {_format_time(st.st_atime)}")
    print(f"  Tạo:        {_format_time(st.st_ctime)}")
    
    if path.is_dir():
        count = sum(1 for _ in path.iterdir())
        print(f"  Nội dung:   {count} mục")
    return 0


def _format_mode(mode: int) -> str:
    """Format file mode thành chuỗi rwx."""
    parts = []
    for who in (stat.S_IRUSR, stat.S_IWUSR, stat.S_IXUSR,
                stat.S_IRGRP, stat.S_IWGRP, stat.S_IXGRP,
                stat.S_IROTH, stat.S_IWOTH, stat.S_IXOTH):
        parts.append("r" if who in (stat.S_IRUSR, stat.S_IRGRP, stat.S_IROTH) and mode & who else
                     "w" if who in (stat.S_IWUSR, stat.S_IWGRP, stat.S_IWOTH) and mode & who else
                     "x" if mode & who else "-")
    return "".join(parts)


def _format_time(ts: float) -> str:
    """Format timestamp."""
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))


def register_fs_commands() -> None:
    """Đăng ký lệnh fs."""
    register_command(
        name="fs",
        description="Quản lý hệ thống tệp",
        usage="fs <subcommand> [args...]",
        handler=cmd_fs,
        category="filesystem",
    )
    register_command(name="fs-list", description="Liệt kê tệp (thay ls)",
                     usage="fs list [path]", handler=lambda a: _fs_list(a or ["."]),
                     category="filesystem")
    register_command(name="fs-copy", description="Sao chép (thay cp)",
                     usage="fs copy <src> <dst>", handler=lambda a: _fs_copy(a),
                     category="filesystem")
    register_command(name="fs-move", description="Di chuyển (thay mv)",
                     usage="fs move <src> <dst>", handler=lambda a: _fs_move(a),
                     category="filesystem")
    register_command(name="fs-remove", description="Xoá (thay rm)",
                     usage="fs remove <path>", handler=lambda a: _fs_remove(a),
                     category="filesystem")
    register_command(name="fs-mkdir", description="Tạo thư mục",
                     usage="fs mkdir <path>", handler=lambda a: _fs_mkdir(a),
                     category="filesystem")
    register_command(name="fs-chmod", description="Đổi quyền",
                     usage="fs chmod <mode> <path>", handler=lambda a: _fs_chmod(a),
                     category="filesystem")
    register_command(name="fs-chown", description="Đổi chủ sở hữu",
                     usage="fs chown <user> <path>", handler=lambda a: _fs_chown(a),
                     category="filesystem", requires_maha=True)
    register_command(name="fs-disk", description="Dung lượng đĩa (thay df)",
                     usage="fs disk", handler=lambda a: _fs_disk(a),
                     category="filesystem")
    register_command(name="fs-usage", description="Dung lượng (thay du)",
                     usage="fs usage <path>", handler=lambda a: _fs_usage(a),
                     category="filesystem")
    register_command(name="fs-mount", description="Liệt kê mount",
                     usage="fs mount", handler=lambda a: _fs_mount(a),
                     category="filesystem")
    register_command(name="fs-umount", description="Unmount",
                     usage="fs umount <point>", handler=lambda a: _fs_umount(a),
                     category="filesystem", requires_maha=True)
    
    register_command(name="fs-read", description="Đọc tệp (thay cat)",
                     usage="fs read <file>", handler=lambda a: _fs_read(a),
                     category="filesystem")

    # Aliases
    for alias, canonical in [
        ("ls", "fs-list"), ("cp", "fs-copy"), ("mv", "fs-move"),
        ("rm", "fs-remove"), ("mkdir", "fs-mkdir"), ("cat", "fs-read"),
        ("chmod", "fs-chmod"), ("chown", "fs-chown"), ("df", "fs-disk"),
        ("du", "fs-usage"), ("mount", "fs-mount"), ("umount", "fs-umount"),
    ]:
        register_alias(alias, canonical)
