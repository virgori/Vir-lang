"""
obj_emitter.py – Mach-O Object File Emitter
=============================================
Emits relocatable Mach-O .o files from Q-IR, enabling separate
compilation of Vir modules. Each .vri file compiles to a .o that
can be linked with `ld` to produce an executable.

Usage:
    emitter = MachOEmitter(arch="arm64")
    emitter.add_function("add", machine_code_bytes)
    emitter.add_function("main", main_bytes)
    emitter.write("output.o")

Then link:
    ld -o output output.o runtime.o -lSystem -arch arm64
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Optional

from src.ir.instructions.q_ir import QModule, QFunction
from src.backend.codegen.codegen import CodeGenerator, TargetArch


# ═══════════════════════════════════════════════════════════
# Mach-O Constants
# ═══════════════════════════════════════════════════════════

# Magic numbers
MH_MAGIC_64 = 0xFEEDFACF

# CPU types
CPU_TYPE_X86_64 = 0x01000007
CPU_TYPE_ARM64 = 0x0100000C
CPU_SUBTYPE_ALL = 0x00000003
CPU_SUBTYPE_ARM64_ALL = 0x00000000

# File types
MH_OBJECT = 0x1

# Flags
MH_SUBSECTIONS_VIA_SYMBOLS = 0x2000

# Load commands
LC_SEGMENT_64 = 0x19
LC_SYMTAB = 0x02
LC_BUILD_VERSION = 0x32
LC_DYSYMTAB = 0x0B

# Section types
S_REGULAR = 0x0
S_ATTR_PURE_INSTRUCTIONS = 0x80000000
S_ATTR_SOME_INSTRUCTIONS = 0x00000400

# N-list types
N_SECT = 0x0E
N_EXT = 0x01
N_UNDF = 0x00

# Platform
PLATFORM_MACOS = 1


@dataclass
class Symbol:
    """A symbol table entry."""
    name: str
    offset: int  # offset within __text section
    size: int    # size of the code
    external: bool = True


@dataclass
class Relocation:
    """A relocation entry for cross-references."""
    offset: int     # offset in the section where fixup is needed
    symbol_idx: int # index into symbol table
    rtype: int = 2  # ARM64_RELOC_BRANCH26 or X86_64_RELOC_BRANCH
    length: int = 2 # 2 = 4 bytes
    pcrel: bool = True
    extern: bool = True


class MachOEmitter:
    """Emit relocatable Mach-O 64-bit object files."""

    def __init__(self, arch: str = "arm64") -> None:
        self.arch = arch
        self.symbols: list[Symbol] = []
        self.relocations: list[Relocation] = []
        self.text_data = bytearray()  # __text section content
        self._string_table = bytearray(b"\x00")  # starts with null byte
        self._string_offsets: dict[str, int] = {}

    def _add_string(self, s: str) -> int:
        """Add a string to the string table, return its offset."""
        if s in self._string_offsets:
            return self._string_offsets[s]
        offset = len(self._string_table)
        self._string_table.extend(s.encode("utf-8") + b"\x00")
        self._string_offsets[s] = offset
        return offset

    def add_function(self, name: str, code: bytes, external: bool = True) -> None:
        """Add a function's machine code to the object file."""
        offset = len(self.text_data)
        self.symbols.append(Symbol(
            name=f"_{name}",  # C symbol convention: prefix underscore
            offset=offset,
            size=len(code),
            external=external,
        ))
        self.text_data.extend(code)

    def add_relocation(self, offset: int, target_symbol: str) -> None:
        """Add a relocation for a call/branch to another symbol."""
        # Find symbol index
        target_name = f"_{target_symbol}"
        for idx, sym in enumerate(self.symbols):
            if sym.name == target_name:
                self.relocations.append(Relocation(
                    offset=offset,
                    symbol_idx=idx,
                ))
                return
        # External symbol — add as undefined
        undef_idx = len(self.symbols)
        self.symbols.append(Symbol(
            name=target_name,
            offset=0,
            size=0,
            external=True,
        ))
        self.relocations.append(Relocation(
            offset=offset,
            symbol_idx=undef_idx,
        ))

    def write(self, path: str) -> int:
        """Write the Mach-O object file. Returns bytes written."""
        # Build structured data
        text_section = bytes(self.text_data)
        text_size = len(text_section)

        # Build symbol table
        nlist_entries = bytearray()
        for sym in self.symbols:
            str_offset = self._add_string(sym.name)
            n_type = N_SECT
            if sym.external:
                n_type |= N_EXT
            if sym.size == 0 and sym.offset == 0:
                n_type = N_EXT  # undefined external
            n_sect = 1 if sym.size > 0 else 0  # section 1 = __text
            n_desc = 0
            n_value = sym.offset
            nlist_entries.extend(struct.pack("<IBBHQ",
                str_offset, n_type, n_sect, n_desc, n_value))

        strtab = bytes(self._string_table)
        symtab_size = len(nlist_entries)

        # Build relocation entries
        reloc_entries = bytearray()
        for rel in self.relocations:
            # Mach-O relocation_info: r_address (4), r_symbolnum:24 | r_pcrel:1 | r_length:2 | r_extern:1 | r_type:4
            info = (rel.symbol_idx & 0x00FFFFFF)
            info |= (1 if rel.pcrel else 0) << 24
            info |= (rel.length & 0x3) << 25
            info |= (1 if rel.extern else 0) << 27
            info |= (rel.rtype & 0xF) << 28
            reloc_entries.extend(struct.pack("<II", rel.offset, info))
        nreloc = len(self.relocations)
        reloc_size = len(reloc_entries)

        # CPU type
        if self.arch == "arm64":
            cpu_type = CPU_TYPE_ARM64
            cpu_subtype = CPU_SUBTYPE_ARM64_ALL
        else:
            cpu_type = CPU_TYPE_X86_64
            cpu_subtype = CPU_SUBTYPE_ALL

        # Layout:
        # 1. Mach-O header (32 bytes)
        # 2. LC_SEGMENT_64 (72 + 80 = 152 bytes) with __text section
        # 3. LC_SYMTAB (24 bytes)
        # 4. LC_DYSYMTAB (80 bytes)
        # 5. __text data (text_size)
        # 6. Relocations (reloc_size)
        # 7. Symbol table (symtab_size)
        # 8. String table (strtab)

        ncmds = 3  # SEGMENT_64 + SYMTAB + DYSYMTAB
        header_size = 32
        segment_cmd_size = 72 + 80  # segment header + 1 section header
        symtab_cmd_size = 24
        dysymtab_cmd_size = 80
        sizeofcmds = segment_cmd_size + symtab_cmd_size + dysymtab_cmd_size

        data_offset = header_size + sizeofcmds
        text_offset = data_offset
        reloc_offset = text_offset + text_size
        symtab_offset = reloc_offset + reloc_size
        strtab_offset = symtab_offset + symtab_size

        out = bytearray()

        # 1. Mach-O header
        out.extend(struct.pack("<IIIIIIII",
            MH_MAGIC_64,        # magic
            cpu_type,            # cputype
            cpu_subtype,         # cpusubtype
            MH_OBJECT,           # filetype
            ncmds,               # ncmds
            sizeofcmds,          # sizeofcmds
            MH_SUBSECTIONS_VIA_SYMBOLS,  # flags
            0,                   # reserved
        ))

        # 2. LC_SEGMENT_64
        segname = b"" + b"\x00" * 16  # unnamed segment for .o
        out.extend(struct.pack("<II", LC_SEGMENT_64, segment_cmd_size))
        out.extend(segname)  # segname (16 bytes)
        out.extend(struct.pack("<QQQQIIIII",
            0,                  # vmaddr
            text_size,          # vmsize
            text_offset,        # fileoff
            text_size,          # filesize
            7,                  # maxprot (rwx)
            7,                  # initprot (rwx)
            1,                  # nsects
            0,                  # flags
            0,                  # padding for 8-byte alignment
        ))

        # Section header: __text,__TEXT
        sectname = b"__text" + b"\x00" * 10  # 16 bytes
        segname2 = b"__TEXT" + b"\x00" * 11  # 16 bytes
        sect_flags = S_REGULAR | S_ATTR_PURE_INSTRUCTIONS | S_ATTR_SOME_INSTRUCTIONS
        out.extend(sectname)
        out.extend(segname2)
        out.extend(struct.pack("<QQIIIIIII",
            0,              # addr
            text_size,      # size
            text_offset,    # offset
            4 if self.arch == "arm64" else 0,  # align (2^4 = 16 for ARM64)
            reloc_offset if nreloc > 0 else 0,  # reloff
            nreloc,         # nreloc
            sect_flags,     # flags
            0,              # reserved1
            0,              # reserved2
        ))
        out.extend(struct.pack("<I", 0))  # reserved3

        # 3. LC_SYMTAB
        nsyms = len(self.symbols)
        out.extend(struct.pack("<IIIIII",
            LC_SYMTAB,
            symtab_cmd_size,
            symtab_offset,
            nsyms,
            strtab_offset,
            len(strtab),
        ))

        # 4. LC_DYSYMTAB
        n_local = sum(1 for s in self.symbols if not s.external)
        n_extern = sum(1 for s in self.symbols if s.external and s.size > 0)
        n_undef = sum(1 for s in self.symbols if s.external and s.size == 0)
        out.extend(struct.pack("<II", LC_DYSYMTAB, dysymtab_cmd_size))
        out.extend(struct.pack("<IIIIIIIIIIIIIIIIII",
            0, n_local,      # ilocalsym, nlocalsym
            n_local, n_extern, # iextdefsym, nextdefsym
            n_local + n_extern, n_undef,  # iundefsym, nundefsym
            0, 0,  # tocoff, ntoc
            0, 0,  # modtaboff, nmodtab
            0, 0,  # extrefsymoff, nextrefsyms
            0, 0,  # indirectsymoff, nindirectsyms
            0, 0,  # extreloff, nextrel
            0, 0,  # locreloff, nlocrel
        ))

        # 5. Section data
        out.extend(text_section)

        # 6. Relocations
        out.extend(reloc_entries)

        # 7. Symbol table
        out.extend(nlist_entries)

        # 8. String table
        out.extend(strtab)

        with open(path, "wb") as f:
            f.write(out)

        return len(out)


def compile_module_to_object(
    module: QModule,
    output_path: str,
    arch: str = "arm64",
) -> int:
    """Compile a QModule to a Mach-O .o file.

    Generates machine code for each function and writes them as
    exportable symbols in a relocatable object file.

    Returns the number of bytes written.
    """
    target = TargetArch.ARM64 if arch == "arm64" else TargetArch.X86_64
    codegen = CodeGenerator(arch=target)

    emitter = MachOEmitter(arch=arch)

    # Generate code for each function and add to object file
    for func in module.functions:
        # Build a simple code variant for the function
        buf = bytearray()
        for instr in func.body:
            # Use the fast code path for object files
            pass  # individual instr codegen handled by the generate() pipeline

    # Use the codegen pipeline to generate variants, then extract fast code
    variants = codegen.generate(module)

    # Also emit function bodies directly using the fast-path codegen
    # For each function, get the machine code from the variant or direct emission
    for func in module.functions:
        # Generate fast-path machine code for the function
        func_code = codegen._codegen_fast(func.body)
        emitter.add_function(func.name, bytes(func_code.bytes_))

    return emitter.write(output_path)


def compile_module_to_sri(
    module: QModule,
    output_path: str,
    arch: str = "arm64",
    entry: str = "main",
) -> None:
    """Compile a QModule to a .sri binary file.

    Uses the CodeGenerator's SRI emission pipeline to produce a
    Serialized Runtime Image containing fast-path machine code.
    """
    target = TargetArch.ARM64 if arch == "arm64" else TargetArch.X86_64
    codegen = CodeGenerator(arch=target)
    sri = codegen.emit_sri(module, entry=entry)
    sri.write(output_path)
