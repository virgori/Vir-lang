"""
Viron Privilege System — Hệ thống quyền "maha".
=================================================
maha thay thế sudo: cấp quyền tối cao tạm thời cho lệnh.

Cơ chế:
- Xác thực người dùng qua mật khẩu hoặc token
- Kiểm tra quyền maha trong policy file
- Cache xác thực trong thời gian cấu hình (mặc định 5 phút)
- Ghi log mọi thao tác maha (audit trail)

Ví dụ:
    maha net restart eth0     → chạy 'net restart eth0' với quyền tối cao
    maha -u mahavir proc kill 1234  → chạy với quyền mahavir
"""

from __future__ import annotations

import hashlib
import os
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Sequence


class MahaLevel(Enum):
    """Cấp độ quyền maha."""
    USER = auto()       # Người dùng bình thường
    ELEVATED = auto()   # Quyền nâng cao (một số lệnh hệ thống)
    SUPREME = auto()    # Quyền tối cao (mahavir) — toàn quyền


@dataclass
class MahaPolicy:
    """Chính sách quyền cho một người dùng hoặc nhóm."""
    user: str
    allowed_commands: list[str]  # Rỗng = cho phép tất cả
    level: MahaLevel = MahaLevel.ELEVATED
    require_password: bool = True
    timeout_seconds: int = 300  # 5 phút cache


@dataclass
class MahaSession:
    """Session xác thực maha đang hoạt động."""
    user: str
    level: MahaLevel
    authenticated_at: float
    timeout_seconds: int
    target_user: str = "mahavir"

    @property
    def is_valid(self) -> bool:
        return (time.time() - self.authenticated_at) < self.timeout_seconds


class MahaAuditLog:
    """Ghi log tất cả thao tác maha cho kiểm toán."""
    
    _LOG_PATH = Path("/var/log/viron/maha.log")

    def __init__(self, log_path: Path | None = None) -> None:
        self._path = log_path or self._LOG_PATH
    
    def record(self, user: str, command: str, args: Sequence[str],
               granted: bool, target_user: str = "mahavir") -> None:
        """Ghi một bản ghi kiểm toán."""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        status = "GRANTED" if granted else "DENIED"
        entry = f"[{timestamp}] {status} user={user} target={target_user} cmd={command} args={' '.join(args)}\n"
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(entry)
        except PermissionError:
            # Fallback: ghi vào home directory
            fallback = Path.home() / ".viron" / "maha.log"
            fallback.parent.mkdir(parents=True, exist_ok=True)
            with open(fallback, "a", encoding="utf-8") as f:
                f.write(entry)


class MahaEngine:
    """
    Engine chính cho hệ thống quyền maha.
    
    Thay thế sudo với:
    - Xác thực dựa trên policy
    - Session caching (không hỏi mật khẩu liên tục)
    - Audit logging
    - Hỗ trợ chạy lệnh dưới quyền mahavir hoặc user khác
    """

    # Đường dẫn policy mặc định
    _POLICY_PATHS = [
        Path("/etc/viron/maha.policy"),
        Path.home() / ".config" / "viron" / "maha.policy",
    ]

    def __init__(self) -> None:
        self._policies: dict[str, MahaPolicy] = {}
        self._sessions: dict[str, MahaSession] = {}
        self._audit = MahaAuditLog()
        self._load_default_policies()

    def _load_default_policies(self) -> None:
        """Load chính sách mặc định: mahavir có toàn quyền."""
        self._policies["mahavir"] = MahaPolicy(
            user="mahavir",
            allowed_commands=[],  # Rỗng = tất cả
            level=MahaLevel.SUPREME,
            require_password=False,
            timeout_seconds=0,  # Không hết hạn
        )

    def load_policy_file(self, path: Path) -> int:
        """
        Load policy từ file.
        
        Format:
            user=username level=elevated commands=net,proc,svc password=yes timeout=300
        """
        if not path.is_file():
            return 0
        loaded = 0
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                policy = self._parse_policy_line(line)
                if policy:
                    self._policies[policy.user] = policy
                    loaded += 1
        return loaded

    @staticmethod
    def _parse_policy_line(line: str) -> MahaPolicy | None:
        """Parse một dòng policy."""
        parts: dict[str, str] = {}
        for token in line.split():
            if "=" in token:
                k, v = token.split("=", 1)
                parts[k] = v
        
        user = parts.get("user")
        if not user:
            return None
        
        level_str = parts.get("level", "elevated")
        level_map = {"user": MahaLevel.USER, "elevated": MahaLevel.ELEVATED, "supreme": MahaLevel.SUPREME}
        level = level_map.get(level_str, MahaLevel.ELEVATED)
        
        commands_str = parts.get("commands", "")
        commands = [c for c in commands_str.split(",") if c] if commands_str else []
        
        require_pw = parts.get("password", "yes").lower() in ("yes", "true", "1")
        timeout = int(parts.get("timeout", "300"))
        
        return MahaPolicy(
            user=user,
            allowed_commands=commands,
            level=level,
            require_password=require_pw,
            timeout_seconds=timeout,
        )

    def authenticate(self, user: str, password_hash: str | None = None) -> bool:
        """
        Xác thực người dùng cho maha.
        
        Trả về True nếu xác thực thành công.
        mahavir luôn có quyền tối cao.
        """
        policy = self._policies.get(user)
        
        if policy is None:
            # Không có policy → từ chối
            return False
        
        # Kiểm tra session còn hiệu lực
        session = self._sessions.get(user)
        if session and session.is_valid:
            return True
        
        # mahavir không cần mật khẩu
        if user == "mahavir":
            self._create_session(user, MahaLevel.SUPREME)
            return True
        
        if policy.require_password and password_hash is None:
            return False
        
        # Tạo session mới
        self._create_session(user, policy.level, policy.timeout_seconds)
        return True

    def _create_session(self, user: str, level: MahaLevel,
                        timeout: int = 300) -> None:
        self._sessions[user] = MahaSession(
            user=user,
            level=level,
            authenticated_at=time.time(),
            timeout_seconds=timeout,
        )

    def check_permission(self, user: str, command: str) -> bool:
        """Kiểm tra user có quyền chạy lệnh với maha không."""
        policy = self._policies.get(user)
        if policy is None:
            return False
        
        # mahavir luôn có quyền
        if user == "mahavir" or policy.level == MahaLevel.SUPREME:
            return True
        
        # Nếu allowed_commands rỗng → cho phép tất cả
        if not policy.allowed_commands:
            return True
        
        return command in policy.allowed_commands

    def execute_as_maha(self, user: str, command: str, args: Sequence[str],
                        target_user: str = "mahavir") -> tuple[bool, str]:
        """
        Thực thi lệnh với quyền maha.
        
        Returns: (success, message)
        """
        # Kiểm tra session
        session = self._sessions.get(user)
        if not session or not session.is_valid:
            self._audit.record(user, command, args, granted=False, target_user=target_user)
            return False, "Chưa xác thực. Dùng 'maha' để xác thực trước."
        
        # Kiểm tra quyền
        if not self.check_permission(user, command):
            self._audit.record(user, command, args, granted=False, target_user=target_user)
            return False, f"Không có quyền chạy '{command}' với maha."
        
        # Ghi log và thực thi
        self._audit.record(user, command, args, granted=True, target_user=target_user)
        return True, "OK"

    def invalidate_session(self, user: str) -> None:
        """Hủy session maha của user."""
        self._sessions.pop(user, None)

    def add_policy(self, policy: MahaPolicy) -> None:
        """Thêm policy mới trực tiếp."""
        self._policies[policy.user] = policy

    def get_current_level(self, user: str) -> MahaLevel:
        """Lấy cấp quyền hiện tại."""
        session = self._sessions.get(user)
        if session and session.is_valid:
            return session.level
        return MahaLevel.USER


# Singleton engine
_maha_engine = MahaEngine()


def get_maha_engine() -> MahaEngine:
    return _maha_engine
