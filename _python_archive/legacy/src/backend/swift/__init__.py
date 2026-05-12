# ═══════════════════════════════════════════════════════════════════════════════
# Vir → Swift Transpiler Backend
# ═══════════════════════════════════════════════════════════════════════════════
# 
# "Vỏ Vir - Nhân Native" Architecture:
#   Layer 1: Vir Syntax → Swift/Kotlin transpilation
#   Layer 2: Native Core (C/C++/Rust) → Static library bindings
#   Layer 3: Native Compiler (Xcode/swiftc) → Final binary
#
# Author: Vir Team
# Date: 11/3/2026
# ═══════════════════════════════════════════════════════════════════════════════

from .transpiler import VirToSwiftTranspiler
from .mapping import VirSwiftMapping
from .bridge import SwiftNativeBridge
from .cli import swift_build_command

__all__ = [
    'VirToSwiftTranspiler',
    'VirSwiftMapping', 
    'SwiftNativeBridge',
    'swift_build_command',
]
