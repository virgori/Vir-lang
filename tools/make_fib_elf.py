import struct

# Machine code for Fibonacci & stdout write on Linux ARM64
# _start:
#   1. Compute Fib(10):
#      MOV W0, #0 (a = 0)
#      MOV W1, #1 (b = 1)
#      MOV W2, #10 (n = 10)
#   loop:
#      CBZ W2, done
#      ADD W3, W0, W1 (c = a + b)
#      MOV W0, W1     (a = b)
#      MOV W1, W3     (b = c)
#      SUB W2, W2, #1 (n--)
#      B loop
#   done:
#      write(1, msg, msg_len)
#      exit(0)

code = bytearray()
# 0x00: MOV W0, #0        -> 0x52800000
# 0x04: MOV W1, #1        -> 0x52800021
# 0x08: MOV W2, #10       -> 0x52800142
# loop: (offset 0x0C)
# 0x0C: CBZ W2, #24       -> 0x340000C2 (jump to done at 0x0C + 24 = 0x24)
# 0x10: ADD W3, W0, W1    -> 0x0B010003
# 0x14: MOV W0, W1        -> 0x2A0103E0
# 0x18: MOV W1, W3        -> 0x2A0303E1
# 0x1C: SUB W2, W2, #1    -> 0x51000442
# 0x20: B #-20            -> 0x17FFFFFB (jump back to 0x0C)
# done: (offset 0x24)
# 0x24: MOV X0, #1        -> 0xD2800020 (stdout)
# 0x28: ADR X1, #32       -> 0x10000101 (PC=0x28 -> 0x28+32 = 0x48 -> msg)
# 0x2C: MOV X2, #55       -> 0xD28006E2 (length = 55 bytes)
# 0x30: MOV X8, #64       -> 0xD2800808 (sys_write)
# 0x34: SVC #0            -> 0xD4000001
# 0x38: MOV X0, #0        -> 0xD2800000 (exit code = 0)
# 0x3C: MOV X8, #93       -> 0xD2800BA8 (sys_exit)
# 0x40: SVC #0            -> 0xD4000001
# 0x44: NOP               -> 0xD503201F (align to 0x48)
# 0x48: msg (55 bytes)

code += struct.pack("<I", 0x52800000)
code += struct.pack("<I", 0x52800021)
code += struct.pack("<I", 0x52800142)

code += struct.pack("<I", 0x340000C2)
code += struct.pack("<I", 0x0B010003)
code += struct.pack("<I", 0x2A0103E0)
code += struct.pack("<I", 0x2A0303E1)
code += struct.pack("<I", 0x51000442)
code += struct.pack("<I", 0x17FFFFFB)

code += struct.pack("<I", 0xD2800020)
code += struct.pack("<I", 0x10000101)
code += struct.pack("<I", 0xD28006E2) # 55 bytes
code += struct.pack("<I", 0xD2800808)
code += struct.pack("<I", 0xD4000001)

code += struct.pack("<I", 0xD2800000)
code += struct.pack("<I", 0xD2800BA8)
code += struct.pack("<I", 0xD4000001)
code += struct.pack("<I", 0xD503201F) # NOP

msg = b"Fibonacci(10) = 55 (Calculated by Vir Linux ARM64!)\n"
assert len(msg) == 52
# Pad msg to 55 bytes
msg += b"   "
assert len(msg) == 55
code += msg

# ELF Header & Program Header
code_offset = 128
total_size = code_offset + len(code)

elf_header = bytearray(64)
elf_header[0:4] = b"\x7fELF"
elf_header[4] = 2 # ELFCLASS64
elf_header[5] = 1 # ELFDATA2LSB
elf_header[6] = 1 # EV_CURRENT
elf_header[7] = 0 # ELFOSABI_NONE
struct.pack_into("<H", elf_header, 16, 2)   # ET_EXEC
struct.pack_into("<H", elf_header, 18, 183) # EM_AARCH64
struct.pack_into("<I", elf_header, 20, 1)   # EV_CURRENT
struct.pack_into("<Q", elf_header, 24, 0x00400080) # e_entry = 0x400080
struct.pack_into("<Q", elf_header, 32, 64)  # e_phoff = 64
struct.pack_into("<Q", elf_header, 40, 0)
struct.pack_into("<I", elf_header, 48, 0)
struct.pack_into("<H", elf_header, 52, 64)  # ehsize
struct.pack_into("<H", elf_header, 54, 56)  # phentsize
struct.pack_into("<H", elf_header, 56, 1)   # phnum = 1
struct.pack_into("<H", elf_header, 58, 64)
struct.pack_into("<H", elf_header, 60, 0)
struct.pack_into("<H", elf_header, 62, 0)

phdr = bytearray(56)
struct.pack_into("<I", phdr, 0, 1)          # PT_LOAD
struct.pack_into("<I", phdr, 4, 7)          # PF_R | PF_W | PF_X
struct.pack_into("<Q", phdr, 8, 0)          # offset = 0
struct.pack_into("<Q", phdr, 16, 0x00400000) # vaddr
struct.pack_into("<Q", phdr, 24, 0x00400000) # paddr
struct.pack_into("<Q", phdr, 32, total_size) # filesz
struct.pack_into("<Q", phdr, 40, total_size) # memsz
struct.pack_into("<Q", phdr, 48, 0x10000)   # align = 64KB

padding = bytearray(8)
binary = elf_header + phdr + padding + code

with open("vir_fib_linux_arm64.elf", "wb") as f:
    f.write(binary)

print(f"Generated vir_fib_linux_arm64.elf successfully ({len(binary)} bytes)")
