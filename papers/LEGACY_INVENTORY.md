# VPS v1 legacy-document inventory

**Audit date:** 2026-10-02

**Disposition:** legacy source documents were reorganized under `docs/_legacy/`
on 2026-10-02; no source document was deleted or assigned a production paper
ID. Architecture, algorithm, and specification documents remain in the active
`docs/` tree.

## Mapping policy

Legacy filenames are not reliable evidence of VPS class. Migration MUST inspect
the content and provenance of each document before allocating an ID.

| Legacy content | Recommended VPS treatment |
|---|---|
| Defect, gap, limitation, or unresolved audit finding | Create an ISSUE; preserve the legacy path as evidence |
| Proposed implementation, architecture, or strict prompt | Create a PLAN only after linking one or more verified source ISSUEs |
| Completed implementation and verification evidence | Create a REPORT linked to the governing ISSUE and PLAN |
| Release notes, general status, roadmap, or user documentation | Preserve under `docs/_legacy/`; link from a paper when it is evidence |
| Mixed plan and result | Split future governance into PLAN and REPORT; keep the original intact for provenance |

Migration MUST NOT infer completion from a `done/` directory or from words such
as `FINAL`, `COMPLETION`, or `REPORT` in a filename. Claims must be re-verified
against active code and tests. The new paper SHOULD cite the original path and
commit. Once registered, its ID is permanent.

The reorganization retained these contract/specification artifacts in the
active documentation tree:

- `docs/REGISTER_ALLOCATION_STRICT_SPEC.md` → migrated to `VIRC-SPC-0003`
- `docs/STRICT_V2_GAP_TEST_CONTRACT.md` → migrated to `VIRC-SPC-0005`
- `docs/spec_gap_contract_baseline.tsv`

## `docs/_legacy/plan/` candidates (42)

- `docs/_legacy/plan/ARENA_SIMD_MULTI_TARGET_BENCHMARK_REPORT.md`
- `docs/_legacy/plan/EXPERIMENTAL_O4_REGIONAL_REGISTER_ALLOCATION_PLAN.md`
- `docs/_legacy/plan/PRODUCTION_SECURITY_ARCHITECTURE_PLAN.md`
- `docs/_legacy/plan/STDLIB_ENV_DATA_FORMATS_PLAN.md`
- `docs/_legacy/plan/STRICT_AGGREGATE_COLLECTION_TYPE_COMPATIBILITY_PROMPT_PART_3.md`
- `docs/_legacy/plan/STRICT_BIND_FFI_BACKEND_END_TO_END_PROMPT.md`
- `docs/_legacy/plan/STRICT_MULTI_TARGET_RUNTIME_BACKEND_RESTRUCTURE_PROMPT.md`
- `docs/_legacy/plan/STRICT_PRE_LOOP_TRANSFORMS_AND_GEORGE_APPEL_IRC_PROMPT.md`
- `docs/_legacy/plan/STRICT_TYPED_REFERENCE_AUTO_DEREF_PROMPT_PART_2.md`
- `docs/_legacy/plan/STRICT_TYPE_SAFETY_ENTITY_POINTER_HARDENING_PROMPT.md`
- `docs/_legacy/plan/STRICT_TYPE_SYSTEM_SOUNDNESS_TERMINATION_AND_COMPLEXITY_PROMPT.md`
- `docs/_legacy/plan/STRICT_V2_FULL_COMPILER_END_TO_END_PROMPT.md`
- `docs/_legacy/plan/STRICT_V2_GAP_FEATURES_IMPLEMENTATION_PROMPT.md`
- `docs/_legacy/plan/STRICT_V2_GEMMA_VIR_Q8_0_TENSOR_MATMUL_PROMPT.md`
- `docs/_legacy/plan/STRICT_VIRON_RUNTIME_DUAL_JIT_HOTPATCH_COMPLETION_PROMPT.md`
- `docs/_legacy/plan/STRICT_VIR_OF_GENERIC_SYNTAX_MIGRATION_PROMPT.md`
- `docs/_legacy/plan/VIRC_ICHING_DIAGNOSTIC_ORIGIN_AND_SILENT_FAILURE_ISSUE_PROMPT.md`
- `docs/_legacy/plan/VIRON_V2_ARCHITECTURE_SPEC.md`
- `docs/_legacy/plan/VIR_GPU_COMPILER_IMPLEMENTATION_PLAN.md`
- `docs/_legacy/plan/VSCODE_VIR_LSP_SYNTAX_SEMANTIC_INTEGRATION_PROMPT.md`
- `docs/_legacy/plan/compiler_hardening_plan.md`
- `docs/_legacy/plan/done/COMPILER_VOID_VALUE_LOWERING_HANDOFF.md`
- `docs/_legacy/plan/done/REGISTER_ALLOCATION_OPTIMIZATION_AND_BLOCK_ARENA_PLAN.md`
- `docs/_legacy/plan/done/SOURCE_ORIGIN_DIAGNOSTICS_END_TO_END_PROMPT.md`
- `docs/_legacy/plan/done/STDLIB_REGISTRY_FLAT_INCLUDE_SELF_HOST_PROMPT.md`
- `docs/_legacy/plan/done/STRICT_BORROW_CHECKER_LOOP_FIXED_POINT_PROMPT.md`
- `docs/_legacy/plan/done/STRICT_FFI_EXTERN_IMPORT_END_TO_END_PROMPT.md`
- `docs/_legacy/plan/done/STRICT_V2_ARENA_SIMD_MULTI_TARGET_IMPLEMENTATION_PROMPT.md`
- `docs/_legacy/plan/done/STRICT_V2_CASE_PATTERN_MATCHING_END_TO_END_PROMPT.md`
- `docs/_legacy/plan/done/STRICT_V2_GROUPED_VAR_LET_DECLARATIONS_IMPLEMENTATION_PROMPT.md`
- `docs/_legacy/plan/done/STRICT_V2_IN_REF_OUT_MULTI_TARGET_BACKEND_PROMPT.md`
- `docs/_legacy/plan/done/STRICT_V2_MEMORY_COMPLETION_O1_HEAP_IMPLEMENTATION_PROMPT.md`
- `docs/_legacy/plan/done/STRICT_V2_MEMORY_OWNERSHIP_ARENA_IMPLEMENTATION_PROMPT.md`
- `docs/_legacy/plan/done/STRICT_V2_PACKED_ENTITY_VIRC_2_8_2_PROMPT.md`
- `docs/_legacy/plan/done/STRICT_V2_PERCENT_OPERATOR_MODULO_CLEANUP_PROMPT.md`
- `docs/_legacy/plan/done/STRICT_V2_STRING_INTERPOLATION_AND_LITERAL_VALUES_PROMPT.md`
- `docs/_legacy/plan/done/STRICT_V2_TENSOR_MULTI_INDEX_MATMUL_PROMPT.md`
- `docs/_legacy/plan/done/STRICT_V2_UFCS_RESOLUTION_END_TO_END_PROMPT.md`
- `docs/_legacy/plan/done/STRICT_V2_UFCS_UNRESOLVED_RECEIVER_NULL_CALL_PROMPT.md`
- `docs/_legacy/plan/done/STRICT_VIRC_CLI_LOGGING_DIAGNOSTIC_STORAGE_PROMPT.md`
- `docs/_legacy/plan/done/V2_7_0_RELEASE_HARDENING_PLAN.md`
- `docs/_legacy/plan/done/VIR_LSP_COMPILER_HANDOFF_2026-10-01.md`

## `docs/_legacy/report/` candidates (17)

- `docs/_legacy/report/COMPILER_BUGS_AND_LIMITATIONS.md`
- `docs/_legacy/report/FFI_EXTERN_IMPORT_REPORT.md`
- `docs/_legacy/report/PHASE_1_TO_10_COMPLETION_REPORT.md`
- `docs/_legacy/report/README.md`
- `docs/_legacy/report/SOURCE_ORIGIN_DIAGNOSTICS_STATUS_2026_09_23.md`
- `docs/_legacy/report/STRICT_V2_FULL_COMPILER_HANDOVER_2026_09_08.md`
- `docs/_legacy/report/STRICT_V2_MEMORY_ARENA_AUDIT_2026_09_21.md`
- `docs/_legacy/report/STRING_INTERPOLATION_E2E_REPORT.md`
- `docs/_legacy/report/V2_7_0_RELEASE_HARDENING_REPORT.md`
- `docs/_legacy/report/V2_8_0_RELEASE_REPORT.md`
- `docs/_legacy/report/V2_8_5_RELEASE_REPORT.md`
- `docs/_legacy/report/V2_8_5_RELEASE_REPORT_EN.md`
- `docs/_legacy/report/V2_9_0_RELEASE_NOTES.md`
- `docs/_legacy/report/V3_2_0_RELEASE_NOTES.md`
- `docs/_legacy/report/V3_8_1_RELEASE_NOTES.md`
- `docs/_legacy/report/VIRC_CLI_COMPLETION_EVIDENCE_2026_09_30.md`
- `docs/_legacy/report/checklist/UNFINISHED_AND_NOOP_FEATURES_CHECKLIST.md`

## Other root-level `docs/_legacy/` candidates (28)

- `docs/_legacy/BENCHMARKS.md`
- `docs/_legacy/BENCHMARK_REPORT.md`
- `docs/_legacy/BENCHMARK_REPORT_v2.md`
- `docs/_legacy/BENCHMARK_REPORT_v3.md`
- `docs/_legacy/CODEBASE_AUDIT_2026_03_10.md`
- `docs/_legacy/COMPILER_BUGS_AND_LIMITATIONS.md`
- `docs/_legacy/COMPILER_BUG_CHECKLIST.md`
- `docs/_legacy/COMPILER_STATUS.md`
- `docs/_legacy/COMPLETION_STATUS.md`
- `docs/_legacy/CRYPTO_SECURITY_AUDIT_REPORT.md`
- `docs/_legacy/FINAL_HONEST_REPORT.md`
- `docs/_legacy/PHASE2_IR_LOWERING_REPORT.md`
- `docs/_legacy/PHASE2_ROADMAP_DETAILED.md`
- `docs/_legacy/PHASE3_ROADMAP_DETAILED.md`
- `docs/_legacy/PROGRESS_REPORT_2026_06_20.md`
- `docs/_legacy/PROGRESS_REPORT_2026_06_21.md`
- `docs/_legacy/RELEASE_PROCESS.md`
- `docs/_legacy/RELEASE_v3.4.0.md`
- `docs/_legacy/RELEASE_v3.5.0.md`
- `docs/_legacy/RELEASE_v3.8.0.md`
- `docs/_legacy/REPORT_2026_08_26_GEMINI.md`
- `docs/_legacy/SELF_HOST_AND_STDLIB_COMPLETION_REPORT_2026.md`
- `docs/_legacy/STATUS_REPORT_2026_03_15.md`
- `docs/_legacy/STDLIB_ROADMAP.md`
- `docs/_legacy/TENSOR_ML_OPERATORS_REPORT_2026.md`
- `docs/_legacy/VIR_V2.0_SELF_HOSTING_AUDIT.md`
- `docs/_legacy/WIR_VSS_ARCHITECTURE_PLAN.md`
- `docs/_legacy/virgori_library_design_plan.md`

## Recommended first migration pass

1. Audit unresolved limitation and checklist documents first; create ISSUEs only
   for findings still reproducible on the active tree.
2. Audit implementation prompts next; link each valid PLAN to those ISSUEs and
   record obsolete proposals as rejected or superseded rather than executing
   them blindly.
3. Convert completion reports only where current diffs and tests provide
   evidence. Otherwise retain them as legacy evidence or create a follow-up
   ISSUE for the verification gap.
4. Preserve release notes, broad roadmaps, and general documentation in
   `docs/_legacy/`; do not treat them as current architecture or specification.
