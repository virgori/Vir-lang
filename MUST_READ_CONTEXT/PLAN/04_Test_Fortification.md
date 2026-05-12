# VIR Test Fortification Plan — Stage 4 Quality Assurance

> **Mục đích:** Kế hoạch kiểm thử toàn diện để đảm bảo Vir engine mới tương đương với C engine
> **Ngày tạo:** 22/03/2026
> **Phiên bản:** 2.0 — Stage 4 Preparation (Corrected 02/04/2026)

> ⚠️ **AUDIT CORRECTION (02/04/2026):** Phiên bản gốc dùng tên file sai (`vtest_*.vri`) — thực tế naming convention là `*_vtest.vri`. Bảng test suites bên dưới đã được cập nhật với tên file thực và số lượng test functions chính xác.

---

## Mục lục

1. [Current Test Inventory](#1-current-test-inventory)
2. [Binary Consistency Testing](#2-binary-consistency-testing)
3. [Memory Leak Detection](#3-memory-leak-detection)
4. [Regression Testing Strategy](#4-regression-testing-strategy)
5. [Performance Benchmarks](#5-performance-benchmarks)
6. [Platform Coverage](#6-platform-coverage)
7. [Chaos Testing](#7-chaos-testing)
8. [CI/CD Integration](#8-cicd-integration)

---

## 1. Current Test Inventory

### Test Framework: vtest

**Location:** `stdlib/vir/test/`

> **⚠️ Ghi chú naming:** File convention thực tế là `*_vtest.vri` (vd: `math_vtest.vri`), KHÔNG phải `vtest_*.vri` như bản gốc.

| Suite | File (thực tế) | Funcs | Coverage Area |
|-------|------|-------|---------------|
| VM Opcodes | `vm_opcodes_vtest.vri` | 107 | Q-IR opcode coverage |
| Parser | `parser_conformance_vtest.vri` | 89 | Syntax coverage |
| Syscall | `syscall_conformance_vtest.vri` | 31 | OS wrappers |
| Type System | `type_system_vtest.vri` | 30 | Type checking |
| PGO/Tiered | `pgo_tiered_vtest.vri` | 27 | Profile-guided opt |
| Math | `math_vtest.vri` | 25 | Math functions |
| Tokenizer | `tokenizer_vtest.vri` | 25 | Lexer/tokenizer |
| Tools | `tools_vtest.vri` | 22 | Tool utilities |
| NN | `nn_vtest.vri` | 21 | Neural network |
| SIMD/JIT | `simd_jit_vtest.vri` | 20 | SIMD + JIT ops |
| Q-IR | `qir_vtest.vri` | 20 | IR operations |
| Platform | `platform_vtest.vri` | 17 | Platform-specific |
| RegAlloc | `regalloc_vtest.vri` | 17 | Register allocation |
| WIR | `wir_vtest.vri` | 17 | WASM IR |
| Proptest/Fuzz | `proptest_fuzz_vtest.vri` | 16 | Property-based/fuzz |
| Lowering | `lowering_vtest.vri` | 14 | IR lowering |
| Mem | `mem_vtest.vri` | 13 | Memory management |
| Cost Model | `cost_model_vtest.vri` | 12 | Optimization costs |
| VSS | `vss_vtest.vri` | 12 | Vir string system |
| Bootstrap | `bootstrap_vtest.vri` | 10 | Bootstrap pipeline |
| Codegen | `codegen_vtest.vri` | 10 | Code generation |
| Bench E2E | `bench_e2e_vtest.vri` | 9 | End-to-end bench |
| Virgex | `virgex_vtest.vri` | 8 | Regex engine |
| Compiler | `compiler_vtest.vri` | — | Compiler tests |
| Engine Conf. | `engine_conformance_vtest.vri` | — | Core behavior |
| **TOTAL** | **28 files** | **~796** | |

### Ngoài vtest: virc End-to-End Tests

**Location:** `Vir/test_*.vri`  
**Runner:** `bash run_tests.sh`

| Status (02/04/2026) | Count |
|---|---|
| **PASS** | 46 |
| WIP/debug stubs | ~14 |
| **Total files** | ~60 |

### Test Runner

```bash
# Run all tests
./vir stdlib/vir/test/run_all_vtest.vri

# Run specific suite
./vir stdlib/vir/test/engine_conformance_vtest.vri
```

---

## 2. Binary Consistency Testing

### Goal

Ensure Vir-engine output is **bit-for-bit identical** to C-engine output.

### Strategy: Dual-Engine Harness

```ascii
┌─────────────────┐     ┌────────────────┐
│   Test Input    │────▶│    C Engine    │──▶ Output A
│   (.vri file)   │     └────────────────┘
│                 │     ┌────────────────┐
│                 │────▶│   Vir Engine   │──▶ Output B
└─────────────────┘     └────────────────┘
                               │
                               ▼
                        ┌────────────────┐
                        │  Compare A == B │
                        └────────────────┘
```

### Implementation: `binary_diff_test.vri`

```vir
// stdlib/vir/test/tools/binary_diff_test.vri

import "std/process" as proc
import "std/fs" as fs
import "std/cmp" as cmp

fn run_binary_diff(test_file: String) -> Bool {
    // Run with C engine
    let c_output = proc.exec("./vir_c_engine", [test_file])
    
    // Run with Vir engine  
    let vir_output = proc.exec("./vir", [test_file])
    
    // Compare stdout
    if c_output.stdout != vir_output.stdout {
        print("STDOUT MISMATCH:")
        print("  C:   " + c_output.stdout)
        print("  Vir: " + vir_output.stdout)
        return false
    }
    
    // Compare stderr
    if c_output.stderr != vir_output.stderr {
        print("STDERR MISMATCH")
        return false
    }
    
    // Compare exit code
    if c_output.exit_code != vir_output.exit_code {
        print("EXIT CODE MISMATCH: C=" + str(c_output.exit_code) + " Vir=" + str(vir_output.exit_code))
        return false
    }
    
    return true
}

fn run_all_binary_tests() {
    let test_files = fs.glob("tests/**/*.vri")
    let passed = 0
    let failed = 0
    
    for file in test_files {
        if run_binary_diff(file) {
            passed = passed + 1
        } else {
            failed = failed + 1
            print("FAILED: " + file)
        }
    }
    
    print("Binary Consistency: " + str(passed) + "/" + str(passed + failed))
}
```

### Critical Test Cases for Binary Consistency

| Category | Test | Why Critical |
|----------|------|--------------|
| Float precision | `1.1 + 2.2` | IEEE 754 rounding |
| Integer overflow | `9223372036854775807 + 1` | Wrap behavior |
| String encoding | `"日本語"` | UTF-8 handling |
| Division | `17 / 5`, `-17 / 5` | Truncation direction |
| Modulo | `-17 % 5` | Sign behavior |
| NaN handling | `0.0 / 0.0` | NaN propagation |
| Infinity | `1e308 * 10` | Inf handling |

---

## 3. Memory Leak Detection

### Strategy 1: Reference Count Verification

```vir
// stdlib/vir/test/tools/rc_leak_detector.vri

fn test_no_leaks() {
    let before = sys.heap_allocated()
    
    // Run test code
    test_body()
    
    // Force GC
    sys.gc_collect()
    
    let after = sys.heap_allocated()
    
    assert_eq(before, after, "Memory leak detected: " + str(after - before) + " bytes")
}
```

### Strategy 2: Object Tracking

```vir
entity LeakTracker {
    active_objects: Map[Int, String]  // ptr -> allocation site
    
    fn on_alloc(ptr: Int, site: String) {
        self.active_objects.set(ptr, site)
    }
    
    fn on_free(ptr: Int) {
        self.active_objects.delete(ptr)
    }
    
    fn report_leaks() {
        if self.active_objects.len() > 0 {
            print("LEAKED OBJECTS:")
            for (ptr, site) in self.active_objects {
                print("  " + str(ptr) + " allocated at " + site)
            }
        }
    }
}
```

### Strategy 3: Stress Test Patterns

```vir
// Memory stress tests

fn test_array_growth_shrink() {
    for _ in 0..1000 {
        let arr = []
        for i in 0..10000 {
            arr.push(i)
        }
        // arr goes out of scope - should be freed
    }
    // Check no accumulation
}

fn test_string_concat_heavy() {
    for _ in 0..1000 {
        let s = ""
        for i in 0..100 {
            s = s + str(i)
        }
        // s goes out of scope
    }
}

fn test_entity_cycles() {
    // Test circular reference handling
    entity Node { next: Node? }
    
    let a = Node { next: null }
    let b = Node { next: a }
    a.next = b  // Circular!
    
    // Should not leak when both go out of scope
}
```

### Memory Test Suite: `memory_stress_vtest.vri`

| Test | Purpose |
|------|---------|
| `test_large_array_allocation` | Allocate 1M element array, verify cleanup |
| `test_string_interning` | Many identical strings, verify dedup |
| `test_rapid_alloc_free` | 100K alloc/free cycles |
| `test_deep_recursion` | Stack usage under deep calls |
| `test_entity_field_update` | Repeated field updates don't leak |
| `test_map_churn` | Insert/delete cycles |
| `test_closure_capture` | Closures don't hold refs too long |

---

## 4. Regression Testing Strategy

### Test Categories

```
tests/
├── unit/           # Single-feature tests
├── integration/    # Multi-component tests
├── regression/     # Bug-specific tests (with issue #)
├── fuzzing/        # Random input tests
└── snapshot/       # Output comparison tests
```

### Regression Test Naming Convention

```
tests/regression/issue_0042_null_deref.vri
tests/regression/issue_0087_float_precision.vri
tests/regression/issue_0123_unicode_slice.vri
```

### Snapshot Testing

```vir
// stdlib/vir/test/tools/snapshot.vri

fn snapshot_test(name: String, fn_to_test: fn() -> String) {
    let expected_file = "tests/snapshots/" + name + ".expected"
    let actual = fn_to_test()
    
    if fs.exists(expected_file) {
        let expected = fs.read(expected_file)
        assert_eq(actual, expected, "Snapshot mismatch for " + name)
    } else {
        // First run - create snapshot
        fs.write(expected_file, actual)
        print("Created snapshot: " + expected_file)
    }
}
```

### Regression Test Protocol

1. **Bug reported** → Create minimal reproducer
2. **Test created** → `tests/regression/issue_XXXX_description.vri`
3. **Bug fixed** → Test must pass
4. **Test permanent** → Never remove regression tests

---

## 5. Performance Benchmarks

### Benchmark Suite: `benchmarks/`

| Benchmark | What it measures |
|-----------|------------------|
| `fib_recursive.vri` | Function call overhead |
| `fib_iterative.vri` | Loop overhead |
| `array_sum.vri` | Array iteration |
| `string_concat.vri` | String allocation |
| `entity_create.vri` | Object allocation |
| `map_lookup.vri` | Hash table performance |
| `simd_dot_product.vri` | SIMD throughput |
| `syscall_overhead.vri` | System call latency |

### Performance Regression Detection

```vir
// benchmarks/runner.vri

const TOLERANCE = 0.10  // 10% regression threshold

fn run_benchmark(name: String, iterations: Int, fn_body: fn()) -> Float {
    let start = sys.time_ns()
    for _ in 0..iterations {
        fn_body()
    }
    let end = sys.time_ns()
    return (end - start) / iterations
}

fn check_regression(name: String, current_ns: Float) -> Bool {
    let baseline_file = "benchmarks/baselines/" + name + ".baseline"
    if fs.exists(baseline_file) {
        let baseline = parse_float(fs.read(baseline_file))
        let slowdown = (current_ns - baseline) / baseline
        
        if slowdown > TOLERANCE {
            print("⚠️ REGRESSION: " + name + " is " + str(slowdown * 100) + "% slower")
            return false
        }
    }
    return true
}
```

### Baseline Management

```bash
# Record new baselines (after major release)
./vir benchmarks/runner.vri --record-baseline

# Check against baselines
./vir benchmarks/runner.vri --check
```

---

## 6. Platform Coverage

### Target Platforms

| Platform | Architecture | Status | CI |
|----------|--------------|--------|-----|
| Linux | x86_64 | Primary | ✅ |
| Linux | ARM64 | Primary | ✅ |
| macOS | ARM64 (M1+) | Primary | ✅ |
| macOS | x86_64 | Secondary | ✅ |
| FreeBSD | x86_64 | Tertiary | ⏳ |
| Windows | x86_64 | Future | ❌ |

### Platform-Specific Tests

```vir
// tests/platform/macos_arm64.vri

@platform("macos", "arm64")
fn test_macos_specific() {
    // Test macOS-specific syscalls
    let info = sys.sysctl("hw.ncpu")
    assert(info > 0)
}

// tests/platform/linux_x86_64.vri

@platform("linux", "x86_64")
fn test_linux_specific() {
    // Test Linux-specific features
    let cpuinfo = fs.read("/proc/cpuinfo")
    assert(cpuinfo.contains("processor"))
}
```

### Cross-Platform Matrix

| Test Category | Linux | macOS | FreeBSD |
|---------------|-------|-------|---------|
| File I/O | ✅ | ✅ | ✅ |
| Network | ✅ | ✅ | ✅ |
| Threading | ✅ | ✅ | ⏳ |
| SIMD | ✅ | ✅ | ✅ |
| Syscalls | ✅ | ✅ | ⏳ |

---

## 7. Chaos Testing

### Purpose

Find edge cases and rare bugs through randomized/adversarial testing.

### Fuzzing Strategy

```vir
// tests/fuzzing/syntax_fuzzer.vri

fn generate_random_program(depth: Int) -> String {
    if depth <= 0 {
        return random_literal()
    }
    
    match random_int(0, 5) {
        case 0 -> generate_binop(depth - 1)
        case 1 -> generate_if_stmt(depth - 1)
        case 2 -> generate_loop(depth - 1)
        case 3 -> generate_function(depth - 1)
        case 4 -> generate_entity(depth - 1)
        case _ -> random_literal()
    }
}

fn fuzz_parser(iterations: Int) {
    for i in 0..iterations {
        let program = generate_random_program(5)
        try {
            compile_and_run(program)
        } catch e {
            // Expected - many random programs are invalid
            // But should never CRASH
        }
    }
}
```

### Edge Case Generators

| Generator | Produces |
|-----------|----------|
| `extreme_nesting` | 1000 levels of `if { if { if { ...` |
| `long_strings` | 10MB strings |
| `unicode_chaos` | Combining characters, RTL, ZWJ |
| `float_specials` | NaN, Inf, -0.0, subnormals |
| `boundary_values` | INT_MAX, INT_MIN, etc. |

### Crash Detection

```vir
fn chaos_test(test_fn: fn()) {
    let pid = sys.fork()
    if pid == 0 {
        // Child process
        test_fn()
        sys.exit(0)
    } else {
        // Parent process
        let status = sys.waitpid(pid)
        if status.signaled {
            print("CRASH DETECTED: signal " + str(status.signal))
            // Log for reproduction
        }
    }
}
```

---

## 8. CI/CD Integration

### GitHub Actions Workflow

```yaml
# .github/workflows/test.yml

name: Test Suite

on: [push, pull_request]

jobs:
  test-linux-x86_64:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build
        run: make build
      - name: Unit Tests
        run: ./vir stdlib/vir/test/run_all_vtest.vri
      - name: Binary Consistency
        run: ./vir tests/tools/binary_diff_all.vri
      - name: Memory Tests
        run: ./vir tests/memory_stress_vtest.vri
      - name: Benchmarks
        run: ./vir benchmarks/runner.vri --check

  test-linux-arm64:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: uraimo/run-on-arch-action@v2
        with:
          arch: aarch64
          distro: ubuntu22.04
          run: |
            make build
            ./vir stdlib/vir/test/run_all_vtest.vri

  test-macos-arm64:
    runs-on: macos-14  # M1 runner
    steps:
      - uses: actions/checkout@v4
      - name: Build
        run: make build
      - name: Tests
        run: ./vir stdlib/vir/test/run_all_vtest.vri
```

### Test Reporting

```vir
// Generate JUnit-compatible XML for CI

fn generate_junit_report(results: Array[TestResult]) -> String {
    let xml = "<?xml version=\"1.0\"?>\n"
    xml = xml + "<testsuites>\n"
    
    for suite in group_by_suite(results) {
        xml = xml + "  <testsuite name=\"" + suite.name + "\" tests=\"" + str(suite.count) + "\">\n"
        for test in suite.tests {
            if test.passed {
                xml = xml + "    <testcase name=\"" + test.name + "\"/>\n"
            } else {
                xml = xml + "    <testcase name=\"" + test.name + "\">\n"
                xml = xml + "      <failure message=\"" + test.error + "\"/>\n"
                xml = xml + "    </testcase>\n"
            }
        }
        xml = xml + "  </testsuite>\n"
    }
    
    xml = xml + "</testsuites>\n"
    return xml
}
```

---

## Test Fortification Checklist

### Before Stage 4 Start

- [ ] All ~796 existing test functions pass
- [ ] Binary consistency tool created
- [ ] Memory leak detector implemented
- [ ] Baseline benchmarks recorded
- [ ] CI pipeline configured for all platforms

### During Stage 4

- [ ] Every C function replaced has corresponding test
- [ ] Binary consistency checked after each module
- [ ] Memory tests run after each major change
- [ ] Benchmarks checked for regressions

### After Stage 4 Complete

- [ ] Full regression suite passes
- [ ] No memory leaks detected
- [ ] Performance within 5% of C baseline
- [ ] All platforms tested

---

## Priority Test Files for Stage 4

| Priority | File | Tests |
|----------|------|-------|
| P0 | `engine_conformance_vtest.vri` | — |
| P0 | `vm_opcodes_vtest.vri` | 107 |
| P0 | `parser_conformance_vtest.vri` | 89 |
| P1 | `syscall_conformance_vtest.vri` | 31 |
| P1 | `memory_stress_vtest.vri` | (new) |
| P2 | `binary_diff_all.vri` | (new) |
| P2 | `benchmarks/runner.vri` | (new) |

---

*Document generated for Stage 4 "Kill C" preparation — 22/03/2026*
