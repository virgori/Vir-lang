from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
VIRC = Path(os.environ.get("VIRC", str(ROOT / "bin/virc")))


def compile_and_run(source: str, opt: str = "-O0", target: str | None = None) -> subprocess.CompletedProcess:
    tmp_dir = ROOT / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix=".vri", dir=tmp_dir, delete=False) as f:
        f.write(source)
        src_path = Path(f.name)
    bin_path = src_path.with_suffix("")
    try:
        cmd = [str(VIRC), str(src_path), opt, "-o", str(bin_path)]
        if target:
            cmd.extend(["--target", target])
        c_res = subprocess.run(
            cmd,
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        if c_res.returncode != 0:
            return c_res
        if target and "x86_64" in target:
            rel_bin = bin_path.relative_to(ROOT)
            r_res = subprocess.run(
                ["docker", "run", "--rm", "--platform", "linux/amd64", "-v", f"{ROOT}:/work", "-w", "/work", "alpine", f"./{rel_bin}"],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            return r_res
        # On macOS arm64, sign binary before execution
        subprocess.run(["codesign", "-s", "-", "-f", str(bin_path)], capture_output=True)
        r_res = subprocess.run(
            [str(bin_path)],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        return r_res
    finally:
        if src_path.exists():
            src_path.unlink()
        if bin_path.exists():
            bin_path.unlink()


def test_positive_all_six_dtypes_at_all_opt_levels():
    """Verify all 6 normative dtypes (f32, f16, f64, i8, u8, i32) pass at O0, O1, O2, O3 on ARM64 and x86_64."""
    src = (ROOT / "tests/strict_v2/tensor_supported_types_positive.vri").read_text()
    for opt in ["-O0", "-O1", "-O2", "-O3"]:
        res_arm = compile_and_run(src, opt)
        assert res_arm.returncode == 0, f"ARM64 failed at {opt}: stdout={res_arm.stdout}, stderr={res_arm.stderr}"
        res_x86 = compile_and_run(src, opt, target="linux-x86_64")
        assert res_x86.returncode == 0, f"x86_64 failed at {opt}: stdout={res_x86.stdout}, stderr={res_x86.stderr}"


def test_positive_64_byte_payload_alignment_at_all_opt_levels():
    """Verify 64-byte payload boundary alignment passes at O0, O2, O3."""
    src = (ROOT / "tests/strict_v2/tensor_result_alignment_e2e.vri").read_text()
    for opt in ["-O0", "-O2", "-O3"]:
        res = compile_and_run(src, opt)
        assert res.returncode == 0, f"Failed at {opt}: stdout={res.stdout}, stderr={res.stderr}"


def test_positive_tensor_descriptor_propagation_all_opt_levels():
    """Verify tensor descriptors survive return, parameter, inference, and entity-field paths on both targets."""
    src = (ROOT / "tests/strict_v2/tensor_descriptor_propagation_e2e.vri").read_text()
    for opt in ["-O0", "-O1", "-O2", "-O3"]:
        res_arm = compile_and_run(src, opt)
        assert res_arm.returncode == 0, f"ARM64 descriptor propagation failed at {opt}: stdout={res_arm.stdout}, stderr={res_arm.stderr}"
        res_x86 = compile_and_run(src, opt, target="linux-x86_64")
        assert res_x86.returncode == 0, f"x86_64 descriptor propagation failed at {opt}: stdout={res_x86.stdout}, stderr={res_x86.stderr}"


def test_mutation_swapped_dimensions_fails_compile():
    """Mutation control: swapping inner dimensions in matmul must fail compilation with E3014."""
    bad_shape_src = """
    func main() -> int:
        var a: tensor[i32; 2, 3] = [1, 2, 3, 4, 5, 6]
        var b: tensor[i32; 2, 3] = [1, 2, 3, 4, 5, 6]
        var c = a ** b
        out 0
    end.
    """
    res = compile_and_run(bad_shape_src, "-O0")
    assert res.returncode != 0, "Compilation should fail on incompatible inner dimensions"
    assert "E3014" in res.stderr or "E3014" in res.stdout, f"Expected E3014: {res.stdout} {res.stderr}"


def test_mutation_dtype_erasure_mismatch_fails_compile():
    """Mutation control: attempting matmul across different element dtypes must be rejected with E3007."""
    mismatched_dtype_src = """
    func main() -> int:
        var a: tensor[f32; 2, 2] = [1.0, 2.0, 3.0, 4.0]
        var b: tensor[i32; 2, 2] = [1, 2, 3, 4]
        var c = a ** b
        out 0
    end.
    """
    res = compile_and_run(mismatched_dtype_src, "-O0")
    assert res.returncode != 0, "Compilation must reject dense tensor matmul with mismatched dtypes"
    assert "E3007" in res.stderr or "E3007" in res.stdout, f"Expected E3007: {res.stdout} {res.stderr}"


def test_mutation_corrupted_stride_detected():
    """Mutation control: reading 4-byte packed f32 at 8-byte double strides produces wrong value and kills mutant."""
    corrupt_stride_src = """
    extern func native_read_i64(addr: int, offset: int) -> int

    func main() -> int:
        var a: tensor[f32; 2, 2] = [1.0, 2.0, 3.0, 4.0]
        var a_ptr = a as int
        # In 4-byte packed layout:
        # offset 16..20: a[0, 0] = 1.0
        # offset 20..24: a[0, 1] = 2.0
        # offset 24..28: a[1, 0] = 3.0
        # A corrupted 8-byte stride read at offset 24 reads a[1, 0] bits instead of a[0, 1]!
        # If an oracle checks whether offset 24 holds 2.0, it will detect the corruption and exit 42.
        var corrupted_read = native_read_i64(a_ptr, 24)
        # 2.0 in double IEEE-754 is 4611686018427387904. The 32-bit float bits at offset 24 do NOT match this.
        if corrupted_read != 4611686018427387904 do
            out 42
        end
        out 0
    end.
    """
    res = compile_and_run(corrupt_stride_src, "-O0")
    # Exit code 42 proves the mutant (reading with 8-byte stride) was detected and killed!
    assert res.returncode == 42, f"Expected corrupted stride mutant to be killed with code 42, got {res.returncode}"


def test_mutation_signed_i8_zero_extension_rejection():
    """Mutation control: proves an oracle expecting zero-extended 255 for -1 correctly FAILS (kills mutant)."""
    mutated_src = """
    func main() -> int:
        var d: tensor[i8; 2] = [-1, 42]
        # Mutated assertion: expects buggy zero-extension (255) instead of -1
        if d[0] == 255 do out 0 end
        out 1
    end.
    """
    res = compile_and_run(mutated_src, "-O0")
    assert res.returncode == 1, "Should exit 1 because d[0] is sign-extended (-1), killing the zero-extension mutant"


def test_mutation_f16_scalar_width_change_detected():
    """Mutation control: proves 16-bit packed layout is sensitive to 32-bit stride mutant."""
    f16_stride_mutant_src = """
    extern func native_read_i64(addr: int, offset: int) -> int

    func main() -> int:
        var b: tensor[f16; 2] = [1.0, 2.0]
        # In 2-byte packed layout:
        # offset 16..18: b[0] = 1.0 (fp16 0x3C00)
        # offset 18..20: b[1] = 2.0 (fp16 0x4000)
        # A mutated 4-byte stride read at offset 20 reads beyond the tensor elements.
        var b_ptr = b as int
        var raw_word = native_read_i64(b_ptr, 16)
        var b1_bits = (raw_word shr 16) and 65535
        # b[1] in fp16 is 0x4000 (16384). If layout were 32-bit (stride 4), bits 16..31 would be 0 or mantissa.
        if b1_bits != 16384 do
            out 43
        end
        out 0
    end.
    """
    res = compile_and_run(f16_stride_mutant_src, "-O0")
    assert res.returncode == 0, f"Expected valid 2-byte packing, got {res.returncode}"


def test_mutation_zero_result_matmul_regression():
    """Mutation control: proves the non-zero oracle rejects zero-result regressions."""
    src = (ROOT / "tests/spec_gap_contract/tensor_rectangular_matmul_edge.vri").read_text()
    res = compile_and_run(src, "-O3")
    assert res.returncode == 0
    lines = [line.strip() for line in res.stdout.strip().splitlines() if line.strip()]
    assert lines == ["58", "64", "139", "154"], f"Expected non-zero oracle, got {lines}"
    assert lines != ["0", "0", "0", "0"], "Regression: matmul produced all zeroes"


def test_positive_f16_rectangular_matmul_all_opt_levels():
    """Verify f16 rectangular matmul (2x3 ** 3x2) and elementwise multiply (><) pass at O0-O3 on ARM64 and x86_64."""
    src = (ROOT / "tests/strict_v2/tensor_f16_matmul_rect_e2e.vri").read_text()
    for opt in ["-O0", "-O1", "-O2", "-O3"]:
        res_arm = compile_and_run(src, opt)
        assert res_arm.returncode == 0, f"ARM64 f16 matmul failed at {opt}: stdout={res_arm.stdout}, stderr={res_arm.stderr}"
        res_x86 = compile_and_run(src, opt, target="linux-x86_64")
        assert res_x86.returncode == 0, f"x86_64 f16 matmul failed at {opt}: stdout={res_x86.stdout}, stderr={res_x86.stderr}"


def test_positive_f16_ieee754_boundary_all_opt_levels():
    """Verify IEEE-754 binary16 boundary values (+0, -0, max finite, min subnormal, rounding, overflow) pass at O0-O3 on ARM64 and x86_64."""
    src = (ROOT / "tests/strict_v2/tensor_f16_boundary_e2e.vri").read_text()
    for opt in ["-O0", "-O1", "-O2", "-O3"]:
        res_arm = compile_and_run(src, opt)
        assert res_arm.returncode == 0, f"ARM64 f16 boundary failed at {opt}: stdout={res_arm.stdout}, stderr={res_arm.stderr}"
        res_x86 = compile_and_run(src, opt, target="linux-x86_64")
        assert res_x86.returncode == 0, f"x86_64 f16 boundary failed at {opt}: stdout={res_x86.stdout}, stderr={res_x86.stderr}"


def test_mutation_f16_negative_zero_sign_loss_killed():
    """Mutant control: if half conversion discards the sign bit of -0.0 (old x86 bug), 1.0/z1 > 0.0 becomes true.
    The correct compiler must preserve the sign bit, rejecting this mutant with exit code 1."""
    mutant_src = """
    func main() -> int:
        var pz: f64 = 0.0
        var nz: f64 = pz * -1.0
        var t: tensor[f16; 2] = [0.0, 0.0]
        t[1] = nz
        var z1: f64 = t[1]
        # Mutated assertion: expects the buggy positive reciprocal (> 0) from an erased sign bit
        if 1.0 / z1 > 0.0 do
            out 0
        end
        out 1
    end.
    """
    for opt in ["-O0", "-O2"]:
        res_arm = compile_and_run(mutant_src, opt)
        assert res_arm.returncode == 1, f"ARM64 mutant survived at {opt}: returncode={res_arm.returncode}"
        res_x86 = compile_and_run(mutant_src, opt, target="linux-x86_64")
        assert res_x86.returncode == 1, f"x86_64 mutant survived at {opt}: returncode={res_x86.returncode}"
