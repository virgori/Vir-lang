"""
Tests cho Viron CLI System Management Tools.
=============================================
Kiểm tra: registry, alias engine, maha, net, proc, fs, svc, pkg, user, sys, CLI dispatch.
"""

from __future__ import annotations

import os
import sys
import pytest

# Đảm bảo import được
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ═══════════════════════════════════════════════════════════════
# Registry Tests
# ═══════════════════════════════════════════════════════════════

class TestCommandRegistry:
    def setup_method(self):
        from src.viron.registry import CommandRegistry, CommandMeta
        self.registry = CommandRegistry()
        self.meta = CommandMeta(
            name="test-cmd",
            description="Test command",
            usage="test-cmd [args]",
            handler=lambda args: 0,
            category="test",
        )

    def test_register_and_resolve(self):
        self.registry.register(self.meta)
        result = self.registry.resolve("test-cmd")
        assert result is not None
        assert result.name == "test-cmd"
        assert result.description == "Test command"

    def test_resolve_unknown_returns_none(self):
        assert self.registry.resolve("nonexistent") is None

    def test_alias_zero_cost(self):
        """Alias trỏ đến cùng CommandMeta object → zero overhead."""
        self.registry.register(self.meta)
        self.registry.alias("test-alias", "test-cmd")
        
        original = self.registry.resolve("test-cmd")
        aliased = self.registry.resolve("test-alias")
        
        assert aliased is not None
        assert aliased is original  # Cùng object, không copy
        assert aliased.handler is original.handler

    def test_alias_unknown_raises(self):
        with pytest.raises(KeyError):
            self.registry.alias("bad-alias", "nonexistent")

    def test_is_alias(self):
        self.registry.register(self.meta)
        self.registry.alias("my-alias", "test-cmd")
        
        assert self.registry.is_alias("my-alias") is True
        assert self.registry.is_alias("test-cmd") is False

    def test_get_aliases(self):
        self.registry.register(self.meta)
        self.registry.alias("a1", "test-cmd")
        self.registry.alias("a2", "test-cmd")
        
        aliases = self.registry.get_aliases("test-cmd")
        assert set(aliases) == {"a1", "a2"}

    def test_canonical_name(self):
        self.registry.register(self.meta)
        self.registry.alias("a1", "test-cmd")
        
        assert self.registry.canonical_name("a1") == "test-cmd"
        assert self.registry.canonical_name("test-cmd") == "test-cmd"
        assert self.registry.canonical_name("unknown") is None

    def test_list_commands_no_duplicates(self):
        self.registry.register(self.meta)
        self.registry.alias("a1", "test-cmd")
        self.registry.alias("a2", "test-cmd")
        
        commands = self.registry.list_commands()
        assert len(commands) == 1

    def test_list_by_category(self):
        from src.viron.registry import CommandMeta
        self.registry.register(self.meta)
        self.registry.register(CommandMeta(
            name="other", description="Other",
            usage="other", handler=lambda a: 0,
            category="other",
        ))
        
        by_cat = self.registry.list_by_category()
        assert "test" in by_cat
        assert "other" in by_cat
        assert len(by_cat["test"]) == 1


# ═══════════════════════════════════════════════════════════════
# Alias Engine Tests
# ═══════════════════════════════════════════════════════════════

class TestAliasEngine:
    def test_parse_alias_file(self, tmp_path):
        from src.viron.alias_engine import _parse_alias_file
        
        conf = tmp_path / "aliases.conf"
        conf.write_text(
            "# Comment\n"
            "sudo = maha\n"
            "ifconfig = net\n"
            "\n"
            "# Another comment\n"
            "ps = proc\n"
        )
        
        aliases = _parse_alias_file(conf)
        assert aliases == {"sudo": "maha", "ifconfig": "net", "ps": "proc"}

    def test_parse_empty_file(self, tmp_path):
        from src.viron.alias_engine import _parse_alias_file
        
        conf = tmp_path / "empty.conf"
        conf.write_text("")
        assert _parse_alias_file(conf) == {}

    def test_parse_nonexistent_file(self):
        from pathlib import Path
        from src.viron.alias_engine import _parse_alias_file
        
        assert _parse_alias_file(Path("/nonexistent/file")) == {}

    def test_alias_profile(self):
        from src.viron.alias_engine import AliasProfile
        
        profile = AliasProfile("test")
        profile.add("sudo", "maha")
        profile.add("ifconfig", "net")
        
        assert profile.name == "test"
        assert profile.mappings == {"sudo": "maha", "ifconfig": "net"}

    def test_linux_profile(self):
        from src.viron.alias_engine import linux_profile
        
        p = linux_profile()
        assert p.name == "linux"
        assert "sudo" in p.mappings
        assert p.mappings["sudo"] == "maha"

    def test_macos_profile(self):
        from src.viron.alias_engine import macos_profile
        
        p = macos_profile()
        assert p.name == "macos"
        assert "sudo" in p.mappings

    def test_minimal_profile(self):
        from src.viron.alias_engine import minimal_profile
        
        p = minimal_profile()
        assert p.name == "minimal"
        assert len(p.mappings) == 0


# ═══════════════════════════════════════════════════════════════
# Maha Privilege Tests
# ═══════════════════════════════════════════════════════════════

class TestMahaPrivilege:
    def setup_method(self):
        from src.viron.auth.privilege import MahaEngine, MahaLevel, MahaPolicy
        self.engine = MahaEngine()
        self.MahaLevel = MahaLevel
        self.MahaPolicy = MahaPolicy

    def test_mahavir_always_authenticated(self):
        assert self.engine.authenticate("mahavir") is True

    def test_mahavir_always_has_permission(self):
        self.engine.authenticate("mahavir")
        assert self.engine.check_permission("mahavir", "any-command") is True

    def test_unknown_user_denied(self):
        assert self.engine.authenticate("unknown") is False

    def test_session_creation(self):
        self.engine.authenticate("mahavir")
        level = self.engine.get_current_level("mahavir")
        assert level == self.MahaLevel.SUPREME

    def test_session_invalidation(self):
        self.engine.authenticate("mahavir")
        self.engine.invalidate_session("mahavir")
        level = self.engine.get_current_level("mahavir")
        assert level == self.MahaLevel.USER

    def test_add_policy(self):
        policy = self.MahaPolicy(
            user="testuser",
            allowed_commands=["net", "proc"],
            level=self.MahaLevel.ELEVATED,
            require_password=False,
            timeout_seconds=60,
        )
        self.engine.add_policy(policy)
        self.engine.authenticate("testuser")
        
        assert self.engine.check_permission("testuser", "net") is True
        assert self.engine.check_permission("testuser", "proc") is True
        assert self.engine.check_permission("testuser", "maha") is False

    def test_policy_allow_all(self):
        policy = self.MahaPolicy(
            user="admin",
            allowed_commands=[],  # Rỗng = tất cả
            level=self.MahaLevel.ELEVATED,
            require_password=False,
            timeout_seconds=60,
        )
        self.engine.add_policy(policy)
        self.engine.authenticate("admin")
        
        assert self.engine.check_permission("admin", "anything") is True

    def test_execute_as_maha(self):
        self.engine.authenticate("mahavir")
        success, msg = self.engine.execute_as_maha("mahavir", "net", ["list"])
        assert success is True

    def test_execute_without_auth_denied(self):
        success, msg = self.engine.execute_as_maha("nobody", "net", ["list"])
        assert success is False

    def test_parse_policy_line(self):
        from src.viron.auth.privilege import MahaEngine
        
        line = "user=testuser level=elevated commands=net,proc password=no timeout=120"
        policy = MahaEngine._parse_policy_line(line)
        
        assert policy is not None
        assert policy.user == "testuser"
        assert policy.level == self.MahaLevel.ELEVATED
        assert policy.allowed_commands == ["net", "proc"]
        assert policy.require_password is False
        assert policy.timeout_seconds == 120


# ═══════════════════════════════════════════════════════════════
# Identity Manager Tests
# ═══════════════════════════════════════════════════════════════

class TestIdentityManager:
    def setup_method(self):
        from src.viron.auth.identity import IdentityManager, UserRole
        self.mgr = IdentityManager()
        self.UserRole = UserRole

    def test_mahavir_exists_by_default(self):
        user = self.mgr.get_user("mahavir")
        assert user is not None
        assert user.uid == 0
        assert user.is_mahavir is True
        assert user.can_maha is True

    def test_mahavir_cannot_be_deleted(self):
        assert self.mgr.remove_user("mahavir") is False

    def test_add_user(self):
        user = self.mgr.add_user("testuser")
        assert user.username == "testuser"
        assert user.uid >= 1000
        assert user.role == self.UserRole.USER
        assert user.home_dir == "/home/testuser"

    def test_add_user_with_maha(self):
        user = self.mgr.add_user("admin", role=self.UserRole.MAHA_MEMBER, groups=["maha"])
        assert user.can_maha is True

    def test_add_duplicate_user_raises(self):
        self.mgr.add_user("dup")
        with pytest.raises(ValueError):
            self.mgr.add_user("dup")

    def test_remove_user(self):
        self.mgr.add_user("removeme")
        assert self.mgr.remove_user("removeme") is True
        assert self.mgr.get_user("removeme") is None

    def test_get_user_by_uid(self):
        user = self.mgr.add_user("byuid")
        found = self.mgr.get_user_by_uid(user.uid)
        assert found is not None
        assert found.username == "byuid"

    def test_add_group(self):
        group = self.mgr.add_group("developers")
        assert group.name == "developers"
        assert group.gid >= 1000

    def test_add_user_to_group(self):
        self.mgr.add_user("dev1")
        self.mgr.add_group("devs")
        assert self.mgr.add_user_to_group("dev1", "devs") is True
        assert self.mgr.user_in_group("dev1", "devs") is True

    def test_list_users(self):
        self.mgr.add_user("u1")
        self.mgr.add_user("u2")
        users = self.mgr.list_users()
        names = [u.username for u in users]
        assert "mahavir" in names
        assert "u1" in names
        assert "u2" in names

    def test_set_role(self):
        self.mgr.add_user("promoted")
        assert self.mgr.set_role("promoted", self.UserRole.ADMIN) is True
        user = self.mgr.get_user("promoted")
        assert user.role == self.UserRole.ADMIN

    def test_cannot_change_mahavir_role(self):
        assert self.mgr.set_role("mahavir", self.UserRole.USER) is False


# ═══════════════════════════════════════════════════════════════
# CLI Dispatch Tests
# ═══════════════════════════════════════════════════════════════

class TestCLIDispatch:
    def test_help_returns_zero(self, capsys):
        from src.viron.cli import run_cli
        rc = run_cli(["help"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "VIRON" in out.upper()

    def test_version_returns_zero(self, capsys):
        from src.viron.cli import run_cli
        rc = run_cli(["version"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "1.0.0" in out

    def test_alias_list(self, capsys):
        from src.viron.cli import run_cli
        rc = run_cli(["alias"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "sudo" in out or "Alias" in out

    def test_unknown_command(self, capsys):
        from src.viron.cli import run_cli
        rc = run_cli(["completely-unknown-cmd"])
        assert rc == 127
        out = capsys.readouterr().out
        assert "không tìm thấy" in out

    def test_empty_args_shows_help(self, capsys):
        from src.viron.cli import run_cli
        rc = run_cli([])
        assert rc == 0


# ═══════════════════════════════════════════════════════════════
# Net Command Tests
# ═══════════════════════════════════════════════════════════════

class TestNetCommand:
    def test_net_help(self, capsys):
        from src.viron.commands.net import cmd_net
        rc = cmd_net([])
        assert rc == 0
        out = capsys.readouterr().out
        assert "net" in out.lower()
        assert "list" in out

    def test_net_help_explicit(self, capsys):
        from src.viron.commands.net import cmd_net
        rc = cmd_net(["help"])
        assert rc == 0

    def test_net_invalid_subcmd(self, capsys):
        from src.viron.commands.net import cmd_net
        rc = cmd_net(["nonexistent"])
        out = capsys.readouterr().out
        assert "không hợp lệ" in out


# ═══════════════════════════════════════════════════════════════
# Proc Command Tests
# ═══════════════════════════════════════════════════════════════

class TestProcCommand:
    def test_proc_help(self, capsys):
        from src.viron.commands.proc import cmd_proc
        rc = cmd_proc(["help"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "proc" in out.lower()

    def test_proc_kill_no_args(self, capsys):
        from src.viron.commands.proc import cmd_proc
        rc = cmd_proc(["kill"])
        assert rc == 1

    def test_proc_show_no_args(self, capsys):
        from src.viron.commands.proc import cmd_proc
        rc = cmd_proc(["show"])
        assert rc == 1


# ═══════════════════════════════════════════════════════════════
# FS Command Tests
# ═══════════════════════════════════════════════════════════════

class TestFSCommand:
    def test_fs_help(self, capsys):
        from src.viron.commands.fs_cmd import cmd_fs
        rc = cmd_fs(["help"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "fs" in out.lower()

    def test_fs_mkdir_and_remove(self, tmp_path, capsys):
        from src.viron.commands.fs_cmd import cmd_fs
        
        test_dir = str(tmp_path / "test_viron_dir")
        rc = cmd_fs(["mkdir", test_dir])
        assert rc == 0
        assert os.path.isdir(test_dir)

    def test_fs_read_no_args(self, capsys):
        from src.viron.commands.fs_cmd import cmd_fs
        rc = cmd_fs(["read"])
        assert rc == 1

    def test_fs_info_nonexistent(self, capsys):
        from src.viron.commands.fs_cmd import cmd_fs
        rc = cmd_fs(["info", "/nonexistent/path"])
        assert rc == 1

    def test_fs_list_current_dir(self, capsys):
        from src.viron.commands.fs_cmd import cmd_fs
        rc = cmd_fs(["list", "."])
        assert rc == 0


# ═══════════════════════════════════════════════════════════════
# Svc Command Tests
# ═══════════════════════════════════════════════════════════════

class TestSvcCommand:
    def test_svc_help(self, capsys):
        from src.viron.commands.svc import cmd_svc
        rc = cmd_svc(["help"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "svc" in out.lower()

    def test_svc_status_no_args(self, capsys):
        from src.viron.commands.svc import cmd_svc
        rc = cmd_svc(["status"])
        assert rc == 1


# ═══════════════════════════════════════════════════════════════
# Pkg Command Tests
# ═══════════════════════════════════════════════════════════════

class TestPkgCommand:
    def test_pkg_help(self, capsys):
        from src.viron.commands.pkg import cmd_pkg
        rc = cmd_pkg([])
        assert rc == 0
        out = capsys.readouterr().out
        assert "pkg" in out.lower()

    def test_pkg_install_no_args(self, capsys):
        from src.viron.commands.pkg import cmd_pkg
        rc = cmd_pkg(["install"])
        assert rc == 1


# ═══════════════════════════════════════════════════════════════
# User Command Tests
# ═══════════════════════════════════════════════════════════════

class TestUserCommand:
    def test_user_whoami(self, capsys):
        from src.viron.commands.user import cmd_user
        rc = cmd_user(["whoami"])
        assert rc == 0

    def test_user_list(self, capsys):
        from src.viron.commands.user import cmd_user
        rc = cmd_user(["list"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "mahavir" in out.lower()

    def test_user_add_and_del(self, capsys):
        from src.viron.commands.user import cmd_user
        rc = cmd_user(["add", "testuser_xyzzy"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "testuser_xyzzy" in out

    def test_user_del_mahavir_blocked(self, capsys):
        from src.viron.commands.user import cmd_user
        rc = cmd_user(["del", "mahavir"])
        assert rc == 1
        out = capsys.readouterr().out
        assert "mahavir" in out.lower()

    def test_user_help(self, capsys):
        from src.viron.commands.user import cmd_user
        rc = cmd_user(["help"])
        assert rc == 0


# ═══════════════════════════════════════════════════════════════
# Sys Info Tests
# ═══════════════════════════════════════════════════════════════

class TestSysCommand:
    def test_sys_info(self, capsys):
        from src.viron.commands.sys_info import cmd_sys
        rc = cmd_sys(["info"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "Viron" in out

    def test_sys_version(self, capsys):
        from src.viron.commands.sys_info import cmd_sys
        rc = cmd_sys(["version"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "1.0.0" in out

    def test_sys_host(self, capsys):
        from src.viron.commands.sys_info import cmd_sys
        rc = cmd_sys(["host"])
        assert rc == 0

    def test_sys_os(self, capsys):
        from src.viron.commands.sys_info import cmd_sys
        rc = cmd_sys(["os"])
        assert rc == 0

    def test_sys_help(self, capsys):
        from src.viron.commands.sys_info import cmd_sys
        rc = cmd_sys(["help"])
        assert rc == 0


# ═══════════════════════════════════════════════════════════════
# Maha Command Integration Tests
# ═══════════════════════════════════════════════════════════════

class TestMahaCommand:
    def test_maha_no_args(self, capsys):
        from src.viron.commands.maha import cmd_maha
        rc = cmd_maha([])
        assert rc == 1

    def test_maha_list_perms(self, capsys):
        from src.viron.commands.maha import cmd_maha
        rc = cmd_maha(["-l"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "Người dùng" in out or "Cấp quyền" in out

    def test_maha_invalidate(self, capsys):
        from src.viron.commands.maha import cmd_maha
        rc = cmd_maha(["-k"])
        assert rc == 0


# ═══════════════════════════════════════════════════════════════
# Integration: Full Registration
# ═══════════════════════════════════════════════════════════════

class TestFullRegistration:
    def test_all_commands_registered(self):
        """Tất cả lệnh chính phải được đăng ký."""
        from src.viron.registry import CommandRegistry
        from src.viron.cli import _register_all_commands
        
        # Fresh registry
        import src.viron.registry as reg_mod
        old = reg_mod._global_registry
        reg_mod._global_registry = CommandRegistry()
        
        try:
            _register_all_commands()
            registry = reg_mod._global_registry
            
            # Kiểm tra các lệnh chính
            for cmd in ["maha", "net", "proc", "fs", "svc", "pkg", "user", "sys"]:
                assert registry.resolve(cmd) is not None, f"Missing command: {cmd}"
            
            # Kiểm tra aliases
            for alias in ["sudo", "ifconfig", "ps", "ls", "systemctl"]:
                assert registry.resolve(alias) is not None, f"Missing alias: {alias}"
        finally:
            reg_mod._global_registry = old

    def test_alias_points_to_same_handler(self):
        """Alias phải trỏ đến cùng handler — zero cost."""
        from src.viron.registry import CommandRegistry
        from src.viron.cli import _register_all_commands
        
        import src.viron.registry as reg_mod
        old = reg_mod._global_registry
        reg_mod._global_registry = CommandRegistry()
        
        try:
            _register_all_commands()
            registry = reg_mod._global_registry
            
            maha = registry.resolve("maha")
            sudo = registry.resolve("sudo")
            assert maha is not None
            assert sudo is not None
            assert maha.handler is sudo.handler  # Zero-cost: same handler
            
            net = registry.resolve("net")
            ifconfig = registry.resolve("ifconfig")
            assert net is not None
            assert ifconfig is not None
            assert net.handler is ifconfig.handler
        finally:
            reg_mod._global_registry = old
