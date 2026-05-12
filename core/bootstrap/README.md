# Bootstrap Layout

This directory mixes standalone demo/test programs with bootstrap library files.

Library-only files:
- `ir_optimize.vri`: optimizer pass library; expects compiler AST globals/helpers from `compiler.vri`.

Programs that require argv/input context:
- `compiler.vri`
- `test_compiler.vri`
- `vir_parser.vri`
- `vir_parser_legacy.vri`

Programs previously re-verified with the default C binary at `core/build/vir` during the March 2026 compiler-fix pass:
- `test_structs.vri`
- `test_all_features.vri`

Most other `.vri` files here are standalone demos or focused regression programs.
If a future sweep reports `ir_optimize.vri` as a failure, classify that as an invocation mistake first, not a parser/lowerer regression.