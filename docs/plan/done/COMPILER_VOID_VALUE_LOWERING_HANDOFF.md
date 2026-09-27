# Compiler handoff: `void` value reaches AST→MIR unresolved

Status: fixed locally on 2026-09-25; regression, fixed-point, and full suite verified.

## Symptom

After the I-Ching server passed all semantic passes with zero errors and zero warnings, `virc` aborted during lowering:

```text
virc: error: lowering unresolved identifier: void
```

Minimal reproduction:

```vir
include types
include result
import Result from result

func unit_result() -> Result<void, string>:
    out Result.Ok(void)
end.
```

The production trigger was `Result.Ok(void)` in `stdlib/vir/fs/fs.vri` (first observed at line 122). The same valid unit-value form also exists in other stdlib modules.

## Root cause

The front end already treats `void` as a predefined value/type:

- name resolution accepts `void`;
- semantic type checking maps it to the no-value/unit type;
- constant/name handling already recognizes `true`, `false`, `null`, and partially recognizes `void`.

However, `stdlib/vir/compiler/ast_to_mir.vri` lowered identifier literals `true`, `false`, and `null` to MIR immediates, but omitted `void`. Consequently, a valid `void` expression fell through to ordinary symbol lookup and produced the late “unresolved identifier” failure.

This is a compiler lowering bug, not an `fs` or `Result` API bug. Do not replace `Result.Ok(void)` with `Result.Ok(0)` as a workaround because that changes the inferred public payload type.

## Local fix

In `eval_const_expr`, map `void` to immediate zero, matching the unit representation used for `null`/no-value. In the identifier branch of `lower_expr`, map `void` to `mir_opnd_imm(0)` before symbol lookup.

Changed source:

- `stdlib/vir/compiler/ast_to_mir.vri`
- synchronized bundle: `stdlib/vir/compiler/virc.vri`
- regression: `tests/test_void_value_lowering.vri`

`bin/virc` was rebuilt through three self-host stages and promoted from stage 3.

## Verification

- `tests/test_void_value_lowering.vri`: compile PASS, runtime exit 0.
- I-Ching `server.vri`: compile PASS with 0 errors and 0 warnings.
- Fixed point: stage 2 and stage 3 are byte-identical.
- Stage 2/3 SHA-256: `dc8d001e92370064596e43fa4ff21b93435dbb195c13b88922e9a81110148554`.
- InterVir CORS unit test: compile PASS and prints `ALL CORS TESTS PASSED`.
- `./run_tests.sh full`: 731/731 PASS (100%).

## Workspace warning

The worktree already contained unrelated compiler edits. A targeted synchronization was used:

```sh
python3 tools/sync_virc.py ast_to_mir.vri
```

At handoff time, `python3 tools/sync_virc.py --check` still reports pre-existing drift in:

- `parser.vri`
- `sem_pass10_diagnostics.vri`
- `sem_pass3_names.vri`
- `sem_pass4_types.vri`
- `type_table.vri`

Do not run an unreviewed full sync or overwrite those modules while another compiler agent may still be developing them.

## Related project fixes that exposed this compiler bug

- Added explicit `-> string` to `hex_name_vi`, `hex_name_han`, and `hex_full_name_han`.
- Added conservative fallback `out` statements after nested `case` blocks in `json_lookup.vri`, removing three W4001 warnings without changing successful branches.
- Replaced the CORS entity-method call that passed a cast literal through broken UFCS checking with its existing free-function wrapper and an owned two-byte wildcard buffer.

The string ABI migration remains a separate concern. Current `virc` still lowers plain string literals as raw addresses in cases where treating them as the `String { data, byte_len, char_len }` entity and reading `.data` can segfault. Do not claim fat-string migration complete based only on this fix.
