"""
proc — Quản lý tiến trình.
============================
Cú pháp:
    proc                   → Liệt kê tiến trình
    proc top               → Xem tiến trình real-time
    proc show <pid>        → Chi tiết tiến trình
    proc kill <pid>        → Dừng tiến trình
    proc kill -9 <pid>     → Buộc dừng
    proc tree              → Cây tiến trình
    proc find <name>       → Tìm tiến trình theo tên
"""

from __future__ import annotations

import os
import platform
import signal
import subprocess
import sys
from typing import Sequence

from ..registry import register_command, register_alias


def cmd_proc(args: Sequence[str]) -> int:
    """Handler chính cho lệnh proc."""
    if not args:
        return _proc_list([])
    
    subcmd = args[0]
    subargs = args[1:]
    
    handlers = {
        "list": _proc_list,
        "top": _proc_top,
        "show": _proc_show,
        "kill": _proc_kill,
        "tree": _proc_tree,
        "find": _proc_find,
        "help": lambda _: _proc_help(),
    }
    
    handler = handlers.get(subcmd)
    if handler is None:
        # Nếu subcmd là số → coi như proc show <pid>
        if subcmd.isdigit():
            return _proc_show([subcmd])
        print(f"Lệnh con không hợp lệ: '{subcmd}'")
        return _proc_help()
    
    return handler(subargs)


def _proc_help() -> int:
    print("proc — Quản lý tiến trình")
    print()
    print("  proc [list]          Liệt kê tiến trình")
    print("  proc top             Xem real-time")
    print("  proc show <pid>      Chi tiết tiến trình")
    print("  proc kill <pid>      Dừng tiến trình")
    print("  proc kill -9 <pid>   Buộc dừng")
    print("  proc tree            Cây tiến trình")
    print("  proc find <name>     Tìm theo tên")
    return 0


def _proc_list(args: Sequence[str]) -> int:
    """Liệt kê tiến trình."""
    cmd = ["ps", "aux"]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    if result.returncode == 0:
        lines = result.stdout.splitlines()
        # Header + top processes
        if lines:
            print(lines[0])
        for line in lines[1:30]:
            print(line)
        if len(lines) > 30:
            print(f"... và {len(lines) - 30} tiến trình nữa (dùng 'proc find' để lọc)")
    return result.returncode


def _proc_top(args: Sequence[str]) -> int:
    """Xem tiến trình real-time."""
    system = platform.system()
    if system == "Darwin":
        os.execvp("top", ["top", "-l", "1", "-n", "20"])
    else:
        os.execvp("top", ["top", "-b", "-n", "1"])
    return 0


def _proc_show(args: Sequence[str]) -> int:
    """Chi tiết tiến trình."""
    if not args:
        print("Cú pháp: proc show <pid>")
        return 1
    pid = args[0]
    
    system = platform.system()
    if system == "Darwin":
        result = subprocess.run(
            ["ps", "-p", pid, "-o", "pid,ppid,user,%cpu,%mem,stat,start,command"],
            capture_output=True, text=True, timeout=10
        )
    else:
        result = subprocess.run(
            ["ps", "-p", pid, "-o", "pid,ppid,user,%cpu,%mem,stat,start_time,cmd"],
            capture_output=True, text=True, timeout=10
        )
    
    if result.returncode == 0:
        print(result.stdout)
    else:
        print(f"Tiến trình {pid} không tồn tại")
    return result.returncode


def _proc_kill(args: Sequence[str]) -> int:
    """Dừng tiến trình."""
    if not args:
        print("Cú pháp: proc kill [-9] <pid>")
        return 1
    
    sig = signal.SIGTERM
    pid_str = args[0]
    
    if pid_str == "-9" and len(args) > 1:
        sig = signal.SIGKILL
        pid_str = args[1]
    elif pid_str.startswith("-") and len(args) > 1:
        try:
            sig_num = int(pid_str[1:])
            sig = signal.Signals(sig_num)
        except (ValueError, KeyError):
            pass
        pid_str = args[1]
    
    try:
        pid = int(pid_str)
    except ValueError:
        print(f"PID không hợp lệ: {pid_str}")
        return 1
    
    try:
        os.kill(pid, sig)
        print(f"✓ Đã gửi tín hiệu {sig.name} đến tiến trình {pid}")
        return 0
    except ProcessLookupError:
        print(f"Tiến trình {pid} không tồn tại")
        return 1
    except PermissionError:
        print(f"⛔ Không có quyền dừng tiến trình {pid}")
        print(f"Thử: maha proc kill {pid_str}")
        return 1


def _proc_tree(args: Sequence[str]) -> int:
    """Cây tiến trình."""
    system = platform.system()
    if system == "Darwin":
        result = subprocess.run(
            ["pstree"], capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            # pstree có thể chưa cài
            result = subprocess.run(
                ["ps", "-eo", "pid,ppid,command"],
                capture_output=True, text=True, timeout=10
            )
    else:
        result = subprocess.run(
            ["pstree", "-p"], capture_output=True, text=True, timeout=10
        )
    
    if result.returncode == 0:
        print(result.stdout)
    return result.returncode


def _proc_find(args: Sequence[str]) -> int:
    """Tìm tiến trình theo tên."""
    if not args:
        print("Cú pháp: proc find <name>")
        return 1
    
    name = args[0]
    result = subprocess.run(
        ["ps", "aux"],
        capture_output=True, text=True, timeout=10
    )
    
    if result.returncode == 0:
        lines = result.stdout.splitlines()
        if lines:
            print(lines[0])  # Header
        found = 0
        for line in lines[1:]:
            if name.lower() in line.lower():
                print(line)
                found += 1
        if found == 0:
            print(f"Không tìm thấy tiến trình '{name}'")
        else:
            print(f"Tìm thấy {found} tiến trình")
    return result.returncode


def register_proc_commands() -> None:
    """Đăng ký lệnh proc."""
    register_command(
        name="proc",
        description="Quản lý tiến trình",
        usage="proc <subcommand> [args...]",
        handler=cmd_proc,
        category="process",
    )
    register_command(
        name="proc-kill",
        description="Dừng tiến trình",
        usage="proc kill [-9] <pid>",
        handler=lambda args: _proc_kill(args),
        category="process",
    )
    register_command(
        name="proc-top",
        description="Xem tiến trình real-time",
        usage="proc top",
        handler=lambda args: _proc_top(args),
        category="process",
    )
    
    register_alias("ps", "proc")
    register_alias("kill", "proc-kill")
    register_alias("top", "proc-top")
