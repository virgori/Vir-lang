"""
Viron Alias Engine — Zero-cost Command Mapping.
=================================================
Hỗ trợ alias lệnh từ config file mà không ảnh hưởng hiệu năng.
Alias được bake vào registry tại thời điểm khởi tạo, không có
string matching hay redirect nào tại runtime.

Config format (viron_aliases.conf):
    # alias → canonical
    sudo = maha
    ifconfig = net
    su = maha-su
    root = mahavir
"""

from __future__ import annotations

import os
from pathlib import Path

from .registry import get_registry


# Đường dẫn mặc định cho alias config
_DEFAULT_ALIAS_PATHS = [
    Path("/etc/viron/aliases.conf"),
    Path.home() / ".config" / "viron" / "aliases.conf",
    Path.home() / ".viron_aliases",
]


def _parse_alias_file(path: Path) -> dict[str, str]:
    """Parse alias config file. Format: alias = canonical (mỗi dòng)."""
    aliases: dict[str, str] = {}
    if not path.is_file():
        return aliases
    with open(path, encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            parts = line.split("=", 1)
            alias_name = parts[0].strip()
            canonical = parts[1].strip()
            if alias_name and canonical:
                aliases[alias_name] = canonical
    return aliases


def load_aliases(extra_paths: list[Path] | None = None) -> int:
    """
    Load alias từ config files và đăng ký vào registry.
    
    Trả về số alias đã load thành công.
    Alias files được đọc theo thứ tự ưu tiên (system → user → local).
    """
    registry = get_registry()
    paths = list(_DEFAULT_ALIAS_PATHS)
    if extra_paths:
        paths.extend(extra_paths)
    
    # Biến môi trường cho alias file bổ sung
    env_path = os.environ.get("VIRON_ALIAS_FILE")
    if env_path:
        paths.append(Path(env_path))
    
    loaded = 0
    all_aliases: dict[str, str] = {}
    
    for path in paths:
        file_aliases = _parse_alias_file(path)
        all_aliases.update(file_aliases)  # Later files override earlier
    
    for alias_name, canonical in all_aliases.items():
        try:
            registry.alias(alias_name, canonical)
            loaded += 1
        except KeyError:
            # Lệnh gốc chưa đăng ký → bỏ qua alias này
            pass
    
    return loaded


def register_default_aliases() -> None:
    """
    Đăng ký bộ alias mặc định cho tương thích Unix/Linux.
    
    Cho phép người dùng quen với Linux dùng lệnh cũ.
    Alias chỉ là thêm key vào dict → zero-cost.
    """
    registry = get_registry()
    
    default_map = {
        # Unix compatibility aliases
        "sudo": "maha",
        "su": "maha-su",
        "ifconfig": "net",
        "ip": "net",
        "netstat": "net-stat",
        "ss": "net-stat",
        "ps": "proc",
        "kill": "proc-kill",
        "top": "proc-top",
        "ls": "fs-list",
        "cp": "fs-copy",
        "mv": "fs-move",
        "rm": "fs-remove",
        "mkdir": "fs-mkdir",
        "cat": "fs-read",
        "chmod": "fs-chmod",
        "chown": "fs-chown",
        "systemctl": "svc",
        "service": "svc",
        "apt": "pkg",
        "brew": "pkg",
        "useradd": "user-add",
        "userdel": "user-del",
        "passwd": "user-passwd",
        "whoami": "user-whoami",
        "uname": "sys-info",
        "hostname": "sys-host",
        "df": "fs-disk",
        "du": "fs-usage",
        "mount": "fs-mount",
        "umount": "fs-umount",
    }
    
    for alias_name, canonical in default_map.items():
        try:
            registry.alias(alias_name, canonical)
        except KeyError:
            pass  # Lệnh chưa đăng ký → skip


class AliasProfile:
    """
    Alias profile — cho phép chuyển đổi giữa các bộ lệnh.
    
    Ví dụ: profile "linux" map tất cả lệnh Linux cũ,
    profile "minimal" chỉ giữ lệnh Viron gốc.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self._mappings: dict[str, str] = {}

    def add(self, alias: str, canonical: str) -> None:
        self._mappings[alias] = canonical

    def apply(self) -> int:
        """Apply profile vào global registry. Trả về số alias loaded."""
        registry = get_registry()
        count = 0
        for alias_name, canonical in self._mappings.items():
            try:
                registry.alias(alias_name, canonical)
                count += 1
            except KeyError:
                pass
        return count

    @property
    def mappings(self) -> dict[str, str]:
        return dict(self._mappings)


# Built-in profiles
def linux_profile() -> AliasProfile:
    """Profile tương thích đầy đủ Linux."""
    p = AliasProfile("linux")
    for alias, canon in {
        "sudo": "maha", "su": "maha-su", "ifconfig": "net", "ip": "net",
        "ps": "proc", "kill": "proc-kill", "top": "proc-top",
        "ls": "fs-list", "cp": "fs-copy", "mv": "fs-move", "rm": "fs-remove",
        "systemctl": "svc", "apt": "pkg", "useradd": "user-add",
    }.items():
        p.add(alias, canon)
    return p


def macos_profile() -> AliasProfile:
    """Profile tương thích macOS."""
    p = AliasProfile("macos")
    for alias, canon in {
        "sudo": "maha", "ifconfig": "net", "networksetup": "net",
        "ps": "proc", "kill": "proc-kill", "top": "proc-top",
        "ls": "fs-list", "cp": "fs-copy", "mv": "fs-move", "rm": "fs-remove",
        "launchctl": "svc", "brew": "pkg", "dscl": "user-add",
    }.items():
        p.add(alias, canon)
    return p


def minimal_profile() -> AliasProfile:
    """Profile tối giản — chỉ dùng tên Viron gốc, không alias."""
    return AliasProfile("minimal")
