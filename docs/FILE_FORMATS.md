# Vir File Format Specification

*Version 1.0 — July 16, 2025*

---

## File Extensions

| Extension | Type | Description |
|-----------|------|-------------|
| `.vri` | Text | Vir source code (Vir Intermediate) |
| `.sri` | Binary | Serialized Runtime Image (compiled native code) |
| `.vsib` | Binary | Vir Static/Import Binary (library package) |

### Migration Note
Source files were previously `.vir`. All source files have been renamed to `.vri` as of Phase 7.

---

## SRI Binary Format (v1)

The SRI format stores compiled native machine code for a single compilation unit.

### Header (88 bytes, little-endian)

| Offset | Size | Field | Description |
|--------|------|-------|-------------|
| 0 | 4 | Magic | `SRI\x01` |
| 4 | 2 | Version | Format version (currently 1) |
| 6 | 2 | Arch | Target: 0=ARM64, 1=x86_64 |
| 8 | 4 | Flags | Bitfield (see below) |
| 12 | 8 | Entry point | Byte offset into code section |
| 20 | 8 | Code offset | File offset to code section |
| 28 | 8 | Code size | Size of code section in bytes |
| 36 | 8 | Data offset | File offset to data section |
| 44 | 8 | Data size | Size of data section in bytes |
| 52 | 8 | Symtab offset | File offset to symbol table |
| 60 | 4 | Symtab count | Number of symbol entries |
| 64 | 8 | Strtab offset | File offset to string table |
| 72 | 8 | Reloctab offset | File offset to relocation table |
| 80 | 4 | Reloc count | Number of relocation entries |

### Flags

| Bit | Name | Description |
|-----|------|-------------|
| 0 | `has_debug_info` | Debug information present |
| 1 | `position_independent` | PIC code (suitable for shared loading) |
| 2 | `has_bce_metadata` | BCE analysis metadata embedded |
| 3 | `has_escape_info` | Escape analysis info embedded |

### Symbol Table Entry (14 bytes)

| Size | Field | Description |
|------|-------|-------------|
| 4 | name_offset | Offset into string table |
| 8 | address | Address within code section |
| 4 | size | Size of the symbol's code |
| 1 | type | 0=function, 1=data, 2=extern |

### Relocation Entry (9 bytes)

| Size | Field | Description |
|------|-------|-------------|
| 4 | offset | Byte offset in code section |
| 1 | type | 0=ABS64, 1=REL32, 2=BRANCH26, 3=ADRP |
| 4 | symbol_idx | Index into symbol table |

### Usage

```python
from src.backend.formats import SRIBinary, SRISymbol

# Create
sri = SRIBinary(arch=0, code=b"\xd6\x5f\x03\xc0")
sri.symbols.append(SRISymbol("main", address=0, size=4))
sri.write("output.sri")

# Read
sri = SRIBinary.read("output.sri")
print(f"Arch: {'arm64' if sri.arch == 0 else 'x86_64'}")
print(f"Code size: {len(sri.code)} bytes")
```

### CLI

```bash
vir program.vri --emit-sri output.sri
```

---

## VSIB Library Format (v1)

The VSIB format bundles multiple compiled SRI modules into a single library file.

### Structure

```
┌───────────────────────────┐
│ Header (8 bytes)          │
│   Magic: "VSIB" (4)      │
│   Version: u16 (2)       │
│   Module count: u16 (2)  │
├───────────────────────────┤
│ Module Index              │
│   [name_off, sri_off,    │
│    sri_size] × N          │
├───────────────────────────┤
│ Module Bodies             │
│   <SRI binary> × N       │
├───────────────────────────┤
│ Export Table              │
│   Count: u32             │
│   [name_off, mod_idx,    │
│    addr] × M              │
├───────────────────────────┤
│ String Table              │
│   <null-terminated names> │
├───────────────────────────┤
│ Metadata                  │
│   Build timestamp: u64    │
│   Compiler version: str   │
│   Target arch: str        │
│   Opt level: u8           │
└───────────────────────────┘
```

### Module Index Entry (20 bytes)

| Size | Field | Description |
|------|-------|-------------|
| 4 | name_offset | Offset into string table |
| 8 | sri_offset | File offset to this module's SRI data |
| 8 | sri_size | Size of SRI data in bytes |

### Export Table Entry (16 bytes)

| Size | Field | Description |
|------|-------|-------------|
| 4 | name_offset | Offset into string table (format: `module::symbol`) |
| 4 | module_idx | Index into module list |
| 8 | address | Address within module's code section |

### Usage

```python
from src.backend.formats import VSIBLibrary, SRIBinary

lib = VSIBLibrary(compiler_version="vir-1.0", target_arch="arm64")

# Add compiled modules
math_sri = SRIBinary.read("math.sri")
lib.add_module("math", math_sri)

io_sri = SRIBinary.read("io.sri")
lib.add_module("io", io_sri)

lib.write("stdlib.vsib")
```

---

## Compilation Pipeline

```
.vri source → Lexer → Parser → AST → Q-IR → Optimizer (11 passes) → CodeGenerator
                                                                         ↓
                                                                    ┌─────────────┐
                                                                    │ .sri binary  │
                                                                    │ Mach-O .o    │
                                                                    │ JIT runtime  │
                                                                    └─────────────┘
                                                                         ↓
                                                              Multiple .sri → .vsib
```
