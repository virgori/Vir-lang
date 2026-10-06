---
id: "VIR-ISS-0005"
type: "ISSUE"
domain: "VIR"
title: "The has and get constructs duplicate existing resolution mechanisms and lack working semantics"
status: "RESOLVED"
severity: "S2"
priority: "P1"
created: "2026-10-06"
updated: "2026-10-06"
owners:
  - "language"
components:
  - "functions"
  - "modules"
  - "language-specification"
related:
  issues:
    - "VIR-ISS-0007"
    - "VIRC-ISS-0008"
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags:
  - "has"
  - "get"
  - "forward-declaration"
  - "selective-import"
  - "language-simplification"
  - "breaking-change"
  - "spec-conformance"
---

# VIR-ISS-0005 — The has and get constructs duplicate existing resolution mechanisms and lack working semantics

## 1. Summary

The active Vir language specifications define two constructs that duplicate
capabilities already provided by the language and are not implemented as a
coherent end-to-end contract:

- `has name` is described as a function forward declaration, although function
  definitions are already collected independently of source order. It carries
  no parameter or result signature and the current semantic pass registers it
  as a variable, so it cannot serve as a sound function declaration.
- standalone `get name from module [as alias]` is described as the way to bring
  constants and variables into scope, although `import name from module [as
  alias]` already represents selective named imports. The parser lowers both
  spellings to `ImportStmt`, but the source import expander recognizes only
  `import` and `from`, so standalone `get` does not resolve the requested
  module symbol in a complete compile.

For Vir 3.0, this ISSUE proposes removing both language constructs from the
normative grammar and reserving one mechanism for each concern: ordinary
order-independent function definitions and `import`/`export` for module API
access. After removal, `get` remains available as an ordinary identifier or
member name, such as `net.http.get`.

## 2. Context

VIR-SPC-0017 section 6.5 and VIR-SPC-0018 section 6.5 each show only
`has processData` and label it a forward declaration. Neither section defines
a callable signature, compatibility rule with the later definition, separate
declaration versus definition semantics, or a diagnostic for mismatch.
VIR-SPC-0013, the focused function specification, does not establish a
corresponding `has` contract.

VIR-SPC-0014 and sections 3.3-3.8 of VIR-SPC-0017/VIR-SPC-0018 split selective
imports by declaration kind: `import` for functions and standalone `get` for
variables/constants. The same specifications already use
`import get from net.http as fetch`, proving that `get` is also intended to be
a normal exported symbol name. They additionally define combined import
syntax, aliases, and `export`, leaving two surface spellings for one
name-binding operation.

This ISSUE owns only the language-level decision and normative-document cleanup.
Compiler, standard-library, formatter, grammar, language-server, migration, and
test changes are downstream VIRC/tooling conformance work and do not gate
resolution of this VIR documentation ISSUE.

## 3. Expected Behavior

- Functions may be referenced according to the language's normal lexical and
  module resolution rules regardless of whether their definitions appear
  earlier or later in a source file; no `has` declaration is required.
- A function declaration that genuinely has no Vir body uses the existing,
  fully typed `extern func`/FFI contract. A future interface or trait contract
  must use separate, signature-bearing syntax rather than reviving `has`.
- `import name from module` imports any explicitly exported named declaration
  supported by the module system, including functions, types, constants, and
  variables. `import name from module as alias` is its alias form.
- `export` remains the sole declaration of a module's public API and import
  visibility is enforced consistently for every declaration kind.
- `has` and standalone module-directive `get ... from ...` are absent from the
  Vir 3.0 grammar, keyword tables, AST, and normative examples.
- The spelling `get` is legal as an ordinary function, method, field, or local
  identifier and continues to work in qualified calls such as `http.get(...)`.

## 4. Actual Behavior

- VIR-SPC-0017 and VIR-SPC-0018 list `has` as a forward-declaration keyword and
  list standalone `get` as the variable/constant import directive.
- The semantic symbol walk registers ordinary `FuncDef` nodes as functions,
  but groups `HasDecl` with `ShareDecl` and registers both as variables. A
  later function definition of the same name therefore conflicts with the
  supposed declaration instead of completing it.
- Calls to functions defined later in the same module succeed without `has`,
  demonstrating that the construct adds no required declaration-order
  capability in the audited pipeline.
- The parser converts standalone `get` to `ImportStmt`, including an optional
  alias. It does not require the `from` token because the result of
  `match_tok(..., TokType.From)` is ignored.
- The source import expander scans line starts only for `import ` and `from `.
  It does not discover standalone `get `, so the parsed AST shape is not backed
  by module loading and symbol expansion in a full compile.
- Existing self-host parser tests only assert a minimum number of AST children;
  they do not prove name resolution, export enforcement, alias behavior,
  execution, or rejection of malformed syntax.

## 5. Reproduction

The audit used minimal project fixtures with a `module.list` mapping `provider`
to `provider.vri` and the following source forms.

`has` is unnecessary for a later definition:

```vir
func main:
    out helper()
end.

func helper -> int:
    out 7
end.
```

Adding the following line before `main` changes the symbol classification and
causes a duplicate/conflicting declaration diagnostic:

```vir
has helper
```

Standalone `get` parses and passes the semantic check but does not survive a
full compile:

```vir
# provider.vri
const ANSWER = 42
export ANSWER
```

```vir
# main.vri
get ANSWER from provider

func main:
    out ANSWER
end.
```

The canonical selective import succeeds for the same provider:

```vir
import ANSWER from provider

func main:
    out ANSWER
end.
```

Representative commands from repository root:

```sh
./bin/virc /private/tmp/vir_keyword_audit/no_has.vri --check --json --color=never
./bin/virc /private/tmp/vir_keyword_audit/with_has.vri --check --json --color=never
./bin/virc /private/tmp/vir_keyword_audit/get_project/main.vri --check --json --color=never
./bin/virc /private/tmp/vir_keyword_audit/get_project/main.vri -o /private/tmp/vir_keyword_audit/get_out --color=never
./bin/virc /private/tmp/vir_keyword_audit/import_project/main.vri -o /private/tmp/vir_keyword_audit/import_out --color=never
```

## 6. Evidence

- CONFIRMED: VIR-SPC-0017:445-517 and VIR-SPC-0018:441-522 define both
  `import` and standalone `get`; their keyword/reference tables repeat the
  distinction near VIR-SPC-0017:3798,3891,3955-3956 and
  VIR-SPC-0018:3822,3918,4016-4017.
- CONFIRMED: VIR-SPC-0017:1234 and VIR-SPC-0018:1210 are the complete
  normative examples for `has`; neither supplies a type signature.
- CONFIRMED: `compiler/src/frontend/lexer/tokens.vri:317,389` reserves both
  spellings as token kinds; `compiler/src/frontend/parser/ast.vri:107` retains
  a dedicated `HasDecl` node.
- CONFIRMED: `compiler/src/frontend/parser/stmt_module.vri:99-122` converts
  standalone `get` to `ImportStmt` and ignores whether `from` matched.
- CONFIRMED: `compiler/src/main/import_expander.vri:14-43` searches only for
  line-start `import ` and `from ` statements.
- CONFIRMED: `compiler/src/semantic/symbols/walk.vri:72-115,228-233`
  registers `FuncDef` as `SymbolKind.Func` but `HasDecl` as
  `SymbolKind.Variable`.
- CONFIRMED: `compiler/src/lower/ast_to_mir/stmt.vri:692` discards `HasDecl`
  during lowering.
- CONFIRMED: `stdlib/vir/test/type_system_vtest.vri:238-258` tests the two
  spellings only by parsing and counting AST children.
- OBSERVED on 2026-10-06 at checkout HEAD `e1fc2d5` with the current working
  tree: a later-defined function compiled without `has`; adding `has` produced
  E1001; standalone `get` passed `--check` but a full compile failed with an
  unresolved identifier during lowering; the equivalent `import` compiled.
- OBSERVED: standalone `get` of an unexported symbol and the alias form reached
  the same unresolved-identifier failure, so the audit did not observe a
  working export-aware path for the directive.
- CONFIRMED: `python3 tools/sync_virc.py --check` passed during the audit, so
  the modular and generated compiler sources were synchronized for these
  observations.

## 7. Scope

### Affected

- VIR-SPC-0013, VIR-SPC-0014, VIR-SPC-0017, VIR-SPC-0018, and any AI/human
  mirrors or keyword indexes that describe `has` or standalone `get`;
- normative module ordering, function declaration-order rules, import semantics,
  migration guidance, and derived agent guidance.

### Not affected / Unknown

- Ordinary function/method/member names spelled `get`, including
  `import get from net.http as fetch` and `http.get(...)`, are not removed.
- `import`, `include`, `export`, `share`, and typed `extern func` remain language
  constructs; this ISSUE does not redesign their unrelated semantics.
- Compiler/parser/AST/formatter/LSP removal, compatibility diagnostics, source
  migration, tests, and bootstrap state are outside this language-document
  ISSUE and must be tracked in VIRC/tooling work where required.
- VIRC-ISS-0008 owns the broader private-by-default/export-enforcement defect.
  This ISSUE must not close that work merely by consolidating import syntax.
- This ISSUE does not design a new trait/interface declaration form.
- NOT_VERIFIED: the number of external Vir projects that currently use either
  construct.
- NOT_VERIFIED: whether a staged deprecation is required for any supported
  compatibility channel; the proposed Vir 3.0 resolution is direct removal.

## 8. Impact

Keeping the constructs makes the language harder to explain while exposing
users to paths that parse but do not deliver the specified behavior. `has`
suggests a declaration contract that has neither a signature nor compatible
semantic identity. standalone `get` splits one module operation by declaration
kind and bypasses the working textual import-expansion path.

Removal makes the grammar and implementation smaller, gives import/export one
authoritative path, and releases `get` for ordinary API naming. It is a source
compatibility break for code that uses the two directives, but both migrations
are mechanical: delete `has` declarations and replace `get X from M [as A]`
with `import X from M [as A]`.

Severity is S2 because there are straightforward working alternatives and the
failure does not require silent code generation. Priority is P1 because the
decision affects the Vir 3.0 grammar, compiler surface, tooling, and migration
story and should be settled before those interfaces are frozen.

## 9. Preliminary Analysis

- CONFIRMED: the compiler already collects real function definitions as
  function symbols, and an audited later-definition call does not need `has`.
- CONFIRMED: `has` lacks the signature information needed for overload,
  parameter, result, ABI, or declaration-definition compatibility checking.
- CONFIRMED: both `get X from M` and `import X from M` are parsed as selective
  `ImportStmt` nodes, while only the latter is discovered by the source import
  expander.
- CONFIRMED: the existing `import` form already supports aliases and naturally
  names a symbol spelled `get`; a second directive is not needed for that API.
- HYPOTHESIS: direct removal in Vir 3.0 is lower risk than preserving a
  deprecation period because current `has` and standalone `get` behavior is
  incomplete and each has a mechanical replacement.
- HYPOTHESIS: removing `get` from the reserved-keyword table will simplify API
  naming, but parser contexts that currently special-case `TokType.Get` must be
  audited before implementation.
- NOT_VERIFIED: the complete external ecosystem migration count and whether
  generated or vendored sources outside this repository contain either form.
- NOT_VERIFIED: the final diagnostic codes and compatibility window; those
  belong in the implementation PLAN after the language decision is accepted.

## 10. Acceptance Criteria

- [x] The active English and Vietnamese language specifications remove `has`
  and standalone `get ... from ...` from normative grammar, examples, ordering
  rules, dependency-graph text, keyword tables, and quick references.
- [x] The focused function and module specifications state that function lookup
  is declaration-order independent and that `import name from module [as
  alias]` covers every supported exported declaration kind.
- [x] The specifications retain `get` as a legal ordinary identifier/member
  spelling and include a conforming example such as `http.get(...)` or
  `import get from net.http as fetch`.
- [x] The specifications distinguish bodyless typed `extern func` declarations
  from ordinary Vir function definitions and do not assign that role to `has`.
- [x] Active SPEC versions and revision histories record the Vir 3.0 breaking
  change, migration mapping, and English/Vietnamese parity.
- [x] Derived Vir agent guidance uses selective `import` for every exported
  declaration kind and treats `get` only as an ordinary identifier.

Compiler acceptance, diagnostics, source migration, conformance tests and
bootstrap convergence are deliberately not acceptance criteria of this VIR
documentation ISSUE. They require independent VIRC/tooling tracking.

## 11. Related Papers

### Issues

- `VIR-ISS-0007` — loại riêng `lazy include`/`lazy import` khỏi active module
  specifications; phối hợp cùng cleanup `get` nhưng không trùng ownership.
- `VIRC-ISS-0008` — selective imports currently accept symbols that are not
  exported when the provider has no export list. Consolidating syntax does not
  remove the need for fail-closed visibility enforcement.

### Plans

- None yet.

### Reports

- None yet.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-06 | Opened from the `has`/standalone-`get` spec and compiler audit; proposed direct Vir 3.0 removal |
| 2026-10-06 | Linked VIRC-ISS-0008 |
| 2026-10-06 | Linked VIR-ISS-0007 |
| 2026-10-06 | Resolved the language-document scope in VIR-SPC-0006/0013/0014/0017/0018 and separated compiler conformance from VIR acceptance |
