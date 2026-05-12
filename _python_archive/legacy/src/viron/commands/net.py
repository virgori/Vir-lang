"""
net — Lệnh quản lý mạng.
===========================
Thay thế ifconfig/ip. Quản lý interface, IP, DNS, routing, kết nối.

Cú pháp:
    net list                    → Liệt kê các interface mạng
    net show <iface>            → Thông tin chi tiết interface
    net up <iface>              → Bật interface
    net down <iface>            → Tắt interface
    net ip <iface>              → Hiển thị IP
    net ip set <iface> <ip>     → Đặt IP
    net dns                     → Hiển thị DNS
    net dns set <server>        → Đặt DNS server
    net route                   → Hiển thị bảng routing
    net stat                    → Thống kê kết nối (thay netstat/ss)
    net ping <host>             → Ping host
    net trace <host>            → Traceroute
    net scan <range>            → Quét mạng
    net restart <iface>         → Khởi động lại interface
"""

from __future__ import annotations

import platform
import socket
import struct
import subprocess
import sys
from typing import Sequence

from ..registry import register_command, register_alias


def cmd_net(args: Sequence[str]) -> int:
    """Handler chính cho lệnh net."""
    if not args:
        return _net_help()
    
    subcmd = args[0]
    subargs = args[1:]
    
    handlers = {
        "list": _net_list,
        "show": _net_show,
        "up": _net_up,
        "down": _net_down,
        "ip": _net_ip,
        "dns": _net_dns,
        "route": _net_route,
        "stat": _net_stat,
        "ping": _net_ping,
        "trace": _net_trace,
        "restart": _net_restart,
        "scan": _net_scan,
        "help": lambda _: _net_help(),
    }
    
    handler = handlers.get(subcmd)
    if handler is None:
        print(f"Lệnh con không hợp lệ: '{subcmd}'")
        return _net_help()
    
    return handler(subargs)


def _net_help() -> int:
    print("net — Quản lý mạng")
    print()
    print("Cú pháp:")
    print("  net list                  Liệt kê interfaces")
    print("  net show <iface>          Chi tiết interface")
    print("  net up <iface>            Bật interface")
    print("  net down <iface>          Tắt interface")
    print("  net ip <iface>            Hiển thị IP")
    print("  net ip set <iface> <ip>   Đặt IP")
    print("  net dns                   Hiển thị DNS servers")
    print("  net dns set <server>      Đặt DNS server")
    print("  net route                 Bảng routing")
    print("  net stat                  Thống kê kết nối")
    print("  net ping <host>           Ping host")
    print("  net trace <host>          Traceroute")
    print("  net restart <iface>       Khởi động lại interface")
    print("  net scan <range>          Quét mạng")
    return 0


def _net_list(args: Sequence[str]) -> int:
    """Liệt kê các interface mạng."""
    system = platform.system()
    
    if system == "Darwin":
        result = subprocess.run(
            ["networksetup", "-listallhardwareports"],
            capture_output=True, text=True, timeout=10
        )
    elif system == "Linux":
        result = subprocess.run(
            ["ip", "-brief", "link", "show"],
            capture_output=True, text=True, timeout=10
        )
    else:
        # Fallback: dùng socket
        print("Interface mạng:")
        hostname = socket.gethostname()
        try:
            ip = socket.gethostbyname(hostname)
            print(f"  {hostname}: {ip}")
        except socket.error:
            print(f"  {hostname}: (không thể lấy IP)")
        return 0
    
    if result.returncode == 0:
        print("Interfaces mạng:")
        print(result.stdout)
    else:
        print(f"Lỗi: {result.stderr}")
    return result.returncode


def _net_show(args: Sequence[str]) -> int:
    """Hiển thị chi tiết interface."""
    if not args:
        print("Cú pháp: net show <interface>")
        return 1
    
    iface = args[0]
    system = platform.system()
    
    if system == "Darwin":
        result = subprocess.run(
            ["ifconfig", iface],
            capture_output=True, text=True, timeout=10
        )
    else:
        result = subprocess.run(
            ["ip", "addr", "show", iface],
            capture_output=True, text=True, timeout=10
        )
    
    if result.returncode == 0:
        print(f"Interface: {iface}")
        print(result.stdout)
    else:
        print(f"Lỗi: {result.stderr.strip()}")
    return result.returncode


def _net_up(args: Sequence[str]) -> int:
    """Bật interface (cần quyền maha)."""
    if not args:
        print("Cú pháp: net up <interface>")
        return 1
    iface = args[0]
    system = platform.system()
    
    if system == "Darwin":
        cmd = ["networksetup", "-setnetworkserviceenabled", iface, "on"]
    else:
        cmd = ["ip", "link", "set", iface, "up"]
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    if result.returncode == 0:
        print(f"✓ Interface {iface} đã bật")
    else:
        print(f"⛔ Lỗi: {result.stderr.strip()}")
        print("Thử chạy với 'maha net up " + iface + "'")
    return result.returncode


def _net_down(args: Sequence[str]) -> int:
    """Tắt interface (cần quyền maha)."""
    if not args:
        print("Cú pháp: net down <interface>")
        return 1
    iface = args[0]
    system = platform.system()
    
    if system == "Darwin":
        cmd = ["networksetup", "-setnetworkserviceenabled", iface, "off"]
    else:
        cmd = ["ip", "link", "set", iface, "down"]
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    if result.returncode == 0:
        print(f"✓ Interface {iface} đã tắt")
    else:
        print(f"⛔ Lỗi: {result.stderr.strip()}")
    return result.returncode


def _net_ip(args: Sequence[str]) -> int:
    """Hiển thị hoặc đặt IP."""
    if not args:
        # Hiển thị tất cả IP
        hostname = socket.gethostname()
        try:
            addrs = socket.getaddrinfo(hostname, None, socket.AF_INET)
            print("Địa chỉ IP:")
            seen: set[str] = set()
            for addr in addrs:
                ip = addr[4][0]
                if ip not in seen:
                    seen.add(ip)
                    print(f"  {ip}")
        except socket.error as e:
            print(f"Lỗi: {e}")
        return 0
    
    if args[0] == "set" and len(args) >= 3:
        iface, ip_addr = args[1], args[2]
        system = platform.system()
        if system == "Darwin":
            cmd = ["ifconfig", iface, "inet", ip_addr]
        else:
            cmd = ["ip", "addr", "add", ip_addr, "dev", iface]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print(f"✓ Đã đặt IP {ip_addr} cho {iface}")
        else:
            print(f"⛔ Lỗi: {result.stderr.strip()}")
        return result.returncode
    
    # net ip <iface>
    return _net_show(args)


def _net_dns(args: Sequence[str]) -> int:
    """Hiển thị hoặc đặt DNS server."""
    if not args:
        # Hiển thị DNS servers
        system = platform.system()
        if system == "Darwin":
            result = subprocess.run(
                ["scutil", "--dns"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                print("DNS Servers:")
                for line in result.stdout.splitlines():
                    if "nameserver" in line:
                        print(f"  {line.strip()}")
        elif system == "Linux":
            try:
                with open("/etc/resolv.conf") as f:
                    print("DNS Servers:")
                    for line in f:
                        if line.startswith("nameserver"):
                            print(f"  {line.strip()}")
            except FileNotFoundError:
                print("Không tìm thấy /etc/resolv.conf")
        return 0
    
    if args[0] == "set" and len(args) >= 2:
        server = args[1]
        print(f"Đặt DNS server: {server}")
        print("(Cần quyền maha để thay đổi DNS)")
        return 0
    
    return 0


def _net_route(args: Sequence[str]) -> int:
    """Hiển thị bảng routing."""
    system = platform.system()
    if system == "Darwin":
        cmd = ["netstat", "-rn"]
    else:
        cmd = ["ip", "route", "show"]
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    if result.returncode == 0:
        print("Bảng routing:")
        print(result.stdout)
    else:
        print(f"Lỗi: {result.stderr.strip()}")
    return result.returncode


def _net_stat(args: Sequence[str]) -> int:
    """Thống kê kết nối mạng (thay netstat/ss)."""
    system = platform.system()
    
    flags = ["-an"]
    if args:
        if "-t" in args:
            flags.append("-p tcp" if system == "Darwin" else "-t")
        if "-u" in args:
            flags.append("-p udp" if system == "Darwin" else "-u")
        if "-l" in args:
            flags = ["-ln"]
    
    if system == "Darwin":
        cmd = ["netstat"] + flags
    else:
        cmd = ["ss"] + flags
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    if result.returncode == 0:
        print("Kết nối mạng:")
        # Giới hạn output
        lines = result.stdout.splitlines()
        for line in lines[:50]:
            print(f"  {line}")
        if len(lines) > 50:
            print(f"  ... và {len(lines) - 50} dòng nữa")
    else:
        print(f"Lỗi: {result.stderr.strip()}")
    return result.returncode


def _net_ping(args: Sequence[str]) -> int:
    """Ping host."""
    if not args:
        print("Cú pháp: net ping <host> [-c <count>]")
        return 1
    
    host = args[0]
    count = "4"
    if "-c" in args:
        idx = list(args).index("-c")
        if idx + 1 < len(args):
            count = args[idx + 1]
    
    cmd = ["ping", "-c", count, host]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode == 0:
        print(result.stdout)
    else:
        print(f"⛔ Không thể ping {host}")
        if result.stderr:
            print(result.stderr.strip())
    return result.returncode


def _net_trace(args: Sequence[str]) -> int:
    """Traceroute."""
    if not args:
        print("Cú pháp: net trace <host>")
        return 1
    
    host = args[0]
    system = platform.system()
    cmd_name = "traceroute" if system != "Windows" else "tracert"
    
    result = subprocess.run(
        [cmd_name, host],
        capture_output=True, text=True, timeout=60
    )
    print(result.stdout)
    return result.returncode


def _net_restart(args: Sequence[str]) -> int:
    """Khởi động lại interface."""
    if not args:
        print("Cú pháp: net restart <interface>")
        return 1
    
    iface = args[0]
    print(f"Đang khởi động lại {iface}...")
    
    rc = _net_down([iface])
    if rc != 0:
        return rc
    
    import time
    time.sleep(1)
    
    return _net_up([iface])


def _net_scan(args: Sequence[str]) -> int:
    """Quét mạng cơ bản."""
    if not args:
        print("Cú pháp: net scan <ip-range>")
        print("Ví dụ:   net scan 192.168.1.0/24")
        return 1
    
    target = args[0]
    print(f"Đang quét mạng {target}...")
    
    # Quét cơ bản bằng socket
    if "/" not in target:
        # Single host
        try:
            hostname = socket.gethostbyaddr(target)
            print(f"  {target}: {hostname[0]}")
        except socket.herror:
            print(f"  {target}: (không phân giải được)")
        return 0
    
    # Range scan — chỉ thử ping
    base = target.split("/")[0]
    parts = base.split(".")
    if len(parts) != 4:
        print("Định dạng IP không hợp lệ")
        return 1
    
    prefix = ".".join(parts[:3])
    found = 0
    print(f"Quét {prefix}.1 → {prefix}.254")
    
    for i in range(1, 255):
        ip = f"{prefix}.{i}"
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.1)
            result = sock.connect_ex((ip, 80))
            sock.close()
            if result == 0:
                print(f"  ✓ {ip}: mở cổng 80")
                found += 1
        except (socket.error, OSError):
            pass
    
    print(f"Tìm thấy {found} host hoạt động")
    return 0


def register_net_commands() -> None:
    """Đăng ký lệnh net vào registry."""
    register_command(
        name="net",
        description="Quản lý mạng (thay ifconfig/ip)",
        usage="net <subcommand> [args...]",
        handler=cmd_net,
        category="network",
    )
    register_command(
        name="net-stat",
        description="Thống kê kết nối mạng (thay netstat/ss)",
        usage="net stat [-t] [-u] [-l]",
        handler=lambda args: _net_stat(args),
        category="network",
    )
    
    # Alias tương thích
    register_alias("ifconfig", "net")
    register_alias("ip", "net")
    register_alias("netstat", "net-stat")
    register_alias("ss", "net-stat")
