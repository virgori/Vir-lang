#!/usr/bin/env python3
"""
tools/gap_contract_runner.py — Strict Spec Gap Contract Test Runner

Runner for tests/spec_gap_contract/manifest.tsv.
Supports kinds:
  - run: compile, run, exact stdout and exit code match
  - compile_fail: compiler returns non-zero, diagnostic oracle match, no artifact
  - run_fail: compile succeeds, run traps/exits non-zero via error path
  - structural: runtime/behavioral gate + MIR/symbol/structural oracle check
  - wasm_run: compile to WASI, execute with Node.js, and inspect linear memory
  - riscv_structural: compile to RV64 ELF and inspect instruction encodings
  - blocked_contract: unconditionally reports BLOCKED (never PASS)
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "tests/spec_gap_contract/manifest.tsv"
DEFAULT_FIXTURES_DIR = ROOT / "tests/spec_gap_contract"
DEFAULT_BASELINE = ROOT / "docs/report/checklist/spec_gap_contract_baseline.tsv"


@dataclass
class TestEntry:
    test_id: str
    kind: str
    fixture: str
    oracle: str


@dataclass
class TestResult:
    test_id: str
    kind: str
    status: str  # PASS, FAIL, BLOCKED
    target: str
    compile_exit: Optional[int]
    run_exit: Optional[int]
    stdout: str
    stderr: str
    reason: str


def parse_manifest(manifest_path: Path) -> list[TestEntry]:
    entries: list[TestEntry] = []
    lines = manifest_path.read_text(encoding="utf-8").splitlines()
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) >= 4:
            entries.append(
                TestEntry(
                    test_id=parts[0].strip(),
                    kind=parts[1].strip(),
                    fixture=parts[2].strip(),
                    oracle=parts[3].strip(),
                )
            )
        elif len(parts) == 3:
            entries.append(
                TestEntry(
                    test_id=parts[0].strip(),
                    kind=parts[1].strip(),
                    fixture=parts[2].strip(),
                    oracle="",
                )
            )
    return entries


def extract_fixture_expected(fixture_path: Path) -> tuple[Optional[str], Optional[str]]:
    """Extract EXPECT stdout and EXPECT_DIAGNOSTIC from fixture comments if present."""
    content = fixture_path.read_text(encoding="utf-8", errors="replace")
    expected_stdout = None
    expected_diag = None

    m_start = re.search(r"#\s*EXPECT_START\n((?:#[^\n]*\n)+?)#\s*EXPECT_END", content)
    if m_start:
        lines = [
            line[1:].lstrip() if line.startswith("#") else line
            for line in m_start.group(1).splitlines()
        ]
        expected_stdout = "\n".join(lines).strip()
    else:
        m_exp = re.search(r"#\s*EXPECT:\s*\n((?:#[^\n]*\n)+)", content)
        if m_exp:
            lines = [
                line[1:].lstrip() if line.startswith("#") else line
                for line in m_exp.group(1).splitlines()
            ]
            expected_stdout = "\n".join(lines).strip()
        else:
            m_single = re.search(r"#\s*EXPECT:\s*([^\n]+)", content)
            if m_single:
                expected_stdout = m_single.group(1).strip().replace(r"\n", "\n")

    m_diag = re.search(r"#\s*EXPECT_DIAGNOSTIC:\s*([^\n]+)", content)
    if m_diag:
        expected_diag = m_diag.group(1).strip()

    return expected_stdout, expected_diag


def run_command(cmd: list[str], cwd: Path, timeout: float = 5.0) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as e:
        stdout = e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
        stderr = e.stderr.decode() if isinstance(e.stderr, bytes) else (e.stderr or "")
        return -999, stdout, stderr + f"\nTIMEOUT after {timeout}s"
    except Exception as e:
        return -998, "", str(e)


def run_x86_linux(binary_path: Path, timeout: float = 15.0) -> tuple[Optional[int], str, str]:
    """Execute a Linux x86_64 ELF binary via native host, qemu-x86_64, or qemu-system-x86_64 micro-VM."""
    import platform
    if not binary_path.exists():
        return None, "", f"Binary {binary_path} does not exist"

    # 1. Native x86_64 host
    if platform.machine() in ("x86_64", "AMD64"):
        ret, out, err = run_command([str(binary_path)], cwd=ROOT, timeout=timeout)
        return ret, out, err

    # 2. User-mode QEMU if available
    qemu_user = shutil.which("qemu-x86_64") or shutil.which("qemu-x86_64-static")
    if qemu_user:
        ret, out, err = run_command([qemu_user, str(binary_path)], cwd=ROOT, timeout=timeout)
        return ret, out, err

    # 3. System-mode QEMU with Linux micro-VM
    qemu_sys = shutil.which("qemu-system-x86_64") or "/opt/homebrew/bin/qemu-system-x86_64"
    kernel_path = Path("/tmp/vmlinuz-x86_64")
    busybox_path = Path("/tmp/busybox-x86_64")
    if Path(qemu_sys).exists() and kernel_path.exists() and busybox_path.exists():
        with tempfile.TemporaryDirectory(prefix="vir_qemu_") as tmpdir:
            td = Path(tmpdir)
            rootfs = td / "rootfs"
            rootfs.mkdir()
            for d in ["bin", "proc", "sys", "dev", "vir_test"]:
                (rootfs / d).mkdir()
            shutil.copy2(busybox_path, rootfs / "bin/busybox")
            (rootfs / "bin/busybox").chmod(0o755)
            shutil.copy2(binary_path, rootfs / "vir_test/test_binary")
            (rootfs / "vir_test/test_binary").chmod(0o755)
            init_script = (
                "#!/bin/busybox sh\n"
                "/bin/busybox mount -t proc proc /proc 2>/dev/null\n"
                "/bin/busybox mount -t sysfs sysfs /sys 2>/dev/null\n"
                "/bin/busybox mknod /dev/null c 1 3 2>/dev/null\n"
                "/bin/busybox mknod /dev/tty c 5 0 2>/dev/null\n"
                "/vir_test/test_binary\n"
                'echo "EXIT_CODE:$?"\n'
                "echo o > /proc/sysrq-trigger 2>/dev/null || /bin/busybox poweroff -f 2>/dev/null\n"
            )
            init_file = rootfs / "init"
            init_file.write_text(init_script)
            init_file.chmod(0o755)
            initrd_path = td / "initramfs.cpio.gz"
            subprocess.run(
                f"cd {rootfs} && find . | cpio -H newc -o 2>/dev/null | gzip -9 > {initrd_path}",
                shell=True,
                check=True
            )
            qcmd = [
                str(qemu_sys),
                "-kernel", str(kernel_path),
                "-initrd", str(initrd_path),
                "-append", "console=ttyS0 panic=-1 quiet rdinit=/init",
                "-nographic",
                "-no-reboot",
                "-m", "2048M",
                "-cpu", "max"
            ]
            proc = subprocess.run(qcmd, capture_output=True, text=True, timeout=timeout)
            raw_out = proc.stdout
            clean_text = re.sub(r"\x1b[a-zA-Z]|\x1b\[[0-9;?]*[a-zA-Z]", "", raw_out)
            if "Booting from ROM" in clean_text:
                clean_text = clean_text.split("Booting from ROM", 1)[1]
                clean_text = clean_text.lstrip(".")
            stdout_lines = []
            exit_code = None
            for line in clean_text.splitlines():
                line = line.strip()
                if line.startswith("EXIT_CODE:"):
                    try:
                        exit_code = int(line.split(":", 1)[1].strip())
                    except ValueError:
                        pass
                elif not line.startswith("[") and line:
                    stdout_lines.append(line)
            return exit_code, "\n".join(stdout_lines), proc.stderr

    return None, "", "No x86_64 executor available (native, qemu-x86_64, or qemu-system-x86_64)"


def check_compile_fail_oracle(oracle: str, compile_output: str) -> tuple[bool, str]:
    """Verify that compile error diagnostic satisfies oracle keywords."""
    out_lower = compile_output.lower()
    m_contains = re.search(r"diagnostic contains (.+)", oracle, re.IGNORECASE)
    if m_contains:
        spec = m_contains.group(1).strip()
        # Strip semicolon-separated directives (e.g. "; no artifact") — those are
        # checked separately (artifact existence) and are not keyword search terms.
        if ";" in spec:
            spec = spec[: spec.index(";")].strip()
        terms = [t.strip().lower() for t in spec.split(" and ")]
        for term in terms:
            if "/" in term:
                subterms = term.split("/")
                if not any(st.strip() in out_lower for st in subterms):
                    return False, f"diagnostic missing required keyword '{term}'"
            elif term not in out_lower:
                return False, f"diagnostic missing required keyword '{term}'"
        return True, "diagnostic matched required keywords"

    if "parser diagnostic" in oracle.lower():
        if "e1004" in out_lower or "parse" in out_lower or "syntax" in out_lower or "error" in out_lower:
            return True, "parser diagnostic present"
        return False, "expected parser diagnostic"

    if "error" in out_lower or "e1" in out_lower or "e2" in out_lower or "e3" in out_lower:
        return True, "diagnostic error present"
    return False, f"diagnostic does not match oracle: '{oracle}'"


def run_test(
    entry: TestEntry,
    virc_bin: Path,
    target: str = "",
    fixtures_dir: Path = DEFAULT_FIXTURES_DIR,
    timeout: float = 5.0,
    compile_timeout: float = 30.0,
    opt_level: str = "",
) -> TestResult:
    if entry.kind == "blocked_contract":
        return TestResult(
            test_id=entry.test_id,
            kind=entry.kind,
            status="BLOCKED",
            target=target,
            compile_exit=None,
            run_exit=None,
            stdout="",
            stderr="",
            reason=entry.oracle or "Blocked contract",
        )

    fixture_path = fixtures_dir / entry.fixture
    if not fixture_path.is_file():
        return TestResult(
            test_id=entry.test_id,
            kind=entry.kind,
            status="FAIL",
            target=target,
            compile_exit=None,
            run_exit=None,
            stdout="",
            stderr="",
            reason=f"Fixture not found: {fixture_path}",
        )

    with tempfile.TemporaryDirectory(prefix="spec_gap_") as tmpdir:
        tmp_path = Path(tmpdir)
        bin_out = tmp_path / "test_artifact"

        compile_target = (
            "wasm32-wasi-p1"
            if entry.kind == "wasm_run"
            else ("linux-riscv64" if entry.kind == "riscv_structural" else target)
        )
        compile_cmd = [str(virc_bin), str(fixture_path), "-o", str(bin_out)]
        if compile_target:
            compile_cmd.extend(["--target", compile_target])
        if opt_level:
            compile_cmd.append(opt_level)
        m_flags = re.search(r"#\s*VIRC_FLAGS:\s*([^\n]+)", fixture_path.read_text(encoding="utf-8", errors="replace"))
        if m_flags:
            compile_cmd.extend(m_flags.group(1).strip().split())
        elif "missing_reset" in entry.fixture:
            compile_cmd.append("--mutate-mir=missing_reset")
        elif "duplicate_reset" in entry.fixture:
            compile_cmd.append("--mutate-mir=duplicate_reset")
        elif "misordered_reset" in entry.fixture:
            compile_cmd.append("--mutate-mir=misordered_reset")

        c_exit, c_stdout, c_stderr = run_command(compile_cmd, cwd=ROOT, timeout=compile_timeout)
        c_all = c_stdout + "\n" + c_stderr

        # ── Kind: compile_fail ──
        if entry.kind == "compile_fail":
            if bin_out.exists():
                return TestResult(
                    test_id=entry.test_id,
                    kind=entry.kind,
                    status="FAIL",
                    target=target,
                    compile_exit=c_exit,
                    run_exit=None,
                    stdout=c_stdout,
                    stderr=c_stderr,
                    reason="Compiler unexpectedly generated an artifact for negative test",
                )
            if c_exit == 0:
                return TestResult(
                    test_id=entry.test_id,
                    kind=entry.kind,
                    status="FAIL",
                    target=target,
                    compile_exit=c_exit,
                    run_exit=None,
                    stdout=c_stdout,
                    stderr=c_stderr,
                    reason="Compilation succeeded with 0, expected compile rejection",
                )
            matched, reason = check_compile_fail_oracle(entry.oracle, c_all)
            return TestResult(
                test_id=entry.test_id,
                kind=entry.kind,
                status="PASS" if matched else "FAIL",
                target=target,
                compile_exit=c_exit,
                run_exit=None,
                stdout=c_stdout,
                stderr=c_stderr,
                reason=reason,
            )

        # Non compile-fail cases require successful compilation
        if c_exit != 0:
            return TestResult(
                test_id=entry.test_id,
                kind=entry.kind,
                status="FAIL",
                target=target,
                compile_exit=c_exit,
                run_exit=None,
                stdout=c_stdout,
                stderr=c_stderr,
                reason=f"Compilation failed with exit code {c_exit}",
            )

        if not bin_out.exists():
            return TestResult(
                test_id=entry.test_id,
                kind=entry.kind,
                status="FAIL",
                target=target,
                compile_exit=c_exit,
                run_exit=None,
                stdout=c_stdout,
                stderr=c_stderr,
                reason="Compilation succeeded but artifact does not exist",
            )

        if entry.kind == "wasm_run":
            if shutil.which("node") is None:
                return TestResult(
                    test_id=entry.test_id,
                    kind=entry.kind,
                    status="BLOCKED",
                    target=compile_target,
                    compile_exit=c_exit,
                    run_exit=None,
                    stdout="",
                    stderr="",
                    reason="Node.js is required for Wasm validation",
                )
            node_script = r"""
const fs = require("fs");
const { WASI } = require("wasi");
const wasi = new WASI({ version: "preview1", args: [process.argv[1]], env: process.env, preopens: { ".": "." } });
const wasmBuffer = fs.readFileSync(process.argv[1]);
const imports = wasi.getImportObject ? wasi.getImportObject() : { wasi_snapshot_preview1: wasi.wasiImport };
WebAssembly.instantiate(wasmBuffer, imports).then(({ instance }) => {
  let exitCode = 0;
  if (wasi.start) {
    exitCode = wasi.start(instance) || 0;
  } else {
    instance.exports._start();
  }
  if (process.argv[2] === "inspect_slab") {
    const view = new DataView(instance.exports.memory.buffer);
    console.log(`${view.getBigInt64(60000, true)}ok`);
  }
  process.exit(exitCode);
}).catch((error) => {
  console.error(error);
  process.exit(1);
});
"""
            extra_arg = ["inspect_slab"] if entry.test_id == "MEM-WASM-001" else []
            r_exit, r_stdout, r_stderr = run_command(
                ["node", "--no-warnings", "-e", node_script, str(bin_out)] + extra_arg,
                cwd=ROOT,
                timeout=timeout,
            )
            if entry.test_id == "MEM-WASM-001":
                return TestResult(
                    test_id=entry.test_id,
                    kind=entry.kind,
                    status="PASS" if r_exit == 0 and r_stdout.strip() == "0ok" else "FAIL",
                    target=compile_target,
                    compile_exit=c_exit,
                    run_exit=r_exit,
                    stdout=r_stdout,
                    stderr=r_stderr,
                    reason="Wasm slab reused the released size-class slot" if r_exit == 0 and r_stdout.strip() == "0ok" else "Wasm slab reuse validation/execution failed",
                )

            if r_exit != 0:
                return TestResult(
                    test_id=entry.test_id,
                    kind=entry.kind,
                    status="FAIL",
                    target=compile_target,
                    compile_exit=c_exit,
                    run_exit=r_exit,
                    stdout=r_stdout,
                    stderr=r_stderr,
                    reason=f"Wasm execution failed with non-zero exit code {r_exit}",
                )

            expected_stdout = None
            if entry.oracle.startswith("stdout="):
                expected_stdout = entry.oracle[7:].split(";")[0].replace(r"\n", "\n").strip()
            elif entry.oracle.startswith("exit="):
                pass
            actual_stdout = r_stdout.strip()
            if expected_stdout is not None and actual_stdout != expected_stdout:
                return TestResult(
                    test_id=entry.test_id,
                    kind=entry.kind,
                    status="FAIL",
                    target=compile_target,
                    compile_exit=c_exit,
                    run_exit=r_exit,
                    stdout=r_stdout,
                    stderr=r_stderr,
                    reason=f"Wasm stdout mismatch: expected '{expected_stdout}', got '{actual_stdout}'",
                )

            if entry.test_id == "SIMD-WASM-001":
                wasm_bytes = bin_out.read_bytes()
                has_vload = b"\xfd\x00" in wasm_bytes
                has_vstore = b"\xfd\x0b" in wasm_bytes
                has_i64x2_add = b"\xfd\xce\x01" in wasm_bytes
                has_f64x2_add = b"\xfd\xf0\x01" in wasm_bytes
                if not (has_vload and has_vstore and has_i64x2_add and has_f64x2_add):
                    return TestResult(
                        test_id=entry.test_id,
                        kind=entry.kind,
                        status="FAIL",
                        target=compile_target,
                        compile_exit=c_exit,
                        run_exit=r_exit,
                        stdout=r_stdout,
                        stderr=r_stderr,
                        reason=f"Wasm SIMD128 opcodes missing (vload={has_vload}, vstore={has_vstore}, i64x2.add={has_i64x2_add}, f64x2.add={has_f64x2_add})",
                    )
                # Also check --no-simd scalar fallback on Wasm32
                wasm_nosimd = tmp_path / "test_nosimd.wasm"
                ns_exit, _, _ = run_command(
                    [str(virc_bin), str(fixture_path), "--target", "wasm32-wasi-p1", "--no-simd", "-o", str(wasm_nosimd)],
                    cwd=ROOT,
                    timeout=compile_timeout,
                )
                if ns_exit != 0 or not wasm_nosimd.exists() or (b"\xfd\xce\x01" in wasm_nosimd.read_bytes()):
                    return TestResult(
                        test_id=entry.test_id,
                        kind=entry.kind,
                        status="FAIL",
                        target=compile_target,
                        compile_exit=ns_exit,
                        run_exit=r_exit,
                        stdout=r_stdout,
                        stderr=r_stderr,
                        reason="Wasm --no-simd failed to suppress i64x2.add opcode",
                    )

            return TestResult(
                test_id=entry.test_id,
                kind=entry.kind,
                status="PASS",
                target=compile_target,
                compile_exit=c_exit,
                run_exit=r_exit,
                stdout=r_stdout,
                stderr=r_stderr,
                reason="Wasm execution and SIMD128 structural opcodes matched expected oracle",
            )

        if entry.kind == "riscv_structural":
            artifact = bin_out.read_bytes()
            if entry.test_id == "SIMD-RISCV-001":
                # Limit scan strictly to the executable machine code in .text section
                code_bytes = None
                if len(artifact) >= 64 and artifact[:4] == b"\x7fELF" and artifact[4] == 2:
                    try:
                        e_shoff = struct.unpack_from("<Q", artifact, 40)[0]
                        e_shentsize = struct.unpack_from("<H", artifact, 58)[0]
                        e_shnum = struct.unpack_from("<H", artifact, 60)[0]
                        e_shstrndx = struct.unpack_from("<H", artifact, 62)[0]
                        if e_shoff > 0 and e_shnum > 0 and e_shstrndx < e_shnum:
                            sh_records = [
                                struct.unpack_from("<IIQQQQ", artifact, e_shoff + i * e_shentsize)
                                for i in range(e_shnum)
                            ]
                            strtab_hdr = sh_records[e_shstrndx]
                            strtab = artifact[strtab_hdr[4] : strtab_hdr[4] + strtab_hdr[5]]
                            for name_off, sh_type, sh_flags, sh_addr, sh_offset, sh_size in sh_records:
                                s_name = strtab[name_off:].split(b"\0")[0].decode("ascii", errors="ignore")
                                if s_name == ".text" and sh_size > 0:
                                    code_bytes = artifact[sh_offset : sh_offset + sh_size]
                                    break
                    except Exception as ex:
                        return TestResult(
                            test_id=entry.test_id,
                            kind=entry.kind,
                            status="FAIL",
                            target="linux-riscv64",
                            compile_exit=c_exit,
                            run_exit=None,
                            stdout=c_stdout,
                            stderr=c_stderr,
                            reason=f"ELF section header parsing error for RISC-V binary: {ex}",
                        )

                if code_bytes is None:
                    return TestResult(
                        test_id=entry.test_id,
                        kind=entry.kind,
                        status="FAIL",
                        target="linux-riscv64",
                        compile_exit=c_exit,
                        run_exit=None,
                        stdout=c_stdout,
                        stderr=c_stderr,
                        reason="Could not extract .text section from RISC-V ELF binary (parsing failed or .text missing)",
                    )
                words = struct.unpack(f"<{len(code_bytes) // 4}I", code_bytes[: len(code_bytes) // 4 * 4])
                # Check that scalar integer/FP ops are present in .text and RVV vector major opcode (0x57) is not used for flux
                has_scalar_add = any((w & 0xFE00707F) == 0x00000033 for w in words)
                has_rvv = any((w & 0x7F) == 0x57 for w in words)
                valid = has_scalar_add and not has_rvv
                reason = "RISC-V rv64d lowered flux operations to scalar loop fallback cleanly without RVV opcodes in .text"
                if not has_scalar_add:
                    reason = "RISC-V scalar fallback instructions missing in .text"
                elif has_rvv:
                    reason = "RISC-V .text section contains RVV opcode 0x57 when RVV is disabled"
                return TestResult(
                    test_id=entry.test_id,
                    kind=entry.kind,
                    status="PASS" if valid else "FAIL",
                    target="linux-riscv64",
                    compile_exit=c_exit,
                    run_exit=None,
                    stdout=c_stdout,
                    stderr=c_stderr,
                    reason=reason,
                )

            if entry.test_id == "SIMD-014":
                correct_fmv_d_x = struct.pack("<I", 0xF2038153)
                wrong_fmv_d_x = struct.pack("<I", 0xF0038153)
                valid = correct_fmv_d_x in artifact and wrong_fmv_d_x not in artifact
                return TestResult(
                    test_id=entry.test_id,
                    kind=entry.kind,
                    status="PASS" if valid else "FAIL",
                    target="linux-riscv64",
                    compile_exit=c_exit,
                    run_exit=None,
                    stdout=c_stdout,
                    stderr=c_stderr,
                    reason="FMV.D.X uses funct7 0x79" if valid else "RISC-V artifact is missing the correct FMV.D.X encoding or still contains funct7 0x78",
                )

            if entry.test_id == "TARGET-RISCV-003":
                words = struct.unpack(f"<{len(artifact) // 4}I", artifact[: len(artifact) // 4 * 4])
                jal_offsets = []
                for word in words:
                    if word & 0x7F != 0x6F or (word >> 7) & 0x1F != 1:
                        continue
                    imm = (
                        ((word >> 31) & 1) << 20
                        | ((word >> 21) & 0x3FF) << 1
                        | ((word >> 20) & 1) << 11
                        | ((word >> 12) & 0xFF) << 12
                    )
                    if imm & (1 << 20):
                        imm -= 1 << 21
                    jal_offsets.append(imm)
                valid = any(offset > 0 for offset in jal_offsets) and any(offset < 0 for offset in jal_offsets)
                return TestResult(
                    test_id=entry.test_id,
                    kind=entry.kind,
                    status="PASS" if valid else "FAIL",
                    target="linux-riscv64",
                    compile_exit=c_exit,
                    run_exit=None,
                    stdout=c_stdout,
                    stderr=c_stderr,
                    reason="Forward and entry-point JAL offsets are patched" if valid else f"Expected positive and negative patched JAL offsets, got {jal_offsets}",
                )

            return TestResult(
                test_id=entry.test_id,
                kind=entry.kind,
                status="FAIL",
                target="linux-riscv64",
                compile_exit=c_exit,
                run_exit=None,
                stdout=c_stdout,
                stderr=c_stderr,
                reason=f"No RISC-V structural oracle for {entry.test_id}",
            )

        # Run artifact
        run_cmd = [str(bin_out)]
        r_exit, r_stdout, r_stderr = run_command(run_cmd, cwd=ROOT, timeout=timeout)

        # ── Kind: run_fail ──
        if entry.kind == "run_fail":
            if r_exit == 0:
                return TestResult(
                    test_id=entry.test_id,
                    kind=entry.kind,
                    status="FAIL",
                    target=target,
                    compile_exit=c_exit,
                    run_exit=r_exit,
                    stdout=r_stdout,
                    stderr=r_stderr,
                    reason="Execution succeeded with exit 0, expected trap/run failure",
                )
            m = re.search(r"exit\s+(-?\d+)", entry.oracle)
            if m:
                expected_code = int(m.group(1))
                code_matched = (r_exit == expected_code) or (expected_code > 128 and r_exit == -(expected_code - 128)) or (expected_code < 0 and r_exit == 128 + abs(expected_code))
                if not code_matched:
                    return TestResult(
                        test_id=entry.test_id,
                        kind=entry.kind,
                        status="FAIL",
                        target=target,
                        compile_exit=c_exit,
                        run_exit=r_exit,
                        stdout=r_stdout,
                        stderr=r_stderr,
                        reason=f"Execution exit code {r_exit} does not match expected {expected_code}",
                    )
            return TestResult(
                test_id=entry.test_id,
                kind=entry.kind,
                status="PASS",
                target=target,
                compile_exit=c_exit,
                run_exit=r_exit,
                stdout=r_stdout,
                stderr=r_stderr,
                reason=f"Execution correctly trapped/exited non-zero ({r_exit})",
            )

        # ── Kind: run ──
        if entry.kind == "run":
            if r_exit != 0:
                return TestResult(
                    test_id=entry.test_id,
                    kind=entry.kind,
                    status="FAIL",
                    target=target,
                    compile_exit=c_exit,
                    run_exit=r_exit,
                    stdout=r_stdout,
                    stderr=r_stderr,
                    reason=f"Execution failed with non-zero exit code {r_exit}",
                )

            expected_stdout = None
            if entry.oracle.startswith("stdout="):
                expected_stdout = entry.oracle[7:].replace(r"\n", "\n").strip()
            else:
                exp_comment, _ = extract_fixture_expected(fixture_path)
                if exp_comment is not None:
                    expected_stdout = exp_comment

            actual_stdout = r_stdout.strip()
            if expected_stdout is not None:
                if actual_stdout != expected_stdout:
                    return TestResult(
                        test_id=entry.test_id,
                        kind=entry.kind,
                        status="FAIL",
                        target=target,
                        compile_exit=c_exit,
                        run_exit=r_exit,
                        stdout=r_stdout,
                        stderr=r_stderr,
                        reason=f"Stdout mismatch: expected '{expected_stdout}', got '{actual_stdout}'",
                    )

            return TestResult(
                test_id=entry.test_id,
                kind=entry.kind,
                status="PASS",
                target=target,
                compile_exit=c_exit,
                run_exit=r_exit,
                stdout=r_stdout,
                stderr=r_stderr,
                reason="Stdout and exit code matched expected oracle",
            )

        # ── Kind: structural ──
        if entry.kind == "structural":
            m_out = re.search(r"stdout=([^;]+)", entry.oracle)
            if m_out:
                exp_s = m_out.group(1).replace(r"\n", "\n").strip()
                if r_stdout.strip() != exp_s:
                    return TestResult(
                        test_id=entry.test_id,
                        kind=entry.kind,
                        status="FAIL",
                        target=target,
                        compile_exit=c_exit,
                        run_exit=r_exit,
                        stdout=r_stdout,
                        stderr=r_stderr,
                        reason=f"Structural test behavioral stdout mismatch: expected '{exp_s}', got '{r_stdout.strip()}'",
                    )
            if "factorial absent from runtime call graph" in entry.oracle:
                lowered_funcs = re.findall(r"AST->MIR func\s+\d+\s*:\s*(\w+)", c_all)
                if "factorial" in lowered_funcs:
                    return TestResult(
                        test_id=entry.test_id,
                        kind=entry.kind,
                        status="FAIL",
                        target=target,
                        compile_exit=c_exit,
                        run_exit=r_exit,
                        stdout=r_stdout,
                        stderr=r_stderr,
                        reason="Structural gate failed: 'factorial' was lowered to MIR runtime call graph",
                    )
                if bin_out.exists():
                    artifact_bytes = bin_out.read_bytes()
                    if b"factorial" in artifact_bytes:
                        return TestResult(
                            test_id=entry.test_id,
                            kind=entry.kind,
                            status="FAIL",
                            target=target,
                            compile_exit=c_exit,
                            run_exit=r_exit,
                            stdout=r_stdout,
                            stderr=r_stderr,
                            reason="Structural gate failed: 'factorial' symbol/string found in runtime binary artifact",
                        )

            if "no runtime PRECOMP/call" in entry.oracle:
                lowered_funcs = re.findall(r"AST->MIR func\s+\d+\s*:\s*(\w+)", c_all)
                for fn in lowered_funcs:
                    if "precomp" in fn.lower():
                        return TestResult(
                            test_id=entry.test_id,
                            kind=entry.kind,
                            status="FAIL",
                            target=target,
                            compile_exit=c_exit,
                            run_exit=r_exit,
                            stdout=r_stdout,
                            stderr=r_stderr,
                            reason=f"Structural gate failed: precomp function '{fn}' lowered to MIR runtime call graph",
                        )
                if "MIR_INTR_PRECOMP" in c_all or "runtime PRECOMP" in c_all:
                    return TestResult(
                        test_id=entry.test_id,
                        kind=entry.kind,
                        status="FAIL",
                        target=target,
                        compile_exit=c_exit,
                        run_exit=r_exit,
                        stdout=r_stdout,
                        stderr=r_stderr,
                        reason="Structural gate failed: runtime PRECOMP instruction found in compiler output",
                    )

            if entry.test_id == "MEM-STRUCT-001":
                if not bin_out.exists():
                    return TestResult(
                        test_id=entry.test_id,
                        kind=entry.kind,
                        status="FAIL",
                        target=target,
                        compile_exit=c_exit,
                        run_exit=r_exit,
                        stdout=r_stdout,
                        stderr=r_stderr,
                        reason="Structural gate failed: binary artifact not found",
                    )
                # Compile to assembly with -S to verify physical call instruction in main
                s_out = tmp_path / "struct.s"
                s_cmd = [str(virc_bin), str(fixture_path), "-S", "-o", str(s_out)]
                if target:
                    s_cmd.extend(["--target", target])
                if opt_level:
                    s_cmd.append(opt_level)
                s_exit, s_stdout, s_stderr = run_command(s_cmd, cwd=ROOT, timeout=10.0)
                if s_exit != 0 or not s_out.exists():
                    return TestResult(
                        test_id=entry.test_id,
                        kind=entry.kind,
                        status="FAIL",
                        target=target,
                        compile_exit=s_exit,
                        run_exit=None,
                        stdout=s_stdout,
                        stderr=s_stderr,
                        reason="Structural gate failed: unable to emit assembly with -S",
                    )
                s_content = s_out.read_text()
                # Locate main function body in assembly
                m_main = re.search(r"(?:_main|main):\s*\n(.*?)(?:\n\s*(?:_|\.)[a-zA-Z0-9_]+:|\Z)", s_content, re.DOTALL)
                if not m_main:
                    return TestResult(
                        test_id=entry.test_id,
                        kind=entry.kind,
                        status="FAIL",
                        target=target,
                        compile_exit=c_exit,
                        run_exit=r_exit,
                        stdout=r_stdout,
                        stderr=r_stderr,
                        reason="Structural gate failed: main function not found in assembly",
                    )
                main_body = m_main.group(1)
                # Verify that main contains an actual non-NOP call/branch targeting vir_free or heap_free
                has_free_call = bool(re.search(r"\b(bl|call|jal)\s+[_]?(vir_free|heap_free)\b", main_body))
                if not has_free_call:
                    return TestResult(
                        test_id=entry.test_id,
                        kind=entry.kind,
                        status="FAIL",
                        target=target,
                        compile_exit=c_exit,
                        run_exit=r_exit,
                        stdout=r_stdout,
                        stderr=r_stderr,
                        reason="Structural gate failed: main does not contain a concrete branch/call instruction to vir_free/heap_free",
                    )

            if entry.test_id == "SIMD-NEON-001":
                raw = bin_out.read_bytes()
                words = struct.unpack(f"<{len(raw) // 4}I", raw[: len(raw) // 4 * 4])
                has_ldr_q = any((w & 0xFFC00000) == 0x3DC00000 for w in words)
                has_str_q = any((w & 0xFFC00000) == 0x3D800000 for w in words)
                has_add_2d = any((w & 0xFF20FC00) == 0x4E208400 for w in words)
                has_fadd_2d = any((w & 0xFF20FC00) == 0x4E20D400 for w in words)
                if not (has_ldr_q and has_str_q and has_add_2d and has_fadd_2d):
                    return TestResult(
                        test_id=entry.test_id,
                        kind=entry.kind,
                        status="FAIL",
                        target=target,
                        compile_exit=c_exit,
                        run_exit=r_exit,
                        stdout=r_stdout,
                        stderr=r_stderr,
                        reason=f"ARM64 NEON 128-bit opcodes missing (ldr_q={has_ldr_q}, str_q={has_str_q}, add.2d={has_add_2d}, fadd.2d={has_fadd_2d})",
                    )
                # Verify --no-simd scalar fallback omits add.2d/fadd.2d and preserves output
                ns_bin = tmp_path / "neon_nosimd"
                ns_c_exit, _, _ = run_command(
                    [str(virc_bin), str(fixture_path), "--no-simd", "-o", str(ns_bin)],
                    cwd=ROOT,
                    timeout=compile_timeout,
                )
                ns_r_exit, ns_stdout, _ = run_command([str(ns_bin)], cwd=ROOT, timeout=timeout)
                ns_raw = ns_bin.read_bytes() if ns_bin.exists() else b""
                ns_words = struct.unpack(f"<{len(ns_raw) // 4}I", ns_raw[: len(ns_raw) // 4 * 4]) if ns_raw else ()
                ns_has_add_2d = any((w & 0xFF20FC00) in (0x4E208400, 0x4E20D400) for w in ns_words)
                if ns_c_exit != 0 or ns_r_exit != 0 or ns_stdout.strip() != r_stdout.strip() or ns_has_add_2d:
                    return TestResult(
                        test_id=entry.test_id,
                        kind=entry.kind,
                        status="FAIL",
                        target=target,
                        compile_exit=ns_c_exit,
                        run_exit=ns_r_exit,
                        stdout=ns_stdout,
                        stderr=r_stderr,
                        reason=f"ARM64 --no-simd fallback failed (ns_has_add_2d={ns_has_add_2d}, stdout_match={ns_stdout.strip() == r_stdout.strip()})",
                    )
                return TestResult(
                    test_id=entry.test_id,
                    kind=entry.kind,
                    status="PASS",
                    target=target,
                    compile_exit=c_exit,
                    run_exit=r_exit,
                    stdout=r_stdout,
                    stderr=r_stderr,
                    reason="ARM64 NEON 128-bit ldr/str q, add.2d, fadd.2d and --no-simd fallback verified",
                )

            if entry.test_id == "SIMD-SSE2-001":
                x86_bin = tmp_path / "sse2_elf"
                x86_exit, _, x86_err = run_command(
                    [str(virc_bin), str(fixture_path), "--target", "linux-x86_64", "-o", str(x86_bin)],
                    cwd=ROOT,
                    timeout=compile_timeout,
                )
                if x86_exit != 0 or not x86_bin.exists():
                    return TestResult(
                        test_id=entry.test_id,
                        kind=entry.kind,
                        status="FAIL",
                        target="linux-x86_64",
                        compile_exit=x86_exit,
                        run_exit=None,
                        stdout=r_stdout,
                        stderr=x86_err,
                        reason="Failed to compile x86-64 ELF artifact for SSE2 check",
                    )
                x86_bytes = x86_bin.read_bytes()
                has_movdqu_ld = (b"\xf3\x0f\x6f" in x86_bytes) or (b"\xf3\x41\x0f\x6f" in x86_bytes)
                has_movdqu_st = (b"\xf3\x0f\x7f" in x86_bytes) or (b"\xf3\x41\x0f\x7f" in x86_bytes)
                has_paddq = b"\x66\x0f\xd4" in x86_bytes
                has_addpd = b"\x66\x0f\x58" in x86_bytes
                if not (has_movdqu_ld and has_movdqu_st and has_paddq and has_addpd):
                    return TestResult(
                        test_id=entry.test_id,
                        kind=entry.kind,
                        status="FAIL",
                        target="linux-x86_64",
                        compile_exit=x86_exit,
                        run_exit=r_exit,
                        stdout=r_stdout,
                        stderr=r_stderr,
                        reason=f"x86-64 SSE2 opcodes missing (movdqu_ld={has_movdqu_ld}, movdqu_st={has_movdqu_st}, paddq={has_paddq}, addpd={has_addpd})",
                    )
                x86_ns_bin = tmp_path / "sse2_nosimd_elf"
                run_command(
                    [str(virc_bin), str(fixture_path), "--target", "linux-x86_64", "--no-simd", "-o", str(x86_ns_bin)],
                    cwd=ROOT,
                    timeout=compile_timeout,
                )
                if not x86_ns_bin.exists() or (b"\x66\x0f\xd4" in x86_ns_bin.read_bytes()):
                    return TestResult(
                        test_id=entry.test_id,
                        kind=entry.kind,
                        status="FAIL",
                        target="linux-x86_64",
                        compile_exit=x86_exit,
                        run_exit=r_exit,
                        stdout=r_stdout,
                        stderr=r_stderr,
                        reason="x86-64 --no-simd failed to suppress paddq opcode",
                    )
                return TestResult(
                    test_id=entry.test_id,
                    kind=entry.kind,
                    status="PASS",
                    target="linux-x86_64",
                    compile_exit=x86_exit,
                    run_exit=r_exit,
                    stdout=r_stdout,
                    stderr=r_stderr,
                    reason="x86-64 SSE2 movdqu load/store, paddq, addpd and --no-simd fallback verified",
                )

            if entry.test_id == "SIMD-SLP-001":
                raw = bin_out.read_bytes()
                words = struct.unpack(f"<{len(raw) // 4}I", raw[: len(raw) // 4 * 4])
                arm_add_2d = any((w & 0xFF20FC00) == 0x4E208400 for w in words)
                x86_slp = tmp_path / "slp_x86"
                run_command(
                    [str(virc_bin), str(fixture_path), "-O2", "--target", "linux-x86_64", "-o", str(x86_slp)],
                    cwd=ROOT,
                    timeout=compile_timeout,
                )
                x86_paddq = x86_slp.exists() and (b"\x66\x0f\xd4" in x86_slp.read_bytes())
                wasm_slp = tmp_path / "slp_wasm.wasm"
                run_command(
                    [str(virc_bin), str(fixture_path), "-O2", "--target", "wasm32-wasi-p1", "-o", str(wasm_slp)],
                    cwd=ROOT,
                    timeout=compile_timeout,
                )
                wasm_i64x2 = wasm_slp.exists() and (b"\xfd\xce\x01" in wasm_slp.read_bytes())
                if not (arm_add_2d and x86_paddq and wasm_i64x2):
                    return TestResult(
                        test_id=entry.test_id,
                        kind=entry.kind,
                        status="FAIL",
                        target=target,
                        compile_exit=c_exit,
                        run_exit=r_exit,
                        stdout=r_stdout,
                        stderr=r_stderr,
                        reason=f"SLP pair vectorization missing native SIMD opcodes (arm_add_2d={arm_add_2d}, x86_paddq={x86_paddq}, wasm_i64x2={wasm_i64x2})",
                    )
                # Verify alias check blocks SLP when dst aliases src1, while --mutate-mir=missing_slp_alias_check bypasses it
                alias_src = tmp_path / "slp_alias_check.vri"
                alias_src.write_text(
                    "func main:\n"
                    "    var dst = [10, 20]\n"
                    "    let b = [1, 2]\n"
                    "    dst[0] = dst[0] + b[0]\n"
                    "    dst[1] = dst[1] + b[1]\n"
                    "    print dst[0]\n"
                    "    out 0\n"
                    "end.\n",
                    encoding="utf-8",
                )
                safe_bin = tmp_path / "slp_alias_safe"
                mut_bin = tmp_path / "slp_alias_mut"
                run_command([str(virc_bin), str(alias_src), "-O2", "-o", str(safe_bin)], cwd=ROOT, timeout=compile_timeout)
                run_command(
                    [str(virc_bin), str(alias_src), "-O2", "--mutate-mir=missing_slp_alias_check", "-o", str(mut_bin)],
                    cwd=ROOT,
                    timeout=compile_timeout,
                )
                safe_words = struct.unpack(f"<{len(safe_bin.read_bytes()) // 4}I", safe_bin.read_bytes()[: len(safe_bin.read_bytes()) // 4 * 4]) if safe_bin.exists() else ()
                mut_words = struct.unpack(f"<{len(mut_bin.read_bytes()) // 4}I", mut_bin.read_bytes()[: len(mut_bin.read_bytes()) // 4 * 4]) if mut_bin.exists() else ()
                safe_has_vec = any((w & 0xFF20FC00) == 0x4E208400 for w in safe_words)
                mut_has_vec = any((w & 0xFF20FC00) == 0x4E208400 for w in mut_words)
                if safe_has_vec or not mut_has_vec:
                    return TestResult(
                        test_id=entry.test_id,
                        kind=entry.kind,
                        status="FAIL",
                        target=target,
                        compile_exit=c_exit,
                        run_exit=r_exit,
                        stdout=r_stdout,
                        stderr=r_stderr,
                        reason=f"SLP alias check mutation verification failed (safe_has_vec={safe_has_vec}, mut_has_vec={mut_has_vec})",
                    )
                return TestResult(
                    test_id=entry.test_id,
                    kind=entry.kind,
                    status="PASS",
                    target=target,
                    compile_exit=c_exit,
                    run_exit=r_exit,
                    stdout=r_stdout,
                    stderr=r_stderr,
                    reason="SLP pair auto-vectorized across ARM64/x86_64/Wasm32 and alias mutation check verified",
                )

            if entry.test_id == "SIMD-LOOP-001":
                raw = bin_out.read_bytes()
                words = struct.unpack(f"<{len(raw) // 4}I", raw[: len(raw) // 4 * 4])
                arm_add_2d = any((w & 0xFF20FC00) == 0x4E208400 for w in words)
                if not arm_add_2d:
                    return TestResult(
                        test_id=entry.test_id,
                        kind=entry.kind,
                        status="FAIL",
                        target=target,
                        compile_exit=c_exit,
                        run_exit=r_exit,
                        stdout=r_stdout,
                        stderr=r_stderr,
                        reason="1D loop auto-vectorization did not emit NEON add.2d at -O2",
                    )
                # Verify --mutate-mir=missing_slp_tail drops the odd tail lane (N=5) and fails output comparison
                mut_tail_bin = tmp_path / "loop_mut_tail"
                run_command(
                    [str(virc_bin), str(fixture_path), "-O2", "--mutate-mir=missing_slp_tail", "-o", str(mut_tail_bin)],
                    cwd=ROOT,
                    timeout=compile_timeout,
                )
                _, mut_stdout, _ = run_command([str(mut_tail_bin)], cwd=ROOT, timeout=timeout)
                if mut_stdout.strip() == r_stdout.strip():
                    return TestResult(
                        test_id=entry.test_id,
                        kind=entry.kind,
                        status="FAIL",
                        target=target,
                        compile_exit=c_exit,
                        run_exit=r_exit,
                        stdout=mut_stdout,
                        stderr=r_stderr,
                        reason="--mutate-mir=missing_slp_tail unexpectedly produced identical output for odd N=5 loop",
                    )
                return TestResult(
                    test_id=entry.test_id,
                    kind=entry.kind,
                    status="PASS",
                    target=target,
                    compile_exit=c_exit,
                    run_exit=r_exit,
                    stdout=r_stdout,
                    stderr=r_stderr,
                    reason="1D loop stride-2 vectorization + odd tail N=5 and missing_slp_tail mutation check verified",
                )

            if entry.test_id == "SIMD-PROMOTE-001":
                raw = bin_out.read_bytes()
                words = struct.unpack(f"<{len(raw) // 4}I", raw[: len(raw) // 4 * 4])
                arm_has_neon = any(w in (0x3CED6A60, 0x3CAD6AC0) or (w & 0xFFC00000) in (0x3DC00000, 0x3D800000) for w in words)
                if not arm_has_neon or r_exit != 0 or r_stdout.strip() != "42":
                    return TestResult(
                        test_id=entry.test_id,
                        kind=entry.kind,
                        status="FAIL",
                        target=target,
                        compile_exit=c_exit,
                        run_exit=r_exit,
                        stdout=r_stdout,
                        stderr=r_stderr,
                        reason=f"ARM64 promotion execution or NEON opcodes failed (arm_has_neon={arm_has_neon}, exit={r_exit}, stdout={r_stdout.strip()})",
                    )
                ns_bin = tmp_path / "prom_nosimd"
                ns_c_exit, _, _ = run_command([str(virc_bin), str(fixture_path), "--no-simd", "-o", str(ns_bin)], cwd=ROOT, timeout=compile_timeout)
                ns_r_exit, ns_stdout, _ = run_command([str(ns_bin)], cwd=ROOT, timeout=timeout)
                ns_raw = ns_bin.read_bytes() if ns_bin.exists() else b""
                ns_words = struct.unpack(f"<{len(ns_raw) // 4}I", ns_raw[: len(ns_raw) // 4 * 4]) if ns_raw else ()
                ns_has_neon_stub = any(w in (0x3CED6A60, 0x3CAD6AC0) for w in ns_words)
                if ns_c_exit != 0 or ns_r_exit != 0 or ns_stdout.strip() != "42" or ns_has_neon_stub:
                    return TestResult(
                        test_id=entry.test_id,
                        kind=entry.kind,
                        status="FAIL",
                        target=target,
                        compile_exit=ns_c_exit,
                        run_exit=ns_r_exit,
                        stdout=ns_stdout,
                        stderr=r_stderr,
                        reason=f"ARM64 --no-simd promotion failed to suppress NEON stub (ns_has_neon_stub={ns_has_neon_stub})",
                    )
                x86_bin = tmp_path / "prom_x86"
                run_command([str(virc_bin), str(fixture_path), "--target", "linux-x86_64", "-o", str(x86_bin)], cwd=ROOT, timeout=compile_timeout)
                x86_bytes = x86_bin.read_bytes() if x86_bin.exists() else b""
                x86_has_movdqu = (b"\xf3\x0f\x6f" in x86_bytes) or (b"\xf3\x41\x0f\x6f" in x86_bytes) or (b"\xf3\x0f\x7f" in x86_bytes)
                x86_r_exit, x86_r_stdout, x86_r_stderr = run_x86_linux(x86_bin, timeout=timeout)
                x86_ns_bin = tmp_path / "prom_x86_ns"
                run_command([str(virc_bin), str(fixture_path), "--target", "linux-x86_64", "--no-simd", "-o", str(x86_ns_bin)], cwd=ROOT, timeout=compile_timeout)
                x86_ns_bytes = x86_ns_bin.read_bytes() if x86_ns_bin.exists() else b""
                x86_ns_has_movdqu = (b"\xf3\x0f\x6f" in x86_ns_bytes) or (b"\xf3\x41\x0f\x6f" in x86_ns_bytes)
                x86_semantic_ok = (x86_r_exit is not None and x86_r_exit == 0 and x86_r_stdout is not None and x86_r_stdout.strip() == "42")
                if not x86_has_movdqu or x86_ns_has_movdqu or not x86_semantic_ok:
                    return TestResult(
                        test_id=entry.test_id,
                        kind=entry.kind,
                        status="FAIL",
                        target="linux-x86_64",
                        compile_exit=c_exit,
                        run_exit=x86_r_exit,
                        stdout=x86_r_stdout or r_stdout,
                        stderr=x86_r_stderr or r_stderr,
                        reason=f"x86-64 promotion check failed (has_movdqu={x86_has_movdqu}, ns_has_movdqu={x86_ns_has_movdqu}, semantic_ok={x86_semantic_ok}, x86_exit={x86_r_exit}, x86_stdout={repr(x86_r_stdout)})",
                    )
                wasm_bin = tmp_path / "prom_wasm.wasm"
                run_command([str(virc_bin), str(fixture_path), "--target", "wasm32-wasi-p1", "-o", str(wasm_bin)], cwd=ROOT, timeout=compile_timeout)
                wasm_bytes = wasm_bin.read_bytes() if wasm_bin.exists() else b""
                wasm_has_v128 = (b"\xfd\x00" in wasm_bytes) and (b"\xfd\x0b" in wasm_bytes)
                wasm_ns_bin = tmp_path / "prom_wasm_ns.wasm"
                run_command([str(virc_bin), str(fixture_path), "--target", "wasm32-wasi-p1", "--no-simd", "-o", str(wasm_ns_bin)], cwd=ROOT, timeout=compile_timeout)
                wasm_ns_bytes = wasm_ns_bin.read_bytes() if wasm_ns_bin.exists() else b""
                wasm_ns_has_v128 = (b"\xfd\x00" in wasm_ns_bytes) or (b"\xfd\x0b" in wasm_ns_bytes)
                if not wasm_has_v128 or wasm_ns_has_v128:
                    return TestResult(
                        test_id=entry.test_id,
                        kind=entry.kind,
                        status="FAIL",
                        target="wasm32-wasi-p1",
                        compile_exit=c_exit,
                        run_exit=None,
                        stdout=r_stdout,
                        stderr=r_stderr,
                        reason=f"Wasm32 SIMD128 promotion check failed (has_v128={wasm_has_v128}, ns_has_v128={wasm_ns_has_v128})",
                    )
                return TestResult(
                    test_id=entry.test_id,
                    kind=entry.kind,
                    status="PASS",
                    target=target,
                    compile_exit=c_exit,
                    run_exit=r_exit,
                    stdout=r_stdout,
                    stderr=r_stderr,
                    reason="Multi-target promotion SIMD fast path (ARM64 NEON, x86-64 SSE2, Wasm SIMD128) and --no-simd fallback verified",
                )

            if entry.test_id == "SIMD-PROMOTE-X86-001":
                x86_simd_bin = tmp_path / "prom_x86_simd"
                c_exit, _, _ = run_command([str(virc_bin), str(fixture_path), "--target", "linux-x86_64", "-o", str(x86_simd_bin)], cwd=ROOT, timeout=compile_timeout)
                if c_exit != 0 or not x86_simd_bin.exists():
                    return TestResult(
                        test_id=entry.test_id,
                        kind=entry.kind,
                        status="FAIL",
                        target="linux-x86_64",
                        compile_exit=c_exit,
                        run_exit=None,
                        stdout="",
                        stderr="",
                        reason="Compilation for linux-x86_64 default SIMD failed",
                    )
                x86_simd_bytes = x86_simd_bin.read_bytes()
                has_movdqu = (b"\xf3\x0f\x6f" in x86_simd_bytes) or (b"\xf3\x41\x0f\x6f" in x86_simd_bytes) or (b"\xf3\x0f\x7f" in x86_simd_bytes)
                simd_exit, simd_out, simd_err = run_x86_linux(x86_simd_bin, timeout=timeout)

                x86_ns_bin = tmp_path / "prom_x86_nosimd"
                ns_c_exit, _, _ = run_command([str(virc_bin), str(fixture_path), "--target", "linux-x86_64", "--no-simd", "-o", str(x86_ns_bin)], cwd=ROOT, timeout=compile_timeout)
                if ns_c_exit != 0 or not x86_ns_bin.exists():
                    return TestResult(
                        test_id=entry.test_id,
                        kind=entry.kind,
                        status="FAIL",
                        target="linux-x86_64",
                        compile_exit=ns_c_exit,
                        run_exit=None,
                        stdout="",
                        stderr="",
                        reason="Compilation for linux-x86_64 --no-simd failed",
                    )
                x86_ns_bytes = x86_ns_bin.read_bytes()
                ns_has_movdqu = (b"\xf3\x0f\x6f" in x86_ns_bytes) or (b"\xf3\x41\x0f\x6f" in x86_ns_bytes) or (b"\xf3\x0f\x7f" in x86_ns_bytes)
                ns_exit, ns_out, ns_err = run_x86_linux(x86_ns_bin, timeout=timeout)

                simd_ok = (simd_exit is not None and simd_exit == 0 and simd_out.strip() == "42")
                ns_ok = (ns_exit is not None and ns_exit == 0 and ns_out.strip() == "42")

                if not has_movdqu or ns_has_movdqu or not simd_ok or not ns_ok:
                    return TestResult(
                        test_id=entry.test_id,
                        kind=entry.kind,
                        status="FAIL",
                        target="linux-x86_64",
                        compile_exit=c_exit,
                        run_exit=simd_exit,
                        stdout=simd_out,
                        stderr=simd_err or ns_err,
                        reason=f"x86-64 nested arena promotion failed (has_movdqu={has_movdqu}, ns_has_movdqu={ns_has_movdqu}, simd_ok={simd_ok}, simd_exit={simd_exit}, simd_out={repr(simd_out)}, ns_ok={ns_ok}, ns_exit={ns_exit}, ns_out={repr(ns_out)})",
                    )

                return TestResult(
                    test_id=entry.test_id,
                    kind=entry.kind,
                    status="PASS",
                    target="linux-x86_64",
                    compile_exit=0,
                    run_exit=0,
                    stdout=simd_out,
                    stderr="",
                    reason="x86-64 nested arena deep-graph promotion verified under QEMU (both default SIMD and --no-simd exited 0 with stdout 42)",
                )

            if entry.test_id == "TARGET-002":
                if r_exit != 37:
                    return TestResult(
                        test_id=entry.test_id,
                        kind=entry.kind,
                        status="FAIL",
                        target=target,
                        compile_exit=c_exit,
                        run_exit=r_exit,
                        stdout=r_stdout,
                        stderr=r_stderr,
                        reason=f"Expected exit code 37, got {r_exit}",
                    )
                return TestResult(
                    test_id=entry.test_id,
                    kind=entry.kind,
                    status="PASS",
                    target=target,
                    compile_exit=c_exit,
                    run_exit=r_exit,
                    stdout=r_stdout,
                    stderr=r_stderr,
                    reason="Exited with code 37 as required",
                )

            return TestResult(
                test_id=entry.test_id,
                kind=entry.kind,
                status="FAIL" if r_exit != 0 else "PASS",
                target=target,
                compile_exit=c_exit,
                run_exit=r_exit,
                stdout=r_stdout,
                stderr=r_stderr,
                reason=f"Structural check executed (exit={r_exit})",
            )

    return TestResult(
        test_id=entry.test_id,
        kind=entry.kind,
        status="FAIL",
        target=target,
        compile_exit=None,
        run_exit=None,
        stdout="",
        stderr="",
        reason=f"Unknown test kind {entry.kind}",
    )


def save_baseline(results: list[TestResult], output_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# id\tkind\tstatus\ttarget\tcompile_exit\trun_exit\treason\tstdout_escaped\n")
        for r in results:
            clean_stdout = r.stdout.strip().replace("\n", "\\n").replace("\t", " ")
            clean_reason = r.reason.replace("\t", " ").replace("\n", " ")
            f.write(
                f"{r.test_id}\t{r.kind}\t{r.status}\t{r.target}\t"
                f"{r.compile_exit if r.compile_exit is not None else ''}\t"
                f"{r.run_exit if r.run_exit is not None else ''}\t"
                f"{clean_reason}\t{clean_stdout}\n"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Vir Spec Gap Contract Runner")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST, help="Path to manifest.tsv")
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES_DIR, help="Fixtures directory")
    parser.add_argument("--virc", type=Path, default=ROOT / "bin/virc", help="Path to virc compiler")
    parser.add_argument("--target", type=str, default="macos-arm64", help="Target architecture")
    parser.add_argument("--save-baseline", type=Path, default=None, help="Path to save baseline TSV")
    parser.add_argument("--filter", type=str, default="", help="Regex filter by test ID")
    parser.add_argument("--group", type=str, default="", help="Filter by group/phase (e.g. Phase1)")
    parser.add_argument("--timeout", type=float, default=5.0, help="Execution timeout in seconds")
    parser.add_argument("--compile-timeout", type=float, default=30.0, help="Compilation timeout in seconds (default 30; use 60+ for -O2/-O3)")
    parser.add_argument("--opt-level", type=str, default="", help="Optimization level flag (-O0, -O1, -O2, -O3)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print details for every test")
    args = parser.parse_args()

    if not args.virc.is_file() or not os.access(args.virc, os.X_OK):
        print(f"Error: Compiler executable not found or not executable: {args.virc}", file=sys.stderr)
        return 1

    entries = parse_manifest(args.manifest)

    if args.group.lower() == "phase1":
        entries = [
            e for e in entries
            if e.test_id.startswith("PREC-")
            or e.test_id.startswith("NEG-")
            or e.test_id.startswith("FLOAT-")
            or e.test_id.startswith("CAST-")
        ]
    elif args.filter:
        pattern = re.compile(args.filter, re.IGNORECASE)
        entries = [e for e in entries if pattern.search(e.test_id)]

    print(f"==================================================")
    print(f"  Vir Spec Gap Contract Runner")
    manifest_rel = args.manifest.resolve().relative_to(ROOT) if args.manifest.resolve().is_relative_to(ROOT) else args.manifest
    virc_rel = args.virc.resolve().relative_to(ROOT) if args.virc.resolve().is_relative_to(ROOT) else args.virc
    print(f"  Manifest : {manifest_rel}")
    print(f"  Compiler : {virc_rel}")
    print(f"  Target   : {args.target}")
    if args.opt_level:
        print(f"  OptLevel : {args.opt_level}")
    print(f"  Total    : {len(entries)} tests")
    print(f"==================================================\n")

    results: list[TestResult] = []
    pass_count = 0
    fail_count = 0
    blocked_count = 0

    for idx, entry in enumerate(entries, 1):
        res = run_test(
            entry,
            virc_bin=args.virc,
            target=args.target,
            fixtures_dir=args.fixtures,
            timeout=args.timeout,
            compile_timeout=args.compile_timeout,
            opt_level=args.opt_level,
        )
        results.append(res)

        if res.status == "PASS":
            pass_count += 1
            status_str = "\033[92mPASS\033[0m"
        elif res.status == "BLOCKED":
            blocked_count += 1
            status_str = "\033[93mBLOCKED\033[0m"
        else:
            fail_count += 1
            status_str = "\033[91mFAIL\033[0m"

        print(f"[{idx:02d}/{len(entries):02d}] {res.test_id:<12} [{res.kind:<14}] {status_str} : {res.reason}")
        if args.verbose and res.status == "FAIL":
            if res.compile_exit != 0 and res.compile_exit is not None:
                print(f"    Compile Error (exit {res.compile_exit}):\n{res.stdout}\n{res.stderr}")
            elif res.run_exit is not None:
                print(f"    Run Output (exit {res.run_exit}):\n{res.stdout}")

    if args.save_baseline:
        save_baseline(results, args.save_baseline)
        print(f"\nBaseline saved to: {args.save_baseline.relative_to(ROOT)}")

    print(f"\nSummary:")
    print(f"  PASS    : {pass_count}")
    print(f"  FAIL    : {fail_count}")
    print(f"  BLOCKED : {blocked_count}")
    print(f"  TOTAL   : {len(entries)}")

    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
