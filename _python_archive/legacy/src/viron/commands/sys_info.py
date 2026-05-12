"""
sys_info — Thông tin hệ thống.
================================
Cú pháp:
    sys info               → Thông tin tổng quan
    sys host               → Hostname
    sys cpu                → Thông tin CPU
    sys mem                → Thông tin bộ nhớ
    sys os                 → Thông tin OS
    sys uptime             → Thời gian chạy
    sys env                → Biến môi trường
    sys env set <k> <v>    → Đặt biến môi trường
    sys version            → Phiên bản Viron
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
import time
from typing import Sequence

from .. import __version__
from ..registry import register_command, register_alias


def cmd_sys(args: Sequence[str]) -> int:
    """Handler chính cho lệnh sys."""
    if not args:
        return _sys_info([])
    
    subcmd = args[0]
    subargs = args[1:]
    
    handlers = {
        "info": _sys_info,
        "host": _sys_host,
        "cpu": _sys_cpu,
        "mem": _sys_mem,
        "os": _sys_os,
        "uptime": _sys_uptime,
        "env": _sys_env,
        "version": _sys_version,
        "help": lambda _: _sys_help(),
    }
    
    handler = handlers.get(subcmd)
    if handler is None:
        print(f"Lệnh con không hợp lệ: '{subcmd}'")
        return _sys_help()
    
    return handler(subargs)


def _sys_help() -> int:
    print("sys — Thông tin hệ thống")
    print()
    print("  sys info         Tổng quan")
    print("  sys host         Hostname")
    print("  sys cpu          CPU")
    print("  sys mem          Bộ nhớ")
    print("  sys os           Hệ điều hành")
    print("  sys uptime       Thời gian chạy")
    print("  sys env          Biến môi trường")
    print("  sys version      Phiên bản Viron")
    return 0


def _sys_info(args: Sequence[str]) -> int:
    """Thông tin tổng quan hệ thống."""
    print(f"╔══════════════════════════════════════╗")
    print(f"║         Viron System Info            ║")
    print(f"╠══════════════════════════════════════╣")
    print(f"║  Viron:     v{__version__:<23}║")
    print(f"║  OS:        {platform.system():<24}║")
    print(f"║  Release:   {platform.release():<24}║")
    print(f"║  Machine:   {platform.machine():<24}║")
    print(f"║  Hostname:  {platform.node():<24}║")
    print(f"║  Python:    {platform.python_version():<24}║")
    print(f"║  User:      {os.environ.get('USER', 'unknown'):<24}║")
    print(f"╚══════════════════════════════════════╝")
    return 0


def _sys_host(args: Sequence[str]) -> int:
    """Hostname."""
    if args and args[0] == "set" and len(args) > 1:
        print(f"Đổi hostname: cần quyền maha")
        print(f"Thử: maha sys host set {args[1]}")
        return 1
    print(platform.node())
    return 0


def _sys_cpu(args: Sequence[str]) -> int:
    """Thông tin CPU."""
    system = platform.system()
    
    print(f"Architecture: {platform.machine()}")
    print(f"Processor:    {platform.processor()}")
    
    if system == "Darwin":
        result = subprocess.run(
            ["sysctl", "-n", "machdep.cpu.brand_string"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            print(f"CPU:          {result.stdout.strip()}")
        
        result = subprocess.run(
            ["sysctl", "-n", "hw.ncpu"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            print(f"Cores:        {result.stdout.strip()}")
    elif system == "Linux":
        result = subprocess.run(
            ["lscpu"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            print(result.stdout)
    return 0


def _sys_mem(args: Sequence[str]) -> int:
    """Thông tin bộ nhớ."""
    system = platform.system()
    
    if system == "Darwin":
        result = subprocess.run(
            ["sysctl", "-n", "hw.memsize"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            total = int(result.stdout.strip())
            print(f"Tổng RAM: {total / (1024**3):.1f} GB")
        
        result = subprocess.run(
            ["vm_stat"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            print(result.stdout)
    elif system == "Linux":
        result = subprocess.run(
            ["free", "-h"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            print(result.stdout)
    return 0


def _sys_os(args: Sequence[str]) -> int:
    """Thông tin OS."""
    print(f"Hệ thống:   {platform.system()}")
    print(f"Release:     {platform.release()}")
    print(f"Version:     {platform.version()}")
    print(f"Machine:     {platform.machine()}")
    print(f"Platform:    {platform.platform()}")
    return 0


def _sys_uptime(args: Sequence[str]) -> int:
    """Thời gian chạy."""
    result = subprocess.run(
        ["uptime"], capture_output=True, text=True, timeout=5
    )
    if result.returncode == 0:
        print(result.stdout.strip())
    return 0


def _sys_env(args: Sequence[str]) -> int:
    """Biến môi trường."""
    if not args:
        for key, val in sorted(os.environ.items()):
            print(f"  {key}={val}")
        return 0
    
    if args[0] == "set" and len(args) >= 3:
        key, val = args[1], args[2]
        os.environ[key] = val
        print(f"✓ {key}={val}")
        return 0
    
    if args[0] == "get" and len(args) >= 2:
        val = os.environ.get(args[1])
        if val is not None:
            print(f"{args[1]}={val}")
        else:
            print(f"{args[1]}: không tồn tại")
        return 0
    
    # Tìm kiếm
    query = args[0].lower()
    for key, val in sorted(os.environ.items()):
        if query in key.lower() or query in val.lower():
            print(f"  {key}={val}")
    return 0


def _sys_version(args: Sequence[str]) -> int:
    """Phiên bản Viron."""
    print(f"Viron v{__version__}")
    print(f"Python {platform.python_version()}")
    print(f"Platform {platform.platform()}")
    return 0


def register_sys_commands() -> None:
    """Đăng ký lệnh sys."""
    register_command(
        name="sys",
        description="Thông tin hệ thống",
        usage="sys <subcommand>",
        handler=cmd_sys,
        category="system",
    )
    register_command(name="sys-info", description="Thông tin hệ thống",
                     usage="sys info", handler=lambda a: _sys_info(a),
                     category="system")
    register_command(name="sys-host", description="Hostname",
                     usage="sys host", handler=lambda a: _sys_host(a),
                     category="system")
    
    register_alias("uname", "sys-info")
    register_alias("hostname", "sys-host")
