# FFI extern import report

Date: 2026-09-07  
Commit: `08a2449b add target-neutral extern imports`

## Outcome

The compiler now keeps an external declaration as linker metadata rather than
lowering it into an empty MIR/LIR function whose only operation is `ret`.

Accepted declaration forms:

```vir
extern func getpid() -> int
extern from os func getpid() -> int
extern from "/usr/lib/libSystem.B.dylib" func getuid() -> int
```

`extern func` remains a compatibility spelling for `extern from os`. An
external declaration is declaration-only; it is not emitted as a local
function body.

## Compiler flow

1. Parser retains the function signature and the import source in the AST.
2. AST-to-MIR records extern declarations in a target-neutral import registry
   and skips construction of a local `MirFunc`.
3. ARM64 LIR codegen records only imports reached by a call, emits a three
   instruction thunk (`ADRP`, `LDR`, `BR`) for each, and redirects the call to
   that thunk.
4. The Mach-O writer creates `__stubs`, `__la_symbol_ptr`, undefined `nlist`
   records, indirect symbols, `LC_DYLD_INFO_ONLY` binding data, and one
   `LC_LOAD_DYLIB` per distinct source library. `from os` resolves to
   `/usr/lib/libSystem.B.dylib` on the Mach-O path.

The registry intentionally has no Mach-O field. This gives ELF a future
`DT_NEEDED` + `.plt`/`.got` input, PE/COFF an IAT input, and Wasm an import
section input without changing parser, MIR, or LIR call identification.

## Files added

- [stdlib/vir/compiler/ffi_imports.vri](/Users/gengyang/Vir/stdlib/vir/compiler/ffi_imports.vri) — target-neutral declaration, use, and ARM64-stub registry.
- [tests/test_extern_from_os.vri](/Users/gengyang/Vir/tests/test_extern_from_os.vri) — syntax and call smoke test.
- [docs/report/FFI_EXTERN_IMPORT_REPORT.md](/Users/gengyang/Vir/docs/report/FFI_EXTERN_IMPORT_REPORT.md) — this report.

## Files changed

- [stdlib/vir/compiler/parser.vri](/Users/gengyang/Vir/stdlib/vir/compiler/parser.vri)
- [stdlib/vir/compiler/ast_to_mir.vri](/Users/gengyang/Vir/stdlib/vir/compiler/ast_to_mir.vri)
- [stdlib/vir/compiler/lir_codegen.vri](/Users/gengyang/Vir/stdlib/vir/compiler/lir_codegen.vri)
- [stdlib/vir/compiler/macho.vri](/Users/gengyang/Vir/stdlib/vir/compiler/macho.vri)
- [docs/vir_language_spec_v2.0_vi.md](/Users/gengyang/Vir/docs/vir_language_spec_v2.0_vi.md)
- [docs/vir_language_spec_v2.0_en.md](/Users/gengyang/Vir/docs/vir_language_spec_v2.0_en.md)

## Verification and limitation

`./bin/virc stdlib/vir/compiler/virc.vri -o /private/tmp/virc-ffi/virc-dynamic3`
completed successfully after the change.

The generated self-hosted stage-1 binary exits before producing its requested
output in this environment, including when run outside the sandbox. Therefore
the compile-time integration build passes, but this commit does not claim an
end-to-end dyld execution test. Add that test before declaring the Mach-O ABI
path production-ready.

ELF, x86-64 Mach-O, PE/COFF, and Wasm currently share the metadata design only;
their format-specific import emitters are not implemented by this commit.
