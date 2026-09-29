#!/usr/bin/env python3
"""
tools/generate_stdlib_registry.py — Generate canonical stdlib/stdlib.vri registry
Adheres strictly to the Vir v2.0 module naming specification:
  1. Functional dot hierarchy: e.g. compiler.mir.ssa, compiler.ra.color, compiler.lower.mir
  2. Single concise words when meaning is clear: e.g. parsekit, collections.concurrent, async.tasks, viron.fs
  3. Clean test module names without '_vtest' suffix: e.g. test.codegen, test.compiler, test.types, test.bench, test.simd
  4. Standalone / distinct directory packages use straight names: e.g. virgex, regex, json, alloc, types
"""

from pathlib import Path
from collections import OrderedDict

ROOT = Path(__file__).resolve().parents[1]
STDLIB_DIR = ROOT / "stdlib/vir"
OUTPUT_REGISTRY = ROOT / "stdlib/stdlib.vri"

# 1. Canonical Preludes (Spec Section III.3)
PRELUDES = [
    ("types", "core/types.vri"),
    ("option", "core/option.vri"),
    ("result", "core/result.vri"),
    ("alloc", "compiler/alloc_prelude.vri"),
    ("syscall", "compiler/syscall_prelude.vri"),
    ("vec", "compiler/vec_prelude.vri"),
    ("string", "str/string.vri"),
    ("io", "rt/io.vri"),
    ("string_rt", "compiler/string_rt_prelude.vri"),
    ("vec_rt", "rt/vec_rt.vri"),
]

# Explicit overrides mapping relative file paths to canonical names
OVERRIDES = {
    # ── Rule 2: Single-word when already clear ───────────────────────────────
    "compiler/types_prelude.vri": "compiler.types.prelude",
    "compiler/option_prelude.vri": "compiler.option.prelude",
    "compiler/result_prelude.vri": "compiler.result.prelude",
    "parser_kit/parser_kit.vri": "parsekit",
    "str/char.vri": "char",
    "collections/concurrent_map.vri": "collections.concurrent",
    "collections/ordered_map.vri": "collections.ordered",
    "embedded/ring_buffer.vri": "embedded.ring",
    "async/task_runtime.vri": "async.tasks",
    "viron/fs_cmd.vri": "viron.fs",
    "viron/net_cmd.vri": "viron.net",
    "viron/pkg_cmd.vri": "viron.pkg",
    "viron/proc_cmd.vri": "viron.proc",

    # Unambiguous core stdlib modules & primitives (straight names)
    "mem/copy.vri": "copy",
    "collections/map.vri": "map",
    "collections/set.vri": "set",
    "io/stdio.vri": "stdio",
    "core/ops.vri": "ops",
    "debug/assert.vri": "assert",
    "str/builder.vri": "builder",
    "mem/slice.vri": "slice",
    "mem/buffer.vri": "buffer",
    "collections/deque.vri": "deque",
    "collections/hashmap.vri": "hashmap",
    "io/traits.vri": "traits",
    "io/format.vri": "format",
    "math/basic.vri": "math",
    "test/test.vri": "test",

    # Lang
    "lang/lang_ko.vri": "lang.ko",
    "lang/lang_zh.vri": "lang.zh",
    "lang/lang_vi.vri": "lang.vi",
    "lang/lang_ja.vri": "lang.ja",

    # WIR lowering
    "wir/lower_h_m.vri": "wir.lower.hm",
    "wir/lower_m_l.vri": "wir.lower.ml",

    # RT
    "rt/string_rt.vri": "rt.string",
    "rt/vec_rt.vri": "rt.vec",

    # ── Rule 1: Functional dot hierarchy in Compiler ─────────────────────────
    # Lowering (User: compiler.lower.mir, compiler.lower.hir)
    "compiler/ast_to_mir.vri": "compiler.lower.mir",
    "compiler/hir_to_mir.vri": "compiler.lower.hir",
    "compiler/ast_to_hir.vri": "compiler.lower.ast",
    "compiler/lir_lower.vri": "compiler.lower.lir",
    "compiler/lir_to_mc.vri": "compiler.lower.mc",

    # MIR subsystem (User: compiler.mir.pipeline, compiler.mir.ssa)
    "compiler/mir_opt_pipeline.vri": "compiler.mir.pipeline",
    "compiler/mir_ssa.vri": "compiler.mir.ssa",
    "compiler/mir_cfg.vri": "compiler.mir.cfg",
    "compiler/mir_opt.vri": "compiler.mir.opt",
    "compiler/mir_opt_advanced.vri": "compiler.mir.advanced",

    # RA & LIR (User: compiler.ra.color, compiler.ra.graph)
    "compiler/lir_regalloc_color.vri": "compiler.ra.color",
    "compiler/lir_interference.vri": "compiler.ra.graph",
    "compiler/lir_regalloc.vri": "compiler.ra.alloc",
    "compiler/lir_liveness.vri": "compiler.ra.liveness",
    "compiler/lir_ra_arena.vri": "compiler.ra.arena",
    "compiler/lir_verifier.vri": "compiler.lir.verifier",
    "compiler/lir_target_desc.vri": "compiler.lir.desc",
    "compiler/lir_codegen.vri": "compiler.lir.codegen",
    "compiler/lir_codegen_x86.vri": "compiler.lir.x86",
    "compiler/lir_codegen_wasm.vri": "compiler.lir.wasm",
    "compiler/lir_codegen_riscv.vri": "compiler.lir.riscv",

    # MC
    "compiler/mc_printer.vri": "compiler.mc.print",
    "compiler/mc_verify.vri": "compiler.mc.verify",

    # Semantics (User: compiler.sem.borrow)
    "compiler/sem_pass1_modules.vri": "compiler.sem.modules",
    "compiler/sem_pass2_symbols.vri": "compiler.sem.symbols",
    "compiler/sem_pass3_names.vri": "compiler.sem.names",
    "compiler/sem_pass4_types.vri": "compiler.sem.types",
    "compiler/sem_pass5_infer.vri": "compiler.sem.infer",
    "compiler/sem_pass6_typecheck.vri": "compiler.sem.typecheck",
    "compiler/sem_pass7_cfa.vri": "compiler.sem.cfa",
    "compiler/sem_pass8_borrow.vri": "compiler.sem.borrow",
    "compiler/sem_pass9_constfold.vri": "compiler.sem.constfold",
    "compiler/sem_pass10_diagnostics.vri": "compiler.sem.diagnostics",

    # Infrastructure & tables (User: compiler.source)
    "compiler/source_manager.vri": "compiler.source",
    "compiler/symbol_table.vri": "compiler.symbols",
    "compiler/type_table.vri": "compiler.typetable",
    "compiler/scope_tree.vri": "compiler.scopes",
    "compiler/ffi_imports.vri": "compiler.ffi",
    "compiler/error_codes.vri": "compiler.errors",
    "compiler/virc_min.vri": "compiler.min",
    "compiler/codegen_x86.vri": "compiler.codegen.x86",
    "compiler/codegen_wasm.vri": "compiler.codegen.wasm",

    # Target & Backends
    "compiler/target_spec.vri": "compiler.target.spec",
    "compiler/target_paging.vri": "compiler.target.paging",
    "compiler/target_triple.vri": "compiler.target.triple",
    "compiler/opt_pass.vri": "compiler.opt.pass",
    "compiler/opt_backend.vri": "compiler.opt.backend",
    "compiler/opt_backend_arm64.vri": "compiler.opt.arm64",
    "compiler/opt_backend_x86.vri": "compiler.opt.x86",
    "compiler/opt_backend_wasm.vri": "compiler.opt.wasm",
    "compiler/opt_backend_riscv.vri": "compiler.opt.riscv",
    "compiler/opt_backend_arc.vri": "compiler.opt.arc",
    "compiler/opt_backend_generic.vri": "compiler.opt.generic",
    "compiler/ir_optimizer.vri": "compiler.opt.ir",

    # Internal compiler definitions (disambiguated from preludes)
    "compiler/types.vri": "compiler.types.def",
    "compiler/option.vri": "compiler.option.def",
    "compiler/result.vri": "compiler.result.def",
    "compiler/alloc.vri": "compiler.alloc.def",
    "compiler/syscall.vri": "compiler.syscall.def",
    "compiler/vec.vri": "compiler.vec.def",
    "compiler/vec_rt.vri": "compiler.vec.rt",
    "compiler/string_rt.vri": "compiler.string.rt",

    # ── Rule 3: Test modules (clean single words, NO _vtest suffix) ─────────
    "test/codegen_vtest.vri": "test.codegen",
    "test/compiler_vtest.vri": "test.compiler",
    "test/type_system_vtest.vri": "test.types",
    "test/bench_e2e_vtest.vri": "test.bench",
    "test/simd_jit_vtest.vri": "test.simd",
    "test/virgex_vtest.vri": "test.virgex",
    "test/vm_opcodes_vtest.vri": "test.vm",
    "test/mem_vtest.vri": "test.mem",
    "test/math_vtest.vri": "test.math",
    "test/bootstrap_vtest.vri": "test.bootstrap",
    "test/cost_model_vtest.vri": "test.cost",
    "test/data_profile_vtest.vri": "test.profile",
    "test/engine_conformance_vtest.vri": "test.engine",
    "test/grad_vtest.vri": "test.grad",
    "test/lowering_vtest.vri": "test.lowering",
    "test/nn_vtest.vri": "test.nn",
    "test/parser_conformance_vtest.vri": "test.parser",
    "test/pgo_tiered_vtest.vri": "test.pgo",
    "test/platform_vtest.vri": "test.platform",
    "test/proptest_fuzz_vtest.vri": "test.fuzz",
    "test/qir_vtest.vri": "test.qir",
    "test/regalloc_vtest.vri": "test.regalloc",
    "test/run_all_vtest.vri": "test.all",
    "test/syscall_conformance_vtest.vri": "test.syscall",
    "test/tokenizer_vtest.vri": "test.tokenizer",
    "test/tools_vtest.vri": "test.tools",
    "test/vss_vtest.vri": "test.vss",
    "test/wir_vtest.vri": "test.wir",
    "test/fuzz.vri": "test.fuzzing",
    "test/vtest.vri": "test.runner",
}

# Standalone directory candidate names (straight name)
STANDALONE_DIRS = {
    "virgex", "regex", "archive", "ast", "async", "bench", "build",
    "config", "crypto", "doc", "doctest", "encode", "error", "ffi",
    "fmt", "glob", "gpu", "gui", "http", "image", "lsp", "net",
    "path", "pattern", "pkg", "process", "profile", "rand", "reflect",
    "semver", "serde", "sort", "sql", "time", "token", "uuid",
    "viron", "wasm", "thread", "tls", "datetime", "locale"
}

SPECIAL_STANDALONE = [
    ("crypto", "crypto/crypto.vri"),
    ("auth", "auth/oauth2.vri"),
    ("func", "func/functools.vri"),
    ("schedule", "schedule/cron.vri"),
]

def generate_registry():
    all_files = sorted([p.relative_to(STDLIB_DIR).as_posix() for p in STDLIB_DIR.rglob("*.vri")])
    reg = OrderedDict()
    mapped_files = set()

    # 1. Preludes (Spec Section III.3)
    for k, v in PRELUDES:
        reg[k] = v
        mapped_files.add(v)

    # 2. Explicit Overrides (take precedence over automatic scans)
    for rel, name in OVERRIDES.items():
        if rel not in mapped_files:
            assert name not in reg, f"Duplicate registry key in overrides: {name}"
            reg[name] = rel
            mapped_files.add(rel)

    # 3. Standalone top-level files
    for rel in all_files:
        p = Path(rel)
        if len(p.parts) == 1 and rel not in mapped_files and p.stem not in reg:
            reg[p.stem] = rel
            mapped_files.add(rel)

    # 4. Standalone directory modules (any dir/dir.vri package)
    for rel in all_files:
        p = Path(rel)
        if len(p.parts) == 2 and p.parts[0] == p.stem:
            if rel not in mapped_files and p.parts[0] not in reg:
                reg[p.parts[0]] = rel
                mapped_files.add(rel)

    for k, v in SPECIAL_STANDALONE:
        if v not in mapped_files and (STDLIB_DIR / v).exists():
            if k not in reg:
                reg[k] = v
                mapped_files.add(v)

    # 5. Canonical dot-style mapping for all remaining files
    for rel in all_files:
        if rel not in mapped_files:
            p = Path(rel)
            parts = list(p.parts)
            parts[-1] = p.stem
            dot_name = ".".join(parts)
            reg[dot_name] = rel
            mapped_files.add(rel)

    # Format the registry file
    lines = [
        "# ==============================================================================",
        "# Vir v2.0 Standard Library Module Registry",
        "# ==============================================================================",
        "# Source of truth for standard library module mappings: module_name = file_path",
        "# Conventions:",
        "#   - Standalone / distinct directory packages use straight names (e.g. virgex, regex, json)",
        "#   - Canonical preludes use standard names (types, option, result, alloc, etc.)",
        "#   - Subsystems and internal modules use functional dot hierarchy (e.g. compiler.codegen, vss.parser, wir.builder)",
        "#   - Test modules use clean names without '_vtest' suffix (e.g. test.codegen, test.compiler, test.types)",
        "# Root is 'vir', all module paths are resolved relative to stdlib/vir/",
        "# ==============================================================================",
        "",
        "root = vir",
        "",
    ]

    placed = set()

    def emit_section(title, predicate):
        section_lines = []
        for k, v in reg.items():
            if k not in placed and predicate(k, v):
                section_lines.append(f"{k} = {v}")
                placed.add(k)
        if section_lines:
            lines.append(f"# ── {title} " + "─" * max(1, 74 - len(title) - 5))
            lines.extend(section_lines)
            lines.append("")

    # Section 1: Core & Runtime Preludes
    prelude_keys = {k for k, _ in PRELUDES}
    emit_section("Core & Runtime Preludes", lambda k, v: k in prelude_keys)

    # Section 2: Distinct Standalone Packages & Top-Level Modules
    emit_section("Standalone & Top-Level Modules", lambda k, v: "." not in k)

    # Section 3: Compiler Subsystem
    emit_section("Compiler Subsystem", lambda k, v: k.startswith("compiler.") or v.startswith("compiler/"))

    # Section 4: VSS Subsystem
    emit_section("VSS Subsystem", lambda k, v: k.startswith("vss.") or v.startswith("vss/"))

    # Section 5: WIR Subsystem
    emit_section("WIR Subsystem", lambda k, v: k.startswith("wir.") or v.startswith("wir/"))

    # Section 6: Pattern & Regex Subsystems
    emit_section("Pattern & Regex Subsystems", lambda k, v: k.startswith("pattern.") or v.startswith("pattern/") or v.startswith("regex/"))

    # Section 7: Test Subsystem
    emit_section("Test Subsystem", lambda k, v: k.startswith("test.") or v.startswith("test/"))

    # Section 8: Code Generation Subsystem
    emit_section("Code Generation Subsystem", lambda k, v: k.startswith("codegen.") or v.startswith("codegen/"))

    # Section 9: Collections Subsystem
    emit_section("Collections Subsystem", lambda k, v: k.startswith("collections.") or v.startswith("collections/"))

    # Section 10: AI & Machine Learning Subsystem
    emit_section("AI & Machine Learning Subsystem", lambda k, v: k.startswith("ai.") or v.startswith("ai/"))

    # Section 11: Cryptography Subsystem
    emit_section("Cryptography Subsystem", lambda k, v: k.startswith("crypto.") or v.startswith("crypto/"))

    # Section 12: Math Subsystem
    emit_section("Math Subsystem", lambda k, v: k.startswith("math.") or v.startswith("math/"))

    # Section 13: Network & Web Subsystems
    emit_section("Network & Web Subsystems", lambda k, v: k.startswith("net.") or k.startswith("web.") or v.startswith("net/") or v.startswith("web/"))

    # Section 14: Hardware & Embedded Subsystems
    emit_section("Hardware & Embedded Subsystems", lambda k, v: k.startswith("hw.") or k.startswith("embedded.") or v.startswith("hw/") or v.startswith("embedded/"))

    # Section 15: Runtime Internals
    emit_section("Runtime Internals", lambda k, v: k.startswith("rt.") or v.startswith("rt/"))

    # Section 16: General Standard Library Modules
    emit_section("General Standard Library Modules", lambda k, v: True)

    content = "\n".join(lines)
    OUTPUT_REGISTRY.write_text(content)
    print(f"Generated {len(reg)} registry entries in {OUTPUT_REGISTRY}")
    print(f"All {len(all_files)} stdlib files mapped successfully.")

if __name__ == "__main__":
    generate_registry()
