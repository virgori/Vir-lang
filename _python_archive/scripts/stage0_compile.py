#!/usr/bin/env python3
"""
stage0_compile.py — Bootstrap Stage 0: Python → virc binary
=============================================================
Uses the Python-based Vir compiler infrastructure to compile
virc.vri (and all its includes) into a standalone Mach-O ARM64
executable. This is the seed binary that starts the bootstrap.

After this, virc compiles itself — no more Python needed.

Usage:
    python3 scripts/stage0_compile.py [-o build/selfhost/virc-stage0]
"""

from __future__ import annotations

import os
import sys
import struct
import argparse
from pathlib import Path

# Add Vir root to path
VIR_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(VIR_ROOT))
sys.path.insert(0, str(VIR_ROOT / "legacy"))

from src.frontend.tokenizer.ngram_tokenizer import NGramTokenizer, Token
from src.frontend.parser.parser import Parser, ProgramNode
from src.ir.instructions.ir_builder import IRBuilder
from src.ir.instructions.q_ir import QModule
from src.ir.optimizer.optimizer import IROptimizer
from src.backend.codegen.codegen import CodeGenerator, TargetArch
from src.sublib.base import SubLibRegistry
import src.sublib.en  # noqa: F401 — triggers @register for EnglishAdapter


# ═══════════════════════════════════════════════════════
# Mach-O Constants
# ═══════════════════════════════════════════════════════

MH_MAGIC_64 = 0xFEEDFACF
CPU_TYPE_ARM64 = 0x0100000C
CPU_SUB_ALL = 0x00000000
MH_EXECUTE = 2
MH_PIE = 0x00200000
MH_NOUNDEFS = 0x00000001
LC_SEGMENT_64 = 0x19
LC_MAIN = 0x80000028
TEXT_BASE = 0x100000000
PAGE_SIZE = 0x4000


# ═══════════════════════════════════════════════════════
# Include Resolver
# ═══════════════════════════════════════════════════════

def resolve_includes(source_path: Path, stdlib_root: Path) -> str:
    """
    Recursively resolve all `include` directives and concatenate
    source files into a single compilation unit.
    """
    seen: set[str] = set()
    parts: list[str] = []

    def _resolve(path: Path) -> None:
        canonical = str(path.resolve())
        if canonical in seen:
            return
        seen.add(canonical)

        if not path.exists():
            print(f"  [warn] include not found: {path}")
            return

        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("include "):
                mod_path = stripped[8:].rstrip(";").strip()
                # Convert module path: vir::rt::syscall or vir.rt.syscall → vir/rt/syscall.vri
                # Handle both :: and . as separators
                path_with_slashes = mod_path.replace("::", "/").replace(".", "/")
                rel = path_with_slashes + ".vri"
                inc_path = stdlib_root / rel
                if not inc_path.exists():
                    # Try relative to source file - handle both :: and . separators
                    last_part = mod_path.replace("::", ".").split(".")[-1]
                    inc_path = path.parent / (last_part + ".vri")
                _resolve(inc_path)
            elif stripped.startswith("module ") or stripped.startswith("import "):
                # Skip module declarations and import lines
                continue
            else:
                parts.append(line)
        parts.append("")  # separator

    _resolve(source_path)
    return "\n".join(parts)


# ═══════════════════════════════════════════════════════
# Mach-O Emitter (minimal standalone)
# ═══════════════════════════════════════════════════════

def emit_macho_arm64(code: bytes, entry_offset: int, output_path: Path) -> None:
    """Emit a minimal Mach-O ARM64 executable."""

    code_size = len(code)
    text_padded = ((code_size + PAGE_SIZE - 1) // PAGE_SIZE) * PAGE_SIZE

    # Header: 32 bytes
    # Load commands: __PAGEZERO(72) + __TEXT(72+80=152) + LC_MAIN(24) = 248
    ncmds = 3
    sizeofcmds = 72 + 152 + 24  # 248
    header_total = 32 + sizeofcmds  # 280

    text_file_offset = PAGE_SIZE
    text_vm_addr = TEXT_BASE + text_file_offset

    buf = bytearray()

    # ── Mach-O Header (32 bytes) ──
    buf += struct.pack("<I", MH_MAGIC_64)
    buf += struct.pack("<I", CPU_TYPE_ARM64)
    buf += struct.pack("<I", CPU_SUB_ALL)
    buf += struct.pack("<I", MH_EXECUTE)
    buf += struct.pack("<I", ncmds)
    buf += struct.pack("<I", sizeofcmds)
    buf += struct.pack("<I", MH_PIE | MH_NOUNDEFS)
    buf += struct.pack("<I", 0)  # reserved

    # ── __PAGEZERO (72 bytes) ──
    buf += struct.pack("<I", LC_SEGMENT_64)
    buf += struct.pack("<I", 72)
    buf += b"__PAGEZERO\x00\x00\x00\x00\x00\x00"  # 16 bytes
    buf += struct.pack("<Q", 0)                       # vmaddr
    buf += struct.pack("<Q", TEXT_BASE)                # vmsize
    buf += struct.pack("<Q", 0)                       # fileoff
    buf += struct.pack("<Q", 0)                       # filesize
    buf += struct.pack("<I", 0)                       # maxprot
    buf += struct.pack("<I", 0)                       # initprot
    buf += struct.pack("<I", 0)                       # nsects
    buf += struct.pack("<I", 0)                       # flags

    # ── __TEXT segment (72 bytes) + 1 section (80 bytes) = 152 ──
    buf += struct.pack("<I", LC_SEGMENT_64)
    buf += struct.pack("<I", 152)
    buf += b"__TEXT\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"  # 16 bytes
    buf += struct.pack("<Q", TEXT_BASE)                # vmaddr
    buf += struct.pack("<Q", text_file_offset + text_padded)  # vmsize
    buf += struct.pack("<Q", 0)                        # fileoff
    buf += struct.pack("<Q", text_file_offset + text_padded)  # filesize
    buf += struct.pack("<I", 5)                        # maxprot (r-x)
    buf += struct.pack("<I", 5)                        # initprot (r-x)
    buf += struct.pack("<I", 1)                        # nsects
    buf += struct.pack("<I", 0)                        # flags

    # __text section (80 bytes)
    buf += b"__text\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"  # sectname 16
    buf += b"__TEXT\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"  # segname 16
    buf += struct.pack("<Q", text_vm_addr)             # addr
    buf += struct.pack("<Q", code_size)                # size
    buf += struct.pack("<I", text_file_offset)         # offset
    buf += struct.pack("<I", 2)                        # align (2^2=4)
    buf += struct.pack("<I", 0)                        # reloff
    buf += struct.pack("<I", 0)                        # nreloc
    buf += struct.pack("<I", 0x80000400)               # flags
    buf += struct.pack("<I", 0)                        # reserved1
    buf += struct.pack("<I", 0)                        # reserved2
    buf += struct.pack("<I", 0)                        # reserved3

    # ── LC_MAIN (24 bytes) ──
    buf += struct.pack("<I", LC_MAIN)
    buf += struct.pack("<I", 24)
    buf += struct.pack("<Q", text_file_offset + entry_offset)  # entryoff
    buf += struct.pack("<Q", 0)                        # stacksize

    # ── Pad to page ──
    buf += b"\x00" * (text_file_offset - len(buf))

    # ── Code ──
    buf += code

    # ── Pad to page ──
    buf += b"\x00" * (text_padded - code_size)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(bytes(buf))
    os.chmod(str(output_path), 0o755)
    print(f"  Written: {output_path} ({len(buf)} bytes)")


# ═══════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════

def main() -> int:
    parser = argparse.ArgumentParser(description="Stage 0: Compile virc.vri with Python")
    parser.add_argument("source", nargs="?",
                        default=str(VIR_ROOT / "stdlib" / "vir" / "compiler" / "virc.vri"),
                        help="Source .vri file")
    parser.add_argument("-o", "--output",
                        default=str(VIR_ROOT / "build" / "selfhost" / "virc-stage0"),
                        help="Output binary path")
    parser.add_argument("--stdlib",
                        default=str(VIR_ROOT / "stdlib"),
                        help="Path to stdlib root (default: VIR_ROOT/stdlib)")
    args = parser.parse_args()

    source_path = Path(args.source).resolve()
    output_path = Path(args.output).resolve()
    stdlib_root = Path(args.stdlib).resolve()

    print("╔══════════════════════════════════════════════╗")
    print("║  Stage 0: Python → virc-stage0              ║")
    print("╚══════════════════════════════════════════════╝")
    print(f"  Source:  {source_path}")
    print(f"  Output:  {output_path}")
    print(f"  Stdlib:  {stdlib_root}")

    # Step 1: Resolve includes
    print("\n[1/5] Resolving includes...")
    full_source = resolve_includes(source_path, stdlib_root)
    print(f"  Total source: {len(full_source)} bytes, {full_source.count(chr(10))} lines")

    # Step 2: Tokenize
    print("[2/5] Tokenizing...")
    adapter = SubLibRegistry.get("en")
    tokenizer = NGramTokenizer(adapter)
    tokens = tokenizer.tokenize(full_source)
    print(f"  {len(tokens)} tokens")

    # Step 3: Parse
    print("[3/5] Parsing...")
    ast = Parser(tokens).parse()
    print(f"  AST root: {ast.__class__.__name__}")

    # Step 4: Lower to Q-IR + optimize
    print("[4/5] Lowering to Q-IR...")
    builder = IRBuilder()
    ir_module = builder.build(ast)

    optimizer = IROptimizer()
    optimized = optimizer.optimize(ir_module)

    func_count = len(optimized.functions) if hasattr(optimized, 'functions') else 0
    print(f"  {func_count} functions")

    # Step 5: Code generation
    print("[5/5] Generating ARM64 machine code...")
    codegen = CodeGenerator(TargetArch.ARM64)
    variants = codegen.generate(optimized)

    if not variants:
        print("  [error] No code variants generated")
        return 1

    # Extract machine code bytes
    # The code generator produces safe + fast variants; use the safe one for bootstrap
    code_bytes = bytearray()
    entry_offset = 0

    for v in variants:
        code_bytes.extend(v.safe_code.bytes_)

    # The _start entry will be at offset 0 of the first function
    # (virc's vir_main is the entry point)
    print(f"  {len(code_bytes)} bytes machine code")

    # Emit Mach-O
    print("\nEmitting Mach-O ARM64 executable...")
    emit_macho_arm64(bytes(code_bytes), entry_offset, output_path)

    print("\n  Stage 0 complete!")
    print(f"  Binary: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
