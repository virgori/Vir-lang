"""
Vir File Format Specifications
================================
.vri  — Vir Source (text)        "Vir Intermediate"
.sri  — Vir Binary (compiled)    "Serialized Runtime Image"
.vsib — Vir Library (linkable)   "Vir Static/Import Binary"

SRI Binary Format (v1):
  ┌─────────────────────────────────┐
  │ Magic: "SRI\x01" (4 bytes)     │
  │ Version: u16                    │
  │ Arch: u16 (0=arm64, 1=x86_64)  │
  │ Flags: u32                      │
  │   bit 0: has_debug_info         │
  │   bit 1: position_independent   │
  │   bit 2: has_bce_metadata       │
  │   bit 3: has_escape_info        │
  │ Entry point offset: u64         │
  │ Code section offset: u64        │
  │ Code section size: u64          │
  │ Data section offset: u64        │
  │ Data section size: u64          │
  │ Symbol table offset: u64        │
  │ Symbol table count: u32         │
  │ String table offset: u64        │
  │ Relocation table offset: u64    │
  │ Relocation count: u32           │
  │ ─────── Code Section ────────── │
  │ <native machine code bytes>     │
  │ ─────── Data Section ────────── │
  │ <constants, string literals>    │
  │ ─────── Symbol Table ────────── │
  │ [name_offset, addr, size, type] │
  │ ─────── String Table ────────── │
  │ <null-terminated symbol names>  │
  │ ─────── Relocation Table ────── │
  │ [offset, type, symbol_idx]      │
  └─────────────────────────────────┘

VSIB Library Format (v1):
  ┌─────────────────────────────────┐
  │ Magic: "VSIB" (4 bytes)         │
  │ Version: u16                    │
  │ Module count: u16               │
  │ ─────── Module Index ────────── │
  │ [name_offset, sri_offset, size] │
  │ ─────── Module Bodies ────────  │
  │ <SRI binary for each module>    │
  │ ─────── Export Table ────────── │
  │ [name_offset, module_idx, addr] │
  │ ─────── Metadata ────────────── │
  │ Build timestamp: u64            │
  │ Compiler version string         │
  │ Target arch                     │
  │ Optimization level              │
  └─────────────────────────────────┘
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO


# ═══════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════

SRI_MAGIC = b"SRI\x01"
SRI_VERSION = 1
VSIB_MAGIC = b"VSIB"
VSIB_VERSION = 1

# Architecture codes
ARCH_ARM64 = 0
ARCH_X86_64 = 1

# SRI Flags
FLAG_DEBUG_INFO = 1 << 0
FLAG_PIC = 1 << 1
FLAG_BCE_METADATA = 1 << 2
FLAG_ESCAPE_INFO = 1 << 3

# Symbol types
SYM_FUNC = 0
SYM_DATA = 1
SYM_EXTERN = 2

# Relocation types
RELOC_ABS64 = 0
RELOC_REL32 = 1
RELOC_BRANCH26 = 2  # ARM64 b/bl
RELOC_ADRP = 3      # ARM64 adrp


# ═══════════════════════════════════════════════════════════
# SRI Header
# ═══════════════════════════════════════════════════════════

SRI_HEADER_FMT = "<4sHHIQQQQQQIQQI"
SRI_HEADER_SIZE = struct.calcsize(SRI_HEADER_FMT)

@dataclass
class SRISymbol:
    name: str
    address: int
    size: int
    sym_type: int = SYM_FUNC


@dataclass
class SRIReloc:
    offset: int
    reloc_type: int
    symbol_idx: int


@dataclass
class SRIBinary:
    """A compiled .sri binary image."""
    arch: int = ARCH_ARM64
    flags: int = 0
    entry_point: int = 0
    code: bytes = b""
    data: bytes = b""
    symbols: list[SRISymbol] = field(default_factory=list)
    relocations: list[SRIReloc] = field(default_factory=list)

    def write(self, path: str | Path) -> None:
        """Serialize to .sri file."""
        path = Path(path)
        if not path.suffix:
            path = path.with_suffix(".sri")

        # Build string table
        strtab = bytearray()
        name_offsets: dict[str, int] = {}
        for sym in self.symbols:
            if sym.name not in name_offsets:
                name_offsets[sym.name] = len(strtab)
                strtab.extend(sym.name.encode("utf-8"))
                strtab.append(0)

        # Compute offsets
        code_off = SRI_HEADER_SIZE
        data_off = code_off + len(self.code)
        symtab_off = data_off + len(self.data)
        sym_entry_size = struct.calcsize("<IQIB")  # name_off, addr, size, type
        strtab_off = symtab_off + len(self.symbols) * sym_entry_size
        reloctab_off = strtab_off + len(strtab)

        # Write header
        header = struct.pack(
            SRI_HEADER_FMT,
            SRI_MAGIC,
            SRI_VERSION,
            self.arch,
            self.flags,
            self.entry_point,
            code_off,
            len(self.code),
            data_off,
            len(self.data),
            symtab_off,
            len(self.symbols),
            strtab_off,
            reloctab_off,
            len(self.relocations),
        )

        with open(path, "wb") as f:
            f.write(header)
            f.write(self.code)
            f.write(self.data)

            # Symbol table
            for sym in self.symbols:
                f.write(struct.pack(
                    "<IQIB",
                    name_offsets.get(sym.name, 0),
                    sym.address,
                    sym.size,
                    sym.sym_type,
                ))

            # String table
            f.write(bytes(strtab))

            # Relocation table
            for rel in self.relocations:
                f.write(struct.pack("<IBI", rel.offset, rel.reloc_type, rel.symbol_idx))

    @classmethod
    def read(cls, path: str | Path) -> "SRIBinary":
        """Deserialize from .sri file."""
        with open(path, "rb") as f:
            raw_header = f.read(SRI_HEADER_SIZE)
            fields = struct.unpack(SRI_HEADER_FMT, raw_header)

            magic = fields[0]
            if magic != SRI_MAGIC:
                raise ValueError(f"Invalid SRI magic: {magic!r}")

            sri = cls(
                arch=fields[2],
                flags=fields[3],
                entry_point=fields[4],
            )

            # Read code
            f.seek(fields[5])  # code_off
            sri.code = f.read(fields[6])  # code_size

            # Read data
            f.seek(fields[7])  # data_off
            sri.data = f.read(fields[8])  # data_size

            # Read string table first (needed for symbol names)
            strtab_off = fields[11]
            f.seek(strtab_off)
            reloctab_off = fields[12]
            strtab = f.read(reloctab_off - strtab_off)

            def _read_str(offset: int) -> str:
                end = strtab.index(0, offset)
                return strtab[offset:end].decode("utf-8")

            # Read symbol table
            f.seek(fields[9])  # symtab_off
            sym_count = fields[10]
            for _ in range(sym_count):
                raw = f.read(struct.calcsize("<IQIB"))
                name_off, addr, size, sym_type = struct.unpack("<IQIB", raw)
                sri.symbols.append(SRISymbol(
                    name=_read_str(name_off),
                    address=addr,
                    size=size,
                    sym_type=sym_type,
                ))

            # Read relocations
            f.seek(reloctab_off)
            reloc_count = fields[13]
            for _ in range(reloc_count):
                raw = f.read(struct.calcsize("<IBI"))
                off, rtype, sym_idx = struct.unpack("<IBI", raw)
                sri.relocations.append(SRIReloc(off, rtype, sym_idx))

            return sri


# ═══════════════════════════════════════════════════════════
# VSIB Library
# ═══════════════════════════════════════════════════════════

@dataclass
class VSIBExport:
    name: str
    module_idx: int
    address: int


@dataclass
class VSIBModule:
    name: str
    sri: SRIBinary


@dataclass
class VSIBLibrary:
    """A .vsib library — collection of compiled modules."""
    modules: list[VSIBModule] = field(default_factory=list)
    exports: list[VSIBExport] = field(default_factory=list)
    build_timestamp: int = 0
    compiler_version: str = "vir-1.0"
    target_arch: str = "arm64"
    opt_level: int = 2

    def add_module(self, name: str, sri: SRIBinary) -> int:
        idx = len(self.modules)
        self.modules.append(VSIBModule(name=name, sri=sri))
        # Auto-export all functions
        for sym in sri.symbols:
            if sym.sym_type == SYM_FUNC:
                self.exports.append(VSIBExport(
                    name=f"{name}::{sym.name}",
                    module_idx=idx,
                    address=sym.address,
                ))
        return idx

    def write(self, path: str | Path) -> None:
        """Serialize to .vsib file."""
        path = Path(path)
        if not path.suffix:
            path = path.with_suffix(".vsib")

        # Serialize each module's SRI to bytes
        module_blobs: list[bytes] = []
        for mod in self.modules:
            module_blobs.append(self._serialize_sri(mod.sri))

        # Build string table for module names and exports
        strtab = bytearray()
        name_offsets: dict[str, int] = {}

        def _add_str(s: str) -> int:
            if s not in name_offsets:
                name_offsets[s] = len(strtab)
                strtab.extend(s.encode("utf-8"))
                strtab.append(0)
            return name_offsets[s]

        for mod in self.modules:
            _add_str(mod.name)
        for exp in self.exports:
            _add_str(exp.name)

        meta = self.compiler_version.encode("utf-8") + b"\0" + \
               self.target_arch.encode("utf-8") + b"\0"

        with open(path, "wb") as f:
            # Header
            f.write(VSIB_MAGIC)
            f.write(struct.pack("<HH", VSIB_VERSION, len(self.modules)))

            # Module index placeholder (will be filled)
            index_start = f.tell()
            index_entry = struct.calcsize("<IQQ")  # name_off, sri_off, size
            f.write(b"\0" * (len(self.modules) * index_entry))

            # Module bodies
            body_start = f.tell()
            module_offsets: list[tuple[int, int]] = []
            for blob in module_blobs:
                off = f.tell()
                f.write(blob)
                module_offsets.append((off, len(blob)))

            # Export table
            export_off = f.tell()
            f.write(struct.pack("<I", len(self.exports)))
            for exp in self.exports:
                f.write(struct.pack("<IIQ",
                    name_offsets[exp.name], exp.module_idx, exp.address))

            # String table
            strtab_off = f.tell()
            f.write(bytes(strtab))

            # Metadata
            meta_off = f.tell()
            f.write(struct.pack("<Q", self.build_timestamp))
            f.write(meta)
            f.write(struct.pack("<B", self.opt_level))

            # Go back and fill module index
            f.seek(index_start)
            for i, mod in enumerate(self.modules):
                sri_off, sri_size = module_offsets[i]
                f.write(struct.pack("<IQQ",
                    name_offsets[mod.name], sri_off, sri_size))

    @staticmethod
    def _serialize_sri(sri: SRIBinary) -> bytes:
        """Serialize SRI to bytes (in-memory)."""
        import io
        buf = io.BytesIO()

        # Build string table
        strtab = bytearray()
        name_offsets: dict[str, int] = {}
        for sym in sri.symbols:
            if sym.name not in name_offsets:
                name_offsets[sym.name] = len(strtab)
                strtab.extend(sym.name.encode("utf-8"))
                strtab.append(0)

        code_off = SRI_HEADER_SIZE
        data_off = code_off + len(sri.code)
        sym_entry_size = struct.calcsize("<IQIB")
        symtab_off = data_off + len(sri.data)
        strtab_off = symtab_off + len(sri.symbols) * sym_entry_size
        reloctab_off = strtab_off + len(strtab)

        header = struct.pack(
            SRI_HEADER_FMT,
            SRI_MAGIC, SRI_VERSION, sri.arch, sri.flags,
            sri.entry_point, code_off, len(sri.code),
            data_off, len(sri.data),
            symtab_off, len(sri.symbols),
            strtab_off, reloctab_off, len(sri.relocations),
        )

        buf.write(header)
        buf.write(sri.code)
        buf.write(sri.data)
        for sym in sri.symbols:
            buf.write(struct.pack("<IQIB",
                name_offsets.get(sym.name, 0), sym.address, sym.size, sym.sym_type))
        buf.write(bytes(strtab))
        for rel in sri.relocations:
            buf.write(struct.pack("<IBI", rel.offset, rel.reloc_type, rel.symbol_idx))

        return buf.getvalue()
