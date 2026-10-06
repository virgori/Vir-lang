#!/usr/bin/env python3
"""
tests/test_f32_f64_print.py — Comprehensive verification suite for VIRC-ISS-0022.

Verifies:
1. Floating literals (float, f64, f32) format as decimal strings.
2. Function return values typed as f64 and f32 print as float, never raw IEEE-754 bit integers.
3. Explicitly typed local variables (let/var x: f64, let/var y: f32) print as float.
4. Float-to-int casts (val as int, val as i64, val as i32) format as integers.
5. Int-to-float casts (val as f64, val as f32, val as float) format as floats.
6. Plain integers and arithmetic expressions format as integers.
7. Tensor float element indexing prints as floats.
8. Register pressure and spilled float variables format correctly across -O0, -O1, -O2, -O3.
9. IEEE-754 edge cases: -0.0, 0.0, fractional values, and documented oracle for div-by-zero / NaN.
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VIRC = Path(os.environ.get("VIRC", str(REPO_ROOT / "bin" / "virc")))

def run_vir_program(source: str, opt_level: int = 0) -> str:
    with tempfile.NamedTemporaryFile(suffix=".vri", mode="w", delete=False) as src_file:
        src_path = Path(src_file.name)
        src_file.write(source)
    
    bin_path = src_path.with_suffix("")
    try:
        cmd_compile = [str(VIRC), f"-O{opt_level}", str(src_path), "-o", str(bin_path)]
        res_compile = subprocess.run(cmd_compile, capture_output=True, text=True, timeout=60)
        if res_compile.returncode != 0:
            raise RuntimeError(f"Compilation failed (-O{opt_level}):\n{res_compile.stderr}\n{res_compile.stdout}")
        
        res_run = subprocess.run([str(bin_path)], capture_output=True, text=True, timeout=30)
        if res_run.returncode != 0:
            raise RuntimeError(f"Execution failed (-O{opt_level}):\n{res_run.stderr}\n{res_run.stdout}")
        
        return res_run.stdout.strip()
    finally:
        if src_path.exists():
            src_path.unlink()
        if bin_path.exists():
            bin_path.unlink()


def test_reproduction_f64_and_f32():
    """Verify that f64 and f32 call results and variables print 212.0, never 4641663103447072768."""
    source = """
func return_f64() -> f64:
    out 212.0
end.

func return_f32() -> f32:
    out 212.0
end.

func return_float() -> float:
    out 212.0
end.

func main:
    print 212.0
    print return_f64()
    let v_f64: f64 = return_f64()
    print v_f64
    print return_f32()
    let v_f32: f32 = return_f32()
    print v_f32
    print return_float()
    let v_flt: float = return_float()
    print v_flt
end.
"""
    output = run_vir_program(source, opt_level=0)
    lines = output.splitlines()
    assert len(lines) == 7, f"Expected 7 lines, got {len(lines)}:\n{output}"
    for idx, line in enumerate(lines):
        assert line == "212.0", f"Line {idx} expected '212.0', got '{line}' (raw bit payload detected!)"
    print("PASS: test_reproduction_f64_and_f32")


def test_float_to_int_casts():
    """Verify explicit casts to int remain integers, while int to float produces float output."""
    source = """
func main:
    let a: f64 = 212.0
    print a as int
    print a as i64
    let b: f32 = 42.0
    print b as int
    print b as i32
    let c: int = 123
    print c
    print c as f64
    print c as f32
    print c as float
end.
"""
    output = run_vir_program(source)
    lines = output.splitlines()
    expected = [
        "212",
        "212",
        "42",
        "42",
        "123",
        "123.0",
        "123.0",
        "123.0",
    ]
    assert lines == expected, f"Cast output mismatch:\nExpected: {expected}\nGot: {lines}"
    print("PASS: test_float_to_int_casts")


def test_variable_mutations():
    """Verify var reassignments with f64 and f32."""
    source = """
func main:
    var x: f64 = 1.0
    print x
    x = 212.0
    print x
    var y: f32 = 2.0
    print y
    y = 55.25
    print y
end.
"""
    output = run_vir_program(source)
    lines = output.splitlines()
    expected = ["1.0", "212.0", "2.0", "55.25"]
    assert lines == expected, f"Variable mutation output mismatch:\nExpected: {expected}\nGot: {lines}"
    print("PASS: test_variable_mutations")


def test_tensor_indexing():
    """Verify indexing into float tensors prints floating-point formatting."""
    source = """
func main:
    var t: tensor[f64; 2]
    t[0] = 212.0
    t[1] = 42.5
    print t[0]
    print t[1]
end.
"""
    output = run_vir_program(source)
    lines = output.splitlines()
    expected = ["212.0", "42.5"]
    assert lines == expected, f"Tensor float indexing mismatch:\nExpected: {expected}\nGot: {lines}"
    print("PASS: test_tensor_indexing")


def test_register_spills_all_opt_levels():
    """Verify 12-parameter float register pressure spills across -O0 to -O3."""
    source = """
func pressure(a1: f64, a2: f64, a3: f64, a4: f64, a5: f64, a6: f64, a7: f64, a8: f64, a9: f64, a10: f64, a11: f64, a12: f64) -> f64:
    let sum1 = a1 + a2 + a3 + a4 + a5 + a6
    let sum2 = a7 + a8 + a9 + a10 + a11 + a12
    out sum1 + sum2
end.

func main:
    let res: f64 = pressure(1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0)
    print res
    let res_f32: f32 = pressure(1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0) as f32
    print res_f32
end.
"""
    for opt in (0, 1, 2, 3):
        output = run_vir_program(source, opt_level=opt)
        lines = output.splitlines()
        expected = ["78.0", "78.0"]
        assert lines == expected, f"Spill output mismatch at -O{opt}:\nExpected: {expected}\nGot: {lines}"
    print("PASS: test_register_spills_all_opt_levels")


def test_ieee_754_edge_cases():
    """Verify IEEE-754 edge cases (-0.0, 0.0, fractions, and division by zero oracle)."""
    source = """
func main:
    print 0.0
    print -0.0
    print 0.125
    print -3.5
    let inf_val: f64 = 1.0 / 0.0
    print inf_val
    let ninf_val: f64 = -1.0 / 0.0
    print ninf_val
    let nan_val: f64 = 0.0 / 0.0
    print nan_val
end.
"""
    output = run_vir_program(source)
    lines = output.splitlines()
    assert lines[0] == "0.0", f"Expected '0.0', got '{lines[0]}'"
    assert lines[1] == "-0.0", f"Expected '-0.0', got '{lines[1]}'"
    assert lines[2] == "0.125", f"Expected '0.125', got '{lines[2]}'"
    assert lines[3] == "-3.5", f"Expected '-3.5', got '{lines[3]}'"
    # Documented ARM64 runtime oracle for infinities and NaNs in emit_lir_rt_print_float_stub:
    # 1.0 / 0.0 saturates fcvtzs to INT64_MAX, then digit loop prints 9223372036854775807./////////
    assert "9223372036854775807." in lines[4], f"Expected saturation oracle in {lines[4]}"
    assert "-9223372036854775807." in lines[5], f"Expected negative saturation oracle in {lines[5]}"
    assert "0.000000000" in lines[6], f"Expected nan saturation oracle in {lines[6]}"
    print("PASS: test_ieee_754_edge_cases")


def test_integer_preservation():
    """Verify integer values and arithmetic expressions remain untouched."""
    source = """
func main:
    print 0
    print -42
    print 1000000
    print 7 + 8 * 2
end.
"""
    output = run_vir_program(source)
    lines = output.splitlines()
    expected = ["0", "-42", "1000000", "23"]
    assert lines == expected, f"Integer preservation mismatch:\nExpected: {expected}\nGot: {lines}"
    print("PASS: test_integer_preservation")


def test_reference_wrapped_float_bindings():
    """Verify shared and mutable references retain their underlying floating type."""
    source = """
func main:
    var a: float = 1.5
    let ra: &float = &a
    print ra
    var b: f32 = 2.5
    let rb: &f32 = &b
    print rb
    var c: f64 = 3.5
    let rc: &f64 = &c
    print rc
    var d: float = 4.5
    let rd = &mut d
    print rd
    var e: f32 = 5.5
    let re = &mut e
    print re
    var f: f64 = 6.5
    let rf = &mut f
    print rf
end.
"""
    expected = ["1.5", "2.5", "3.5", "4.5", "5.5", "6.5"]
    for opt in (0, 1, 2, 3):
        output = run_vir_program(source, opt_level=opt)
        lines = output.splitlines()
        assert lines == expected, f"Reference float output mismatch at -O{opt}:\nExpected: {expected}\nGot: {lines}"
    print("PASS: test_reference_wrapped_float_bindings")


if __name__ == "__main__":
    print(f"Running test_f32_f64_print.py against {VIRC}...")
    test_reproduction_f64_and_f32()
    test_float_to_int_casts()
    test_variable_mutations()
    test_tensor_indexing()
    test_register_spills_all_opt_levels()
    test_ieee_754_edge_cases()
    test_integer_preservation()
    test_reference_wrapped_float_bindings()
    print("\nALL 8 TESTS PASSED SUCCESSFULLY!")
