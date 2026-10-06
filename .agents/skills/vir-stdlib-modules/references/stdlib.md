# Standard-library usage

## Resolve before use

Never invent a stdlib path or symbol. For each API:

1. Find the module identity in `stdlib/stdlib.vri`.
2. Open the mapped `.vri` source under `stdlib/vir/`.
3. Verify the symbol definition, signature, ownership behavior, and explicit
   `export` declaration.
4. Inspect a current positive caller/test.
5. Compile the smallest relevant fixture for the requested target.

`prelude.vri` and bootstrap/compiler preludes may differ. Verify which prelude
the active command injects; do not assume every module or helper is globally
available.

## Boundaries

- Public stdlib source belongs under `stdlib/vir/**` and is registered by
  `stdlib/stdlib.vri`.
- Compiler implementation belongs under `compiler/**` and is registered by
  `compiler/module.list`.
- A runtime symbol used only by compiler lowering or bootstrap code is not
  automatically a supported user API.
- `vir/mem/alloc` and `vir/rt/alloc` have distinct contracts; resolve the
  actual import before reasoning about allocation or release.

## Typical declaration order

At module level, keep dependencies and declarations in the canonical order:

```text
include -> import -> const -> var -> entity -> func -> export -> share
```

Only declare dependencies actually used. Prefer a focused selective import for
a public API dependency; use include intentionally when the whole include
contract is needed. Do not add a redundant include merely to make an import
resolve.
