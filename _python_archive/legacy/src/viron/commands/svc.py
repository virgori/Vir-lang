"""
svc — Quản lý dịch vụ hệ thống.
==================================
Thay thế systemctl/launchctl/service.

Cú pháp:
    svc list                → Liệt kê dịch vụ
    svc status <name>       → Trạng thái dịch vụ
    svc start <name>        → Khởi động dịch vụ
    svc stop <name>         → Dừng dịch vụ
    svc restart <name>      → Khởi động lại
    svc enable <name>       → Bật tự khởi động
    svc disable <name>      → Tắt tự khởi động
    svc log <name>          → Xem log dịch vụ
"""

from __future__ import annotations

import platform
import subprocess
from typing import Sequence

from ..registry import register_command, register_alias


def cmd_svc(args: Sequence[str]) -> int:
    """Handler chính cho lệnh svc."""
    if not args:
        return _svc_list([])
    
    subcmd = args[0]
    subargs = args[1:]
    
    handlers = {
        "list": _svc_list,
        "status": _svc_status,
        "start": _svc_start,
        "stop": _svc_stop,
        "restart": _svc_restart,
        "enable": _svc_enable,
        "disable": _svc_disable,
        "log": _svc_log,
        "help": lambda _: _svc_help(),
    }
    
    handler = handlers.get(subcmd)
    if handler is None:
        # Coi như svc status <name>
        return _svc_status([subcmd])
    
    return handler(subargs)


def _svc_help() -> int:
    print("svc — Quản lý dịch vụ")
    print()
    print("  svc list              Liệt kê dịch vụ")
    print("  svc status <name>     Trạng thái")
    print("  svc start <name>      Khởi động")
    print("  svc stop <name>       Dừng")
    print("  svc restart <name>    Khởi động lại")
    print("  svc enable <name>     Bật tự khởi động")
    print("  svc disable <name>    Tắt tự khởi động")
    print("  svc log <name>        Xem log")
    return 0


def _get_svc_backend() -> str:
    """Xác định backend quản lý dịch vụ của OS."""
    system = platform.system()
    if system == "Darwin":
        return "launchctl"
    # Linux: kiểm tra systemd
    try:
        result = subprocess.run(
            ["systemctl", "--version"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return "systemd"
    except FileNotFoundError:
        pass
    return "generic"


def _svc_list(args: Sequence[str]) -> int:
    """Liệt kê dịch vụ."""
    backend = _get_svc_backend()
    
    if backend == "launchctl":
        result = subprocess.run(
            ["launchctl", "list"],
            capture_output=True, text=True, timeout=10
        )
    elif backend == "systemd":
        result = subprocess.run(
            ["systemctl", "list-units", "--type=service", "--no-pager"],
            capture_output=True, text=True, timeout=10
        )
    else:
        print("Không xác định được hệ thống quản lý dịch vụ")
        return 1
    
    if result.returncode == 0:
        print("Dịch vụ hệ thống:")
        lines = result.stdout.splitlines()
        for line in lines[:40]:
            print(f"  {line}")
        if len(lines) > 40:
            print(f"  ... và {len(lines) - 40} dịch vụ nữa")
    return result.returncode


def _svc_status(args: Sequence[str]) -> int:
    """Trạng thái dịch vụ."""
    if not args:
        print("Cú pháp: svc status <name>")
        return 1
    
    name = args[0]
    backend = _get_svc_backend()
    
    if backend == "launchctl":
        result = subprocess.run(
            ["launchctl", "print", f"system/{name}"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            result = subprocess.run(
                ["launchctl", "print", f"gui/{_get_uid()}/{name}"],
                capture_output=True, text=True, timeout=10
            )
    elif backend == "systemd":
        result = subprocess.run(
            ["systemctl", "status", name, "--no-pager"],
            capture_output=True, text=True, timeout=10
        )
    else:
        print(f"Không thể kiểm tra dịch vụ '{name}'")
        return 1
    
    if result.returncode == 0:
        print(result.stdout)
    else:
        print(f"Dịch vụ '{name}': {result.stderr.strip() or 'không tìm thấy'}")
    return result.returncode


def _svc_start(args: Sequence[str]) -> int:
    """Khởi động dịch vụ."""
    if not args:
        print("Cú pháp: svc start <name>")
        return 1
    
    name = args[0]
    backend = _get_svc_backend()
    
    if backend == "launchctl":
        cmd = ["launchctl", "kickstart", f"system/{name}"]
    elif backend == "systemd":
        cmd = ["systemctl", "start", name]
    else:
        print("Backend không được hỗ trợ")
        return 1
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    if result.returncode == 0:
        print(f"✓ Dịch vụ '{name}' đã khởi động")
    else:
        print(f"⛔ Lỗi: {result.stderr.strip()}")
        print(f"Thử: maha svc start {name}")
    return result.returncode


def _svc_stop(args: Sequence[str]) -> int:
    """Dừng dịch vụ."""
    if not args:
        print("Cú pháp: svc stop <name>")
        return 1
    
    name = args[0]
    backend = _get_svc_backend()
    
    if backend == "launchctl":
        cmd = ["launchctl", "kill", "SIGTERM", f"system/{name}"]
    elif backend == "systemd":
        cmd = ["systemctl", "stop", name]
    else:
        return 1
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    if result.returncode == 0:
        print(f"✓ Dịch vụ '{name}' đã dừng")
    else:
        print(f"⛔ Lỗi: {result.stderr.strip()}")
    return result.returncode


def _svc_restart(args: Sequence[str]) -> int:
    """Khởi động lại dịch vụ."""
    if not args:
        print("Cú pháp: svc restart <name>")
        return 1
    
    name = args[0]
    backend = _get_svc_backend()
    
    if backend == "systemd":
        cmd = ["systemctl", "restart", name]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    else:
        _svc_stop(args)
        import time
        time.sleep(1)
        return _svc_start(args)
    
    if result.returncode == 0:
        print(f"✓ Dịch vụ '{name}' đã khởi động lại")
    else:
        print(f"⛔ Lỗi: {result.stderr.strip()}")
    return result.returncode


def _svc_enable(args: Sequence[str]) -> int:
    """Bật tự khởi động."""
    if not args:
        print("Cú pháp: svc enable <name>")
        return 1
    
    name = args[0]
    backend = _get_svc_backend()
    
    if backend == "systemd":
        cmd = ["systemctl", "enable", name]
    elif backend == "launchctl":
        cmd = ["launchctl", "enable", f"system/{name}"]
    else:
        return 1
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    if result.returncode == 0:
        print(f"✓ Dịch vụ '{name}' sẽ tự khởi động")
    else:
        print(f"⛔ Lỗi: {result.stderr.strip()}")
    return result.returncode


def _svc_disable(args: Sequence[str]) -> int:
    """Tắt tự khởi động."""
    if not args:
        print("Cú pháp: svc disable <name>")
        return 1
    
    name = args[0]
    backend = _get_svc_backend()
    
    if backend == "systemd":
        cmd = ["systemctl", "disable", name]
    elif backend == "launchctl":
        cmd = ["launchctl", "disable", f"system/{name}"]
    else:
        return 1
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    if result.returncode == 0:
        print(f"✓ Dịch vụ '{name}' sẽ không tự khởi động")
    else:
        print(f"⛔ Lỗi: {result.stderr.strip()}")
    return result.returncode


def _svc_log(args: Sequence[str]) -> int:
    """Xem log dịch vụ."""
    if not args:
        print("Cú pháp: svc log <name>")
        return 1
    
    name = args[0]
    backend = _get_svc_backend()
    
    if backend == "systemd":
        cmd = ["journalctl", "-u", name, "-n", "50", "--no-pager"]
    elif backend == "launchctl":
        cmd = ["log", "show", "--predicate", f"subsystem==\"{name}\"", "--last", "1h"]
    else:
        return 1
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    if result.returncode == 0:
        print(f"Log của '{name}':")
        print(result.stdout)
    return result.returncode


def _get_uid() -> int:
    """Lấy UID hiện tại."""
    import os
    return os.getuid()


def register_svc_commands() -> None:
    """Đăng ký lệnh svc."""
    register_command(
        name="svc",
        description="Quản lý dịch vụ hệ thống (thay systemctl/launchctl)",
        usage="svc <subcommand> [args...]",
        handler=cmd_svc,
        category="service",
    )
    
    register_alias("systemctl", "svc")
    register_alias("service", "svc")
    register_alias("launchctl", "svc")
