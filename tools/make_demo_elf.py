import struct

# 1. ARM64 Machine code (64 bytes)
# 0x00: MOV X0, #1           -> 0xD2800020
# 0x04: ADR X1, #32          -> 0x10000101 (points to msg at offset +32 / 0x20)
# 0x08: MOV X2, #32          -> 0xD2800402 (length = 32 bytes)
# 0x0C: MOV X8, #64          -> 0xD2800808 (Linux sys_write = 64)
# 0x10: SVC #0               -> 0xD4000001
# 0x14: MOV X0, #42          -> 0xD2800540 (exit code = 42)
# 0x18: MOV X8, #93          -> 0xD2800BA8 (Linux sys_exit = 93)
# 0x1C: SVC #0               -> 0xD4000001
# 0x20: "Hello from Vir Linux ARM64 ELF!\n" (32 bytes)

code = bytearray()
code += struct.pack("<I", 0xD2800020) # MOV X0, #1 (stdout)
code += struct.pack("<I", 0x100000E1) # ADR X1, #28 (PC=0x04 -> 0x04+28 = 0x20 -> 'H')
code += struct.pack("<I", 0xD2800402) # MOV X2, #32 (length)
code += struct.pack("<I", 0xD2800808) # MOV X8, #64 (sys_write)
code += struct.pack("<I", 0xD4000001) # SVC #0

code += struct.pack("<I", 0xD2800540)
code += struct.pack("<I", 0xD2800BA8)
code += struct.pack("<I", 0xD4000001)

msg = b"Hello from Vir Linux ARM64 ELF!\n"
assert len(msg) == 32
code += msg
assert len(code) == 64

# 2. ELF Header (64 bytes)
code_offset = 128
total_size = code_offset + len(code) # 192 bytes

elf_header = bytearray(64)
# e_ident
elf_header[0:4] = b"\x7fELF"
elf_header[4] = 2 # ELFCLASS64
elf_header[5] = 1 # ELFDATA2LSB (little-endian)
elf_header[6] = 1 # EV_CURRENT
elf_header[7] = 0 # ELFOSABI_NONE
# e_type = ET_EXEC (2)
struct.pack_into("<H", elf_header, 16, 2)
# e_machine = EM_AARCH64 (183)
struct.pack_into("<H", elf_header, 18, 183)
# e_version = 1
struct.pack_into("<I", elf_header, 20, 1)
# e_entry = 0x400000 + 128 = 0x400080
struct.pack_into("<Q", elf_header, 24, 0x00400080)
# e_phoff = 64
struct.pack_into("<Q", elf_header, 32, 64)
# e_shoff = 0
struct.pack_into("<Q", elf_header, 40, 0)
# e_flags = 0
struct.pack_into("<I", elf_header, 48, 0)
# e_ehsize = 64
struct.pack_into("<H", elf_header, 52, 64)
# e_phentsize = 56
struct.pack_into("<H", elf_header, 54, 56)
# e_phnum = 1
struct.pack_into("<H", elf_header, 56, 1)
# e_shentsize = 64
struct.pack_into("<H", elf_header, 58, 64)
# e_shnum = 0
struct.pack_into("<H", elf_header, 60, 0)
# e_shstrndx = 0
struct.pack_into("<H", elf_header, 62, 0)

# 3. Program Header (56 bytes)
phdr = bytearray(56)
# p_type = PT_LOAD (1)
struct.pack_into("<I", phdr, 0, 1)
# p_flags = PF_R | PF_W | PF_X (7)
struct.pack_into("<I", phdr, 4, 7)
# p_offset = 0
struct.pack_into("<Q", phdr, 8, 0)
# p_vaddr = 0x400000
struct.pack_into("<Q", phdr, 16, 0x00400000)
# p_paddr = 0x400000
struct.pack_into("<Q", phdr, 24, 0x00400000)
# p_filesz = total_size
struct.pack_into("<Q", phdr, 32, total_size)
# p_memsz = total_size
struct.pack_into("<Q", phdr, 40, total_size)
# p_align = 0x10000 (64KB)
struct.pack_into("<Q", phdr, 48, 0x10000)

# 4. Assemble binary
padding = bytearray(8) # 64 + 56 + 8 = 128
binary = elf_header + phdr + padding + code
assert len(binary) == 192

with open("vir_linux_arm64_demo.elf", "wb") as f:
    f.write(binary)

print("Generated vir_linux_arm64_demo.elf successfully (192 bytes)")
