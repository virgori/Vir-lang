from __future__ import annotations

import os
import re
import shutil
import struct
import subprocess
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
VIRC = Path(os.environ.get("VIRC", str(ROOT / "bin/virc")))
Q80_SEMANTIC = ROOT / "tests/spec_gap_contract/q80_external_view_semantic.vri"
Q80_STRIDE80 = ROOT / "tests/spec_gap_contract/q80_external_view_stride80.vri"
Q80_DYNAMIC = ROOT / "tests/spec_gap_contract/q80_external_view_dynamic.vri"
Q80_E2E = ROOT / "tests/spec_gap_contract/q80_gemv_gemm_e2e.vri"
QUANTIZE_INFER = ROOT / "tests/spec_gap_contract/quantize_transparent_infer.vri"
PROBE_FRACTIONAL = ROOT / "tests/fixtures/probe_fractional_activation.vri"
TEST_X86_QUANT = ROOT / "tests/fixtures/test_x86_quant.vri"
PROBE_X86_FRACT = ROOT / "tests/fixtures/probe_fractional_x86.vri"

Q80_META_40 = (
    "codec=2 bits=8 size=40 align=8 qelem=2 rank=2 shape=2,32 "
    "block=40 stride=40 bytes=80 offset=0 view=80 ro=1 own=0 life=1 generation=1"
)
Q80_META_80 = (
    "codec=2 bits=8 size=40 align=8 qelem=2 rank=2 shape=2,64 "
    "block=40 stride=80 bytes=160 offset=0 view=160 ro=1 own=0 life=1 generation=1"
)


def run_dump(fixture: Path, *flags: str) -> str:
    res = subprocess.run(
        [str(VIRC), str(fixture), *flags],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert res.returncode == 0, res.stdout + res.stderr
    return res.stdout


def function_dump(output: str, name: str) -> str:
    marker = f"func {name}\n"
    assert marker in output
    body = output.rsplit(marker, 1)[1]
    return body.split("\nfunc ", 1)[0]


def semantic_main_dump(output: str) -> str:
    matches = list(re.finditer(r"(?m)^  decl \[2\] line \d+: main$", output))
    assert matches
    return output[matches[-1].start():]


def test_q80_external_view_semantic_dump() -> None:
    output = run_dump(Q80_SEMANTIC, "--dump-semantic")
    main = semantic_main_dump(output)
    assert "=== SEMANTIC DUMP ===" in output
    assert (
        "var view: quantized[q8_0; elem=f64; shape=2, 32; block=40; "
        "stride=40; align=8; bytes=80; offset=0; view=80; ro=1; "
        "own=0; life=1; generation=1]"
    ) in main


@pytest.mark.parametrize("dump_flag", ["--dump-mir", "--dump-lir"])
@pytest.mark.parametrize("opt_level", ["-O0", "-O1", "-O2", "-O3"])
def test_q80_external_view_metadata_survives_pipeline(
    dump_flag: str,
    opt_level: str,
) -> None:
    output = run_dump(Q80_SEMANTIC, opt_level, dump_flag)
    main = function_dump(output, "main")
    q80_calls = [line for line in main.splitlines() if "Call " in line and "codec=2" in line]
    assert len(q80_calls) == 2
    assert all(Q80_META_40 in line for line in q80_calls)


@pytest.mark.parametrize("dump_flag", ["--dump-mir", "--dump-lir"])
def test_q80_block_size_and_stride_remain_distinct(dump_flag: str) -> None:
    output = run_dump(Q80_STRIDE80, "-O3", dump_flag)
    main = function_dump(output, "main")
    q80_calls = [line for line in main.splitlines() if "Call " in line and "codec=2" in line]
    assert len(q80_calls) == 2
    assert all(Q80_META_80 in line for line in q80_calls)
    assert all("block=40 stride=40" not in line for line in q80_calls)


def test_q80_dynamic_values_keep_structured_descriptor() -> None:
    output = run_dump(Q80_DYNAMIC, "--dump-semantic")
    main = semantic_main_dump(output)
    assert "var view: quantized[q8_0;" in main
    assert "shape=?, ?" in main
    assert "stride=?" in main
    assert "align=?" in main
    assert "bytes=80; offset=0; view=80" in main
    assert "var view: Q80TensorView" not in main


def arm64_has_fadd_2d(binary_path: Path) -> bool:
    raw = binary_path.read_bytes()
    words = struct.unpack(f"<{len(raw) // 4}I", raw[: len(raw) // 4 * 4])
    return any((word & 0xFF20FC00) == 0x4E20D400 for word in words)


@pytest.mark.parametrize("opt_level", ["-O0", "-O3"])
def test_q80_simd_dispatch_and_no_simd_fallback(
    tmp_path: Path,
    opt_level: str,
) -> None:
    simd_binary = tmp_path / f"q80_{opt_level[1:]}_simd"
    scalar_binary = tmp_path / f"q80_{opt_level[1:]}_scalar"
    for output, extra_flags in (
        (simd_binary, []),
        (scalar_binary, ["--no-simd"]),
    ):
        build = subprocess.run(
            [str(VIRC), str(Q80_E2E), opt_level, *extra_flags, "-o", str(output)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        assert build.returncode == 0, build.stdout + build.stderr
    assert arm64_has_fadd_2d(simd_binary)
    assert not arm64_has_fadd_2d(scalar_binary)


def test_quantize_transparent_infer_mir_dump() -> None:
    res = subprocess.run(
        [str(VIRC), str(QUANTIZE_INFER), "--dump-mir"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert res.returncode == 0, res.stdout + res.stderr
    assert "=== MIR DUMP ===" in res.stdout
    assert "codec=1" in res.stdout
    assert "bits=8" in res.stdout
    assert "size=1" in res.stdout
    assert "align=16" in res.stdout


def test_quantize_transparent_infer_lir_dump() -> None:
    res = subprocess.run(
        [str(VIRC), str(QUANTIZE_INFER), "--dump-lir"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert res.returncode == 0, res.stdout + res.stderr
    assert "=== LIR DUMP ===" in res.stdout
    assert "codec=1" in res.stdout
    assert "bits=8" in res.stdout
    assert "size=1" in res.stdout
    assert "align=16" in res.stdout


def test_fractional_activation_probe_arm64() -> None:
    bin_path = ROOT / "scratch/test_probe_fract_bin"
    build = subprocess.run(
        [str(VIRC), str(PROBE_FRACTIONAL), "-o", str(bin_path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert build.returncode == 0, build.stdout + build.stderr
    run = subprocess.run(
        [str(bin_path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if bin_path.exists():
        bin_path.unlink()
    assert run.returncode == 0, run.stdout + run.stderr
    assert "190.5" in run.stdout.strip()


def test_x86_docker_quantized_execution() -> None:
    if not shutil.which("docker"):
        pytest.skip("Docker is not available")
    info = subprocess.run(["docker", "ps"], capture_output=True, check=False)
    if info.returncode != 0:
        pytest.skip("Docker daemon not running")

    int_bin = ROOT / "scratch/test_x86_int_probe"
    build_int = subprocess.run(
        [str(VIRC), str(TEST_X86_QUANT), "--target", "linux-x86_64", "-o", str(int_bin)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert build_int.returncode == 0, build_int.stdout + build_int.stderr
    res_int = subprocess.run(
        ["docker", "run", "--rm", "--platform", "linux/amd64", "-v", f"{ROOT}:/work", "-w", "/work", "alpine", f"./scratch/{int_bin.name}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if int_bin.exists():
        int_bin.unlink()
    assert res_int.returncode == 0, res_int.stderr
    assert "26" in res_int.stdout

    fract_bin = ROOT / "scratch/test_x86_fract_probe"
    build_fract = subprocess.run(
        [str(VIRC), str(PROBE_X86_FRACT), "--target", "linux-x86_64", "-o", str(fract_bin)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert build_fract.returncode == 0, build_fract.stdout + build_fract.stderr
    res_fract = subprocess.run(
        ["docker", "run", "--rm", "--platform", "linux/amd64", "-v", f"{ROOT}:/work", "-w", "/work", "alpine", f"./scratch/{fract_bin.name}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if fract_bin.exists():
        fract_bin.unlink()
    assert res_fract.returncode == 0, res_fract.stderr
    assert "190" in res_fract.stdout
