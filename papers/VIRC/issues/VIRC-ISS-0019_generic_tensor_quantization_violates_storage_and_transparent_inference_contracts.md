---
id: "VIRC-ISS-0019"
type: "ISSUE"
domain: "VIRC"
title: "Generic tensor quantization violates storage and transparent inference contracts"
status: "TRIAGED"
severity: "S1"
priority: "P0"
created: "2026-10-03"
updated: "2026-10-03"
owners:
  - "compiler"
  - "runtime"
components:
  - "tensor"
  - "quantization"
  - "infer"
  - "mir"
  - "runtime-stubs"
  - "arm64"
  - "x86-64"
  - "tests"
related:
  issues:
    - "VIRC-ISS-0005"
  plans: []
  reports: []
supersedes: null
superseded_by: null
tags:
  - "tensor"
  - "quantize"
  - "int4"
  - "int8"
  - "f16"
  - "f32"
  - "dequantize"
  - "correctness"
---

# VIRC-ISS-0019 — Generic tensor quantization violates storage and transparent inference contracts

## 1. Summary

Generic `quantize(tensor, bits: N)` accepts the normative bit widths but its
runtime format and inference behavior do not satisfy the language contract.
Transparent inference with 8-bit and odd-sized 4-bit values currently produces
zero results, while the 16-bit and 32-bit paths store scaled integers rather
than the specified f16 and f32 representations.

## 2. Context

VIR-SPC-0018 section 26.5 defines storage as f32, f16, i8, or INT4 for bit
widths 32, 16, 8, and 4 and requires compiler-inserted transparent dequantize at
the matching `infer` site. This generic contract is distinct from the explicit
40-byte Q8_0 stdlib codec and from the missing first-class packed metadata
tracked by existing Q8 issues.

## 3. Expected Behavior

- Only floating dense tensors with compile-time bits in `{4, 8, 16, 32}` are
  accepted.
- Each bit width uses the storage representation defined by the active SPEC,
  with documented scale/zero-point policy and deterministic rounding.
- Odd INT4 lengths allocate and initialize the final half byte safely.
- Tensor operations inside `infer:` transparently dequantize or dispatch a
  compatible quantized kernel and produce numerically valid results.
- Quantized values retain enough logical shape and dtype information to reject
  incompatible operations before artifact emission.

## 4. Actual Behavior

- Semantic input and bit-width validation works for the focused negative cases.
- ARM64 and x86 runtime stubs choose integer Qmax values for all four modes;
  the 16-bit and 32-bit paths allocate two or four bytes per element but pack
  scaled integers, not IEEE f16/f32 values.
- `tests/strict_v2/test_quantize_e2e.vri` passes only direct raw-layout checks
  for 8-bit and 4-bit packing.
- Contract case AI-001 expects transparent 8-bit inference results `3` and `7`
  but receives zeros.
- Contract case AI-003 expects odd-INT4 results `6` and `15` but receives zeros.

## 5. Reproduction

```sh
python3 tools/gap_contract_runner.py \
  --virc ./bin/virc --filter '^(AI-001|AI-003|AI-004|AI-005)$' --verbose

./bin/virc tests/strict_v2/test_quantize_e2e.vri \
  -O1 -q -o /tmp/vir_quantize_layout
/tmp/vir_quantize_layout

nl -ba compiler/src/lower/lir_codegen/rt_stubs_math/quantize_backward.vri | \
  sed -n '16,265p'
nl -ba compiler/src/lower/lir_codegen_x86/rt_stubs_math/backward_quantize.vri | \
  sed -n '183,420p'
```

## 6. Evidence

- CONFIRMED: VIR-SPC-0018:3693-3707 defines f32/f16/i8/INT4 storage and
  transparent dequantization during inference.
- CONFIRMED: invalid literal bits and non-tensor/integer tensor inputs are
  rejected with `E3019` and `E3018`.
- CONFIRMED: the current runtime selects Qmax 32767 and 2147483647 for 16/32
  and writes integer-packed payloads.
- CONFIRMED: direct 8-bit/4-bit raw packing fixture passes on macOS ARM64.
- CONFIRMED: AI-001 and AI-003 compile and run but return zero numeric results
  instead of their registered oracles.
- NOT_VERIFIED: rounding, saturation, NaN/Inf, negative zero, f16 encoding,
  multi-target parity, and acceptable inference error bounds.

## 7. Scope

### Affected

- generic language-level `quantize` for bits 4/8/16/32;
- runtime storage layout, rounding, saturation, odd-size packing, and bounds;
- transparent inference dequantization or compatible kernel dispatch;
- deterministic shape/dtype propagation required for correct operation.

### Not affected / Unknown

- explicit Q8_0 40-byte codec, borrowed views, and Gemma integration;
- the separate architectural issue for persistent packed codec/shape/storage
  metadata and automatic Q8_0 dispatch;
- dense tensor scalar/SIMD correctness outside quantized operation boundaries;
- new public quantization syntax or additional codecs.

## 8. Impact

Programs accepted under the published quantization contract can silently
produce incorrect inference results, and 16/32-bit values do not have the
advertised physical representation. This is a core numerical correctness and
memory-layout defect, classified S1/P0.

## 9. Preliminary Analysis

- CONFIRMED: frontend validation is present but runtime representation and
  transparent inference are incomplete.
- CONFIRMED: generic 8-bit quantization and Q8_0 are different physical formats
  and must not be reinterpreted as each other.
- HYPOTHESIS: missing logical metadata and a missing dequantize/dispatch step
  both contribute to the zero inference results.
- NOT_VERIFIED: the correct public rounding and scaling policy where the SPEC
  does not define exact numerical details.

## 10. Acceptance Criteria

- [ ] An approved contract defines exact storage, scale/zero-point, rounding,
  saturation, NaN/Inf, and odd-length behavior for every supported bit width.
- [ ] Bits 32 and 16 use valid f32 and f16 storage as specified, or a separately
  authorized SPEC revision changes that contract before implementation.
- [ ] Bits 8 and 4 pass independent byte-level codec tests including negative,
  boundary, saturation, odd-length, and malformed-input cases.
- [ ] `infer:` produces correct transparent results for each bit width and
  compatible operation against an independent float oracle.
- [ ] Quantized dtype, shape, codec, and storage metadata survive semantic,
  MIR, LIR, optimization, and target lowering without format confusion.
- [ ] Generic 8-bit values cannot be implicitly interpreted as Q8_0 blocks.
- [ ] O0-O3 and affected target parity, module/bundle sync, and fixed-point
  self-host checks pass with a newly built compiler.
- [ ] A VPS PLAN and REPORT link this ISSUE before closure.

## 11. Related Papers

### Issues

- VIRC-ISS-0005 — first-class quantized format, shape, storage metadata, and
  typed dispatch architecture.

### Plans

- None yet.

### Reports

- None yet.

## 12. Revision History

| Date | Change |
|---|---|
| 2026-10-03 | Created and triaged from generic quantize runtime and AI contract audit |
| 2026-10-03 | Linked VIRC-ISS-0005 |
