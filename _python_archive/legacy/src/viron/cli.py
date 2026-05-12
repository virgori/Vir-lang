"""
Viron CLI — Main entry point for the Vir system management tool.
===============================================================
Viron is the primary CLI, orchestrating all system commands:
- maha (supreme privilege, replaces sudo)
- net (network, replaces ifconfig)
- proc (processes, replaces ps)
- fs (files, replaces ls/cp/mv)
- svc (services, replaces systemctl)
- pkg (packages, replaces apt/brew)
- user (users, mahavir = supreme user)
- sys (system info)

The alias engine maps zero-cost to other command sets.
"""

from __future__ import annotations

import sys
from typing import Sequence

from . import __version__
from .registry import get_registry, CommandRegistry
from .alias_engine import load_aliases, register_default_aliases

# Import and register all commands
from .commands.maha import register_maha_commands
from .commands.net import register_net_commands
from .commands.proc import register_proc_commands
from .commands.fs_cmd import register_fs_commands
from .commands.svc import register_svc_commands
from .commands.pkg import register_pkg_commands
from .commands.user import register_user_commands
from .commands.sys_info import register_sys_commands


def _register_all_commands() -> None:
    """Register all built-in commands."""
    register_maha_commands()
    register_net_commands()
    register_proc_commands()
    register_fs_commands()
    register_svc_commands()
    register_pkg_commands()
    register_user_commands()
    register_sys_commands()


def _print_banner() -> None:
    print(f"""
╔══════════════════════════════════════════╗
║           V I R O N  v{__version__:<17}║
║   System Management — Vir OS CLI Tool    ║
╚══════════════════════════════════════════╝
""")


def _print_help() -> None:
    """Print general help."""
    _print_banner()
    
    registry = get_registry()
    categories = registry.list_by_category()
    
    category_names = {
        "auth": "🔐 Auth & Privileges",
        "network": "🌐 Network",
        "process": "⚙️  Processes",
        "filesystem": "📁 Filesystem",
        "service": "🔧 Services",
        "package": "📦 Packages",
        "user": "👤 Users",
        "system": "💻 System",
    }
    
    for cat, commands in categories.items():
        cat_name = category_names.get(cat, cat.title())
        print(f"  {cat_name}:")
        for cmd in commands:
            aliases = registry.get_aliases(cmd.name)
            alias_str = f" (alias: {', '.join(aliases)})" if aliases else ""
            maha_str = " [requires maha]" if cmd.requires_maha else ""
            print(f"    {cmd.name:<16} {cmd.description}{alias_str}{maha_str}")
        print()
    
    print("Usage: viron <command> [arguments...]")
    print("       viron help           Help")
    print("       viron alias          List aliases")
    print("       viron version        Version")
    print()
    print("Examples:")
    print("  viron net list              List network interfaces")
    print("  viron maha proc kill 1234   Kill process with maha privilege")
    print("  viron user whoami           Show current user")
    print("  viron fs list /home         List files")
    print()
    print("Supreme user: mahavir | Supreme privilege: maha")


def _print_aliases() -> None:
    """List all aliases."""
    registry = get_registry()
    commands = registry.list_commands()
    
    print("Registered aliases:")
    print(f"  {'Alias':<20} {'→'} {'Command'}")
    print("  " + "-" * 45)
    
    for cmd in commands:
        aliases = registry.get_aliases(cmd.name)
        for alias in aliases:
            print(f"  {alias:<20} → {cmd.name}")


def run_cli(argv: Sequence[str] | None = None) -> int:
    """
    Main entry point for Viron CLI.
    
    Pipeline:
    1. Register all commands
    2. Load aliases from config + defaults
    3. Parse argv and dispatch to handler
    """
    args = list(argv) if argv is not None else sys.argv[1:]
    
    # Step 1: Register commands
    _register_all_commands()
    
    # Step 2: Load aliases (zero-cost — just adds dict entries)
    register_default_aliases()
    load_aliases()
    
    # Step 3: Dispatch
    if not args:
        _print_help()
        return 0
    
    command_name = args[0]
    command_args = args[1:]
    
    # Built-in meta commands
    if command_name in ("help", "--help", "-h"):
        _print_help()
        return 0
    if command_name in ("version", "--version", "-v"):
        print(f"Viron v{__version__}")
        return 0
    if command_name == "alias":
        _print_aliases()
        return 0
    
    # Registry lookup O(1)
    registry = get_registry()
    meta = registry.resolve(command_name)
    
    if meta is None:
        print(f"viron: command not found: '{command_name}'")
        print(f"Use 'viron help' to see available commands.")
        return 127
    
    # Check maha privilege if required
    if meta.requires_maha:
        from .auth.identity import get_identity_manager
        user = get_identity_manager().get_current_user()
        if not user.can_maha and not user.is_mahavir:
            print(f"⛔ Command '{command_name}' requires maha privilege.")
            print(f"Try: viron maha {command_name} {' '.join(command_args)}")
            return 1
    
    # Execute handler
    try:
        return meta.handler(command_args)
    except KeyboardInterrupt:
        print("\nCancelled.")
        return 130
    except Exception as e:
        print(f"⛔ Error: {e}")
        return 1


def main() -> None:
    """Entry point for pyproject.toml console_scripts."""
    sys.exit(run_cli())
