# The Vir Programming Language

[![Release](https://img.shields.io/github/v/release/virgori/Vir-lang)](https://github.com/virgori/Vir-lang/releases/latest)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

Vir is a systems programming language developed by Virgori Labs. This is the
active Vir 3.0 source repository; the compiler currently reports `virc 4.2.1`
and the language server reports `vir-lsp 4.0.0`. The language contract and
implementation status are separate: see the
[language specification](papers/VIR/specs/VIR-SPC-0017_language_specification_english.md)
and [compiler source guide](compiler/README.md).

The repository state that previously occupied `main` is preserved under
[`Vir-2.0_legacy_`](Vir-2.0_legacy_/). Active compiler, standard-library,
paper, editor-extension, and language-server sources now live in `compiler/`,
`stdlib/`, `papers/`, `vscode-tool/`, and `vir-lsp/` respectively.

## Implemented today

- A compiler written in Vir, with canonical source under `compiler/src/` and a
  checked-in generated bundle under `compiler/generated/`. The
  [synchronization check](tools/sync_virc.py) verifies that the bundle matches
  its source modules. This is evidence of the tested bootstrap path, not a
  claim of complete language conformance.
- AST parsing, semantic passes, MIR and LIR lowering, register allocation, and
  machine-code emission are implemented in the
  [compiler source tree](compiler/src/).
- Direct binary writers are present for
  [Mach-O](compiler/src/backend/macho.vri),
  [ELF](compiler/src/backend/elf.vri), and
  [WASM](compiler/src/backend/codegen_wasm.vri). The checked-in native
  executables under `bin/` are macOS ARM64 builds; other targets require their
  own build and verification evidence.
- Ownership and borrow checks have a
  [concrete memory contract suite](tests/memory_contract/README.md) and
  [MIR verification](compiler/src/ir/mir/mir_opt.vri). Memory safety is a
  [language contract](papers/VIR/specs/VIR-SPC-0005_memory_management.md), not
  a blanket certification of every backend, runtime, or FFI program.
- Register allocation uses
  [graph coloring](compiler/src/ir/lir/lir_regalloc_color.vri) and
  [liveness analysis](compiler/src/ir/lir/lir_liveness.vri). The governing
  design is documented in the
  [register-allocation paper](papers/VIRC/specs/VIRC-SPC-0003_register_allocation.md).
  No global “optimal” allocation claim is made.
- Native editor support is provided by the
  [Vir language server](vir-lsp/README.md) and
  [VS Code extension](vscode-tool/README.md).

Source presence identifies implementation; passing tests establish only their
covered behavior. Release support for a target requires its own reproducible
build, smoke execution, and documented evidence.

## Getting started

The repository includes macOS ARM64 executables in `bin/`:

```sh
./bin/virc --version
./bin/vir-lsp --version
```

For language rules, start with the
[English specification](papers/VIR/specs/VIR-SPC-0017_language_specification_english.md)
or the
[Vietnamese specification](papers/VIR/specs/VIR-SPC-0018_language_specification_vietnamese.md).

Repository checks:

```sh
python3 tools/sync_virc.py --check
./paper registry --check
./paper validate
```

## Benchmarks

The previous benchmark methodology and harness are preserved as historical
material under
[`Vir-2.0_legacy_/docs/BENCHMARKS.md`](Vir-2.0_legacy_/docs/BENCHMARKS.md) and
[`Vir-2.0_legacy_/bench/live_suite/run_benchmarks.py`](Vir-2.0_legacy_/bench/live_suite/run_benchmarks.py).
Historical result files are snapshots, not verified performance claims for the
current source tree.

## Roadmap

[VPS planning papers](papers/VIRC/plans/) describe intended compiler work and
experiments. A plan is not by itself proof of implementation. Promotion into
“Implemented today” requires an active source path and a test or report with a
stated scope. See the [VPS registry](papers/REGISTRY.yaml) and
[implementation reports](papers/VIRC/reports/) for traceable status and
evidence.

## Documentation

- [Compiler source guide](compiler/README.md)
- [Language specification — English](papers/VIR/specs/VIR-SPC-0017_language_specification_english.md)
- [Language specification — Vietnamese](papers/VIR/specs/VIR-SPC-0018_language_specification_vietnamese.md)
- [Memory management](papers/VIR/specs/VIR-SPC-0005_memory_management.md)
- [Module and include system](papers/VIR/specs/VIR-SPC-0006_module_include_system.md)
- [Self-hosting specification](papers/VIRC/specs/VIRC-SPC-0004_self_hosting.md)
- [Standard library](stdlib/README.md)
- [VPS paper standard](papers/STANDARD.md)
- [Vir language server](vir-lsp/README.md)
- [VS Code extension](vscode-tool/README.md)

## License

Unless a subdirectory states otherwise, this repository is licensed under the
[Apache License 2.0](LICENSE). The VS Code extension retains its existing
[MIT license](vscode-tool/LICENSE).
