# String interpolation target-matrix report

## Verified native target matrix

The MC assembly path now lowers `MIR_INTR_STR_LIT` into target-specific
symbol-address materialization and emits the referenced NUL-terminated bytes
in the final read-only data section.

| Target | Link/run method | Result |
| --- | --- | --- |
| macOS ARM64 | native Mach-O output | `Hello Vir`, `count=42`, exit 0 |
| Linux ARM64 | `aarch64-linux-gnu-gcc -static -no-pie` on Quizzman | exact output, exit 0 |
| Linux x86-64 | `x86_64-linux-gnu-gcc -static -no-pie` on Quizzman | exact output, exit 0 |
| Linux RISC-V 64 | `riscv64-linux-gnu-gcc -static -no-pie`, `qemu-riscv64` on Quizzman | exact output, exit 0 |

The regression source is `tests/test_interp_v2.vri`. It explicitly returns
zero and requires exact interpolation of both a string and an integer.

## Implemented path

- `lir_to_mc.vri`: ARM64 uses `ADRP` + low-12-bit `ADD`; x86-64 uses RIP
  relative `LEA`; RISC-V uses `la`.
- `mc_printer.vri`: emits Darwin `__TEXT,__cstring` or ELF `.rodata` string
  pools, architecture-correct address instructions, and newline-consistent
  string-print runtime stubs.
- `virc.vri`: appends the string pool after generated functions and runtime
  stubs.

## Remaining non-passing targets/features

### wasm32-wasi-p1

This is a compiler defect, not a missing local runtime. Node.js is available
as a local WASM host, but compiling `test_interp_v2.vri` with
`--target wasm32-wasi-p1` currently terminates with `SIGSEGV` before creating
the `.wasm` file. The active driver still constructs placeholder empty
`QIRFunc` bodies instead of lowering active LIR/MIR into WASM instructions.
It cannot be described as end-to-end implemented.

### Float literals

`tests/test_literals_v2.vri` is intentionally strict and currently fails at
its `3.14 != 0.0` guard. `native_parse_float` has no self-hosted runtime
implementation, so the lexer stores `3.14` as zero before MIR lowering. The
ARM64 MC printer now materializes arbitrary i64 immediates correctly with
`movz`/`movk`, but that cannot repair a value lost during lexing. Boolean and
`none` literal checks pass before the float guard.
