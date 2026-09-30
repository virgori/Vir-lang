# The Vir Programming Language

[![Release](https://img.shields.io/github/v/release/virgori/Vir-lang)](https://github.com/virgori/Vir-lang/releases/latest)

Vir is a systems programming language developed by Virgori Labs. The language
contract and implementation status are separate: see the
[language specification](docs/vir_language_spec_v2.0_en.md) and
[Architecture / Compiler Status](docs/COMPILER_STATUS.md).

## Implemented today

- A compiler written in Vir, with a release workflow that builds it using the
  checked-in bootstrap compiler and tests the resulting executable:
  [self-hosting build and smoke checks](.github/workflows/virc-release.yml).
  This is evidence of the tested bootstrap path, not a claim of bootstrap
  reproducibility or complete language conformance.
- AST parsing, semantic passes, MIR and LIR lowering, register allocation and
  machine-code emission: [pipeline and stage evidence](docs/COMPILER_STATUS.md).
- Direct binary writers: [Mach-O](stdlib/vir/compiler/macho.vri),
  [ELF](stdlib/vir/compiler/elf.vri), and
  [WASM](stdlib/vir/compiler/codegen_wasm.vri). The native release path does not
  invoke a C compiler or external linker to emit these compiler binaries.
  “Zero dependency” is scoped to that emission path: builds and CI still use
  Python, shell tools, macOS codesign, and Linux execution tooling; FFI programs
  can introduce external libraries. See the [release workflow](.github/workflows/virc-release.yml).
- Ownership and borrow checks have a [concrete memory contract suite](tests/memory_contract/README.md)
  and [MIR verification](stdlib/vir/compiler/mir_opt.vri).
  Memory safety is a [language contract](docs/vir_language_spec_v2.0_en.md),
  not a blanket certification of every backend, runtime or FFI program.
- Register allocation uses [graph coloring](stdlib/vir/compiler/lir_regalloc_color.vri)
  and [liveness analysis](stdlib/vir/compiler/lir_liveness.vri). No global
  “optimal” allocation claim is made.

Source presence identifies implementation; passing tests establish only their
covered behavior. Release validation currently covers macOS ARM64 and Linux
ARM64/x86_64 smoke execution. Other backends require their own evidence before
being advertised as release-supported.

## Getting started

Use the [latest release](https://github.com/virgori/Vir-lang/releases/latest)
and its published compiler assets. Installation commands should be documented
only alongside an installer maintained in this repository.

Check your installed version with `virc --version`. For examples and language
rules, start with the [language specification](docs/vir_language_spec_v2.0_en.md).

## Benchmarks

See [benchmark methodology and limitations](docs/BENCHMARKS.md) and the
[actual harness](bench/live_suite/run_benchmarks.py). Historical result files
are snapshots, not verified performance claims for the current release.

## Roadmap

[Planning documents](docs/plan/) describe intended work and experiments.
A plan, including one under `done/`, is not by itself proof of implementation.
Promotion into “Implemented today” requires an active source path and a test
or release check with a stated scope. See [compiler status](docs/COMPILER_STATUS.md)
for the distinction between the designed pipeline and its current wiring.

## Documentation

- [Architecture / Compiler Status](docs/COMPILER_STATUS.md)
- [Designed architecture](docs/ARCHITECTURE.md)
- [Language specification](docs/vir_language_spec_v2.0_en.md)
- [Benchmark methodology](docs/BENCHMARKS.md)
- [Release process and gates](docs/RELEASE_PROCESS.md)
- [VS Code extension](tools/vscode-vir/README.md)

## License

The previous README stated Apache 2.0, but this checkout contains no root
LICENSE or NOTICE. Confirm the repository-wide licensing files before relying
on that statement; the [editor extension license](tools/vscode-vir/LICENSE)
is scoped to that component.
