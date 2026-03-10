"""
Viron Identity System — Hệ thống nhận dạng người dùng.
=========================================================
mahavir là người dùng tối cao (thay root).

Hệ thống phân quyền:
- mahavir: Người dùng tối cao, mọi quyền, UID=0
- Nhóm maha: Người dùng được phép dùng maha để nâng quyền
- Người dùng thường: Quyền hạn chế
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path


class UserRole(IntEnum):
    """Vai trò người dùng trong hệ thống."""
    GUEST = 0
    USER = 1
    MAHA_MEMBER = 2     # Thành viên nhóm maha
    ADMIN = 3           # Quản trị viên
    MAHAVIR = 4         # Người dùng tối cao


@dataclass
class VirUser:
    """Đại diện cho một người dùng trong hệ thống Vir."""
    uid: int
    username: str
    role: UserRole
    groups: list[str] = field(default_factory=list)
    home_dir: str = ""
    shell: str = "/usr/bin/viron"
    
    @property
    def is_mahavir(self) -> bool:
        return self.uid == 0 or self.role == UserRole.MAHAVIR
    
    @property
    def can_maha(self) -> bool:
        """Kiểm tra có quyền dùng maha không."""
        return (self.is_mahavir 
                or self.role >= UserRole.MAHA_MEMBER 
                or "maha" in self.groups)


@dataclass
class VirGroup:
    """Nhóm người dùng."""
    gid: int
    name: str
    members: list[str] = field(default_factory=list)


# Người dùng tối cao mặc định
MAHAVIR_USER = VirUser(
    uid=0,
    username="mahavir",
    role=UserRole.MAHAVIR,
    groups=["mahavir", "maha"],
    home_dir="/home/mahavir",
    shell="/usr/bin/viron",
)

# Nhóm maha mặc định
MAHA_GROUP = VirGroup(
    gid=0,
    name="maha",
    members=["mahavir"],
)


class IdentityManager:
    """
    Quản lý danh tính người dùng.
    
    Tương tự /etc/passwd + /etc/group nhưng cho Vir OS.
    mahavir thay root, nhóm maha thay nhóm wheel/sudo.
    """

    _PASSWD_PATH = Path("/etc/viron/passwd")
    _GROUP_PATH = Path("/etc/viron/group")

    def __init__(self) -> None:
        self._users: dict[str, VirUser] = {}
        self._groups: dict[str, VirGroup] = {}
        self._uid_map: dict[int, str] = {}
        self._next_uid = 1000
        self._next_gid = 1000
        self._init_defaults()

    def _init_defaults(self) -> None:
        """Khởi tạo mahavir và nhóm maha mặc định."""
        self._users["mahavir"] = MAHAVIR_USER
        self._uid_map[0] = "mahavir"
        self._groups["maha"] = MAHA_GROUP
        self._groups["mahavir"] = VirGroup(gid=0, name="mahavir", members=["mahavir"])

    def add_user(self, username: str, role: UserRole = UserRole.USER,
                 groups: list[str] | None = None,
                 shell: str = "/usr/bin/viron") -> VirUser:
        """Tạo người dùng mới."""
        if username in self._users:
            raise ValueError(f"Người dùng '{username}' đã tồn tại")
        
        uid = self._next_uid
        self._next_uid += 1
        
        user = VirUser(
            uid=uid,
            username=username,
            role=role,
            groups=groups or [],
            home_dir=f"/home/{username}",
            shell=shell,
        )
        self._users[username] = user
        self._uid_map[uid] = username
        
        # Tự động tạo nhóm riêng
        self._groups[username] = VirGroup(
            gid=self._next_gid, name=username, members=[username]
        )
        self._next_gid += 1
        
        # Thêm vào các nhóm đã chỉ định
        for group_name in user.groups:
            if group_name in self._groups:
                if username not in self._groups[group_name].members:
                    self._groups[group_name].members.append(username)
        
        return user

    def remove_user(self, username: str) -> bool:
        """Xoá người dùng. Không thể xoá mahavir."""
        if username == "mahavir":
            return False
        user = self._users.pop(username, None)
        if user is None:
            return False
        self._uid_map.pop(user.uid, None)
        # Xoá khỏi tất cả nhóm
        for group in self._groups.values():
            if username in group.members:
                group.members.remove(username)
        return True

    def get_user(self, username: str) -> VirUser | None:
        return self._users.get(username)

    def get_user_by_uid(self, uid: int) -> VirUser | None:
        name = self._uid_map.get(uid)
        return self._users.get(name) if name else None

    def get_current_user(self) -> VirUser:
        """Lấy người dùng hiện tại dựa trên OS."""
        os_user = os.environ.get("VIRON_USER", os.environ.get("USER", "unknown"))
        user = self._users.get(os_user)
        if user:
            return user
        # Nếu UID = 0 → mahavir
        if os.getuid() == 0:
            return MAHAVIR_USER
        # Tạo user tạm
        return VirUser(
            uid=os.getuid(),
            username=os_user,
            role=UserRole.USER,
            home_dir=str(Path.home()),
        )

    def add_group(self, name: str, members: list[str] | None = None) -> VirGroup:
        """Tạo nhóm mới."""
        if name in self._groups:
            raise ValueError(f"Nhóm '{name}' đã tồn tại")
        gid = self._next_gid
        self._next_gid += 1
        group = VirGroup(gid=gid, name=name, members=members or [])
        self._groups[name] = group
        return group

    def add_user_to_group(self, username: str, group_name: str) -> bool:
        """Thêm user vào nhóm."""
        if username not in self._users or group_name not in self._groups:
            return False
        group = self._groups[group_name]
        if username not in group.members:
            group.members.append(username)
        if group_name not in self._users[username].groups:
            self._users[username].groups.append(group_name)
        return True

    def user_in_group(self, username: str, group_name: str) -> bool:
        group = self._groups.get(group_name)
        return group is not None and username in group.members

    def list_users(self) -> list[VirUser]:
        return list(self._users.values())

    def list_groups(self) -> list[VirGroup]:
        return list(self._groups.values())

    def change_password(self, username: str, password_hash: str) -> bool:
        """Đổi mật khẩu — lưu hash, không bao giờ lưu plaintext."""
        if username not in self._users:
            return False
        # Trong thực tế sẽ ghi vào /etc/viron/shadow
        return True

    def set_role(self, username: str, role: UserRole) -> bool:
        """Thay đổi vai trò người dùng."""
        user = self._users.get(username)
        if user is None or username == "mahavir":
            return False
        self._users[username] = VirUser(
            uid=user.uid,
            username=user.username,
            role=role,
            groups=user.groups,
            home_dir=user.home_dir,
            shell=user.shell,
        )
        return True


# Singleton
_identity_mgr = IdentityManager()


def get_identity_manager() -> IdentityManager:
    return _identity_mgr
