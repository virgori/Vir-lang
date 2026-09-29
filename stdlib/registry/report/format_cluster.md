# Report — Format / parse / fmt

**Registry:** [`../format.md`](../format.md) · [`../parse.md`](../parse.md) · [`../fmt.md`](../fmt.md)  
**Status:** design **closed**; compile **blocked**; `parse` docs-only

## Scope

| Module | Source | Notes |
|---|---|---|
| `format` | `io/format.vri` | int/float/bool formatters |
| `parse` | none yet | Proposed `parse.int` / float; today `parse_int` in types/string |
| `fmt` | `fmt/fmt.vri` | Template `format` / `printf` |

## Compile smoke

| Module | Result |
|---|---|
| `format` | FAIL E1001 |
| `parse` | FAIL E2102 (no module) |
| `fmt` | FAIL E1001 |

## Verdict

Do not claim user-facing format/parse until smoke passes. Land `parse` module per registry before removing ad-hoc `parse_int` from `types`. Float non-finite strings follow Decision C when format closes gates.
