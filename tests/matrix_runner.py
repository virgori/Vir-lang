#!/usr/bin/env python3
"""
matrix_runner.py — Strict 8-Target Matrix Validation Runner for Vir Compiler.

Targets:
  1. macos-arm64          (macOS Darwin raw syscall, AAPCS64)
  2. macos-arm64-libsystem(macOS dynamic libSystem.B.dylib, AAPCS64)
  3. linux-arm64          (Linux static ELF, AAPCS64)
  4. windows-arm64        (Windows PE32+, ARM64 ABI, Kernel32 IAT)
  5. linux-x86_64         (Linux static ELF, SysV AMD64)
  6. windows-x86_64       (Windows PE32+, MS x64 ABI, Kernel32 IAT)
  7. linux-riscv64        (Linux static ELF, RV64GC Linux)
  8. wasm32-wasi-p1       (WebAssembly WASI Preview 1)

Checks:
  - Compilation exit code, stdout, stderr, duration
  - Binary structural validation (Mach-O, ELF, PE32+, WASM)
  - Execution verification (Native macOS, Node.js WASI, QEMU/Wine when available)
  - Output correctness vs EXPECT comments
  - Accurate reporting: PASS, FAIL, or BLOCKED_NO_RUNNER (never faked)
"""

import sys
import os
import subprocess
import time
import hashlib
import struct
import json
import argparse
import re
import shutil

TARGETS = [
    "macos-arm64",
    "macos-arm64-libsystem",
    "linux-arm64",
    "windows-arm64",
    "linux-x86_64",
    "windows-x86_64",
    "linux-riscv64",
    "wasm32-wasi-p1",
]

def parse_expected(source_path):
    """Extract expected stdout and exit code from Vir source file comments."""
    expected_stdout = None
    expected_exit = 0

    with open(source_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    m_start = re.search(r'#\s*EXPECT_START\n((?:#[^\n]*\n)+?)#\s*EXPECT_END', content)
    if m_start:
        lines = [line[1:].lstrip() if line.startswith("#") else line for line in m_start.group(1).splitlines()]
        expected_stdout = "\n".join(lines).strip()
    else:
        m_exp = re.search(r'#\s*EXPECT:\s*\n((?:#[^\n]*\n)+)', content)
        if m_exp:
            lines = [line[1:].lstrip() if line.startswith("#") else line for line in m_exp.group(1).splitlines()]
            expected_stdout = "\n".join(lines).strip()
        else:
            m_single = re.search(r'#\s*EXPECT:\s*([^\n]+)', content)
            if m_single:
                val = m_single.group(1).strip()
                val = val.replace("\\n", "\n")
                expected_stdout = val.strip()

    m_exit = re.search(r'#\s*EXPECT_EXIT:\s*([0-9]+)', content)
    if m_exit:
        expected_exit = int(m_exit.group(1))

    return expected_stdout, expected_exit

def sha256_file(path):
    if not os.path.exists(path):
        return ""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def validate_macho_arm64(data, expect_libsystem=False):
    """Validate 64-bit Mach-O ARM64 header and load commands."""
    if len(data) < 32:
        return False, "File too small for Mach-O header (<32 bytes)"
    magic, cputype, cpusubtype, filetype, ncmds, sizeofcmds, flags, reserved = struct.unpack_from("<IIIIIIII", data, 0)
    if magic != 0xfeedfacf:
        return False, f"Invalid Mach-O 64 magic: 0x{magic:08x} (expected 0xfeedfacf)"
    if cputype != 0x0100000c: # CPU_TYPE_ARM64
        return False, f"Invalid CPU type: 0x{cputype:08x} (expected ARM64 0x0100000c)"

    # Walk load commands
    offset = 32
    has_text_seg = False
    has_libsystem = False
    has_entry = False

    for _ in range(ncmds):
        if offset + 8 > len(data):
            break
        cmd, cmdsize = struct.unpack_from("<II", data, offset)
        if cmdsize == 0 or offset + cmdsize > len(data):
            break
        if cmd == 0x19: # LC_SEGMENT_64
            segname = data[offset+8:offset+24].split(b'\x00')[0].decode('ascii', errors='ignore')
            if segname in ("__TEXT", ""):
                has_text_seg = True
        elif cmd == 0x0c: # LC_LOAD_DYLIB
            dylib_name_offset, = struct.unpack_from("<I", data, offset+8)
            name_bytes = data[offset+dylib_name_offset:offset+cmdsize].split(b'\x00')[0]
            if b"libSystem" in name_bytes:
                has_libsystem = True
        elif cmd in (0x28, 0x80000028, 0x5): # LC_MAIN, LC_MAIN_ENTRY, LC_UNIXTHREAD
            has_entry = True
        offset += cmdsize

    if not has_text_seg:
        return False, "Mach-O missing __TEXT segment"
    if expect_libsystem and not has_libsystem:
        return False, "Mach-O dynamic target missing LC_LOAD_DYLIB for libSystem"
    return True, "Valid Mach-O ARM64"

def validate_elf(data, expected_machine):
    """Validate 64-bit ELF header and program headers."""
    if len(data) < 64:
        return False, "File too small for ELF64 header (<64 bytes)"
    if data[:4] != b"\x7fELF":
        return False, f"Invalid ELF magic: {data[:4]}"
    ei_class = data[4]
    ei_data = data[5]
    if ei_class != 2: # 64-bit
        return False, f"Not 64-bit ELF: class={ei_class}"
    if ei_data != 1: # 2's complement, little endian
        return False, f"Not little-endian ELF: data={ei_data}"

    e_type, e_machine, e_version, e_entry, e_phoff, e_shoff, e_flags, e_ehsize, e_phentsize, e_phnum = \
        struct.unpack_from("<HHIQQQIHHH", data, 16)

    if expected_machine and e_machine != expected_machine:
        return False, f"ELF e_machine mismatch: 0x{e_machine:04x} (expected 0x{expected_machine:04x})"
    if e_entry == 0:
        return False, "ELF entrypoint is 0"
    if e_phnum == 0 or e_phoff == 0:
        return False, "ELF missing program headers"

    # Validate PT_LOAD
    has_pt_load = False
    for i in range(e_phnum):
        ph_offset = e_phoff + i * e_phentsize
        if ph_offset + 32 > len(data):
            break
        p_type, = struct.unpack_from("<I", data, ph_offset)
        if p_type == 1: # PT_LOAD
            has_pt_load = True
            break
    if not has_pt_load:
        return False, "ELF missing PT_LOAD segment"
    return True, f"Valid ELF64 (machine=0x{e_machine:04x}, entry=0x{e_entry:x})"

def validate_pe(data, expected_machine):
    """Validate PE32+ (64-bit PE) header and optional header."""
    if len(data) < 64:
        return False, "File too small for DOS header"
    if data[:2] != b"MZ":
        return False, "Missing DOS MZ signature"
    e_lfanew, = struct.unpack_from("<I", data, 60)
    if e_lfanew + 24 > len(data):
        return False, f"Invalid e_lfanew offset {e_lfanew}"
    if data[e_lfanew:e_lfanew+4] != b"PE\x00\x00":
        return False, "Missing PE signature"

    machine, num_sections, timedatestamp, pt_symtab, num_syms, opt_hdr_size, characteristics = \
        struct.unpack_from("<HHIIIHH", data, e_lfanew + 4)

    if expected_machine and machine != expected_machine:
        return False, f"PE Machine mismatch: 0x{machine:04x} (expected 0x{expected_machine:04x})"

    opt_offset = e_lfanew + 24
    if opt_offset + 2 > len(data):
        return False, "Missing PE Optional Header"
    opt_magic, = struct.unpack_from("<H", data, opt_offset)
    if opt_magic != 0x20b: # PE32+ (64-bit)
        return False, f"PE Optional Header magic 0x{opt_magic:04x} != 0x20b (PE32+)"

    entrypoint, = struct.unpack_from("<I", data, opt_offset + 16)
    if entrypoint == 0:
        return False, "PE AddressOfEntryPoint is 0"
    return True, f"Valid PE32+ (machine=0x{machine:04x}, sections={num_sections}, entry=0x{entrypoint:x})"

def validate_wasm(data):
    """Validate WebAssembly binary format."""
    if len(data) < 8:
        return False, "File too small for WASM module (<8 bytes)"
    if data[:4] != b"\x00asm":
        return False, f"Invalid WASM magic: {data[:4]}"
    version, = struct.unpack_from("<I", data, 4)
    if version != 1:
        return False, f"Invalid WASM version: {version} (expected 1)"

    offset = 8
    sections = []
    while offset < len(data):
        sec_id = data[offset]
        offset += 1
        # Read LEB128 size
        size = 0
        shift = 0
        while offset < len(data):
            b = data[offset]
            offset += 1
            size |= (b & 0x7f) << shift
            if (b & 0x80) == 0:
                break
            shift += 7
        sections.append(sec_id)
        offset += size

    return True, f"Valid WASM module (sections: {sections})"

def validate_artifact_structure(target, artifact_path):
    """Structural validator dispatch per target."""
    if not os.path.exists(artifact_path):
        return False, "Artifact file does not exist"
    size = os.path.getsize(artifact_path)
    if size == 0:
        return False, "Artifact file is empty (0 bytes)"
    with open(artifact_path, "rb") as f:
        data = f.read()

    if target == "macos-arm64":
        return validate_macho_arm64(data, expect_libsystem=False)
    elif target == "macos-arm64-libsystem":
        return validate_macho_arm64(data, expect_libsystem=True)
    elif target == "linux-arm64":
        return validate_elf(data, expected_machine=0xb7) # EM_AARCH64 = 183 = 0xb7
    elif target == "linux-x86_64":
        return validate_elf(data, expected_machine=0x3e) # EM_X86_64 = 62 = 0x3e
    elif target == "linux-riscv64":
        return validate_elf(data, expected_machine=0xf3) # EM_RISCV = 243 = 0xf3
    elif target == "windows-arm64":
        return validate_pe(data, expected_machine=0xaa64) # IMAGE_FILE_MACHINE_ARM64 = 0xaa64
    elif target == "windows-x86_64":
        return validate_pe(data, expected_machine=0x8664) # IMAGE_FILE_MACHINE_AMD64 = 0x8664
    elif target == "wasm32-wasi-p1":
        return validate_wasm(data)
    else:
        return False, f"Unknown target {target}"

def run_wasm_node(wasm_path):
    """Run WASI module using Node.js."""
    runner_code = """
const fs = require('fs');
const { WASI } = require('wasi');

const wasmPath = process.argv[1];
const wasi = new WASI({
  version: 'preview1',
  args: process.argv.slice(2),
  args: [wasmPath],
  env: process.env,
  preopens: { '.': '.' }
});

const wasmBuffer = fs.readFileSync(process.argv[2]);
const wasmBuffer = fs.readFileSync(wasmPath);
WebAssembly.instantiate(wasmBuffer, wasi.getImportObject())
  .then(({ instance }) => {
    try {
      const exitCode = wasi.start(instance);
      process.exit(exitCode || 0);
    } catch (e) {
      if (e && e.code) {
        process.exit(e.code);
      }
      console.error(e);
      process.exit(1);
    }
  })
  .catch(err => {
    console.error('Instantiation error:', err);
    process.exit(1);
  });
"""
    cmd = ["node", "--no-warnings", "-e", runner_code, wasm_path]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Timeout (10s)"
    except Exception as e:
        return -1, "", str(e)

def run_target(target, artifact_path, expected_stdout, expected_exit):
    """Attempt execution using available runners. Returns (status, exit_code, stdout, stderr, reason)."""
    # 1. Native execution on macOS ARM64
    if target in ("macos-arm64", "macos-arm64-libsystem"):
        try:
            os.chmod(artifact_path, 0o755)
            p = subprocess.run([artifact_path], capture_output=True, text=True, timeout=10)
            stdout = p.stdout
            code = p.returncode
            if expected_stdout is not None and stdout.strip() != expected_stdout:
                return "FAIL", code, stdout, p.stderr, f"stdout mismatch: got {stdout!r}, expected {expected_stdout!r}"
            if code != expected_exit:
                return "FAIL", code, stdout, p.stderr, f"exit code mismatch: got {code}, expected {expected_exit}"
            return "PASS", code, stdout, p.stderr, "Execution verified natively on host"
        except Exception as e:
            return "FAIL", -1, "", str(e), f"Native execution failed: {e}"

    # 2. WASI Preview 1 execution via Node.js
    if target == "wasm32-wasi-p1":
        if shutil.which("node"):
            code, stdout, stderr = run_wasm_node(artifact_path)
            if expected_stdout is not None and stdout.strip() != expected_stdout:
                return "FAIL", code, stdout, stderr, f"WASI stdout mismatch: got {stdout!r}, expected {expected_stdout!r}"
            if code != expected_exit:
                return "FAIL", code, stdout, stderr, f"WASI exit code mismatch: got {code}, expected {expected_exit}"
            return "PASS", code, stdout, stderr, "Execution verified via Node.js WASI Preview 1"
        else:
            return "BLOCKED_NO_RUNNER", 0, "", "", "Host missing Node.js for WASI P1 execution"

    # 3. Linux targets: check qemu-user or docker
    if target.startswith("linux-"):
        qemu_bin = None
        if target == "linux-arm64" and shutil.which("qemu-aarch64"):
            qemu_bin = "qemu-aarch64"
        elif target == "linux-x86_64" and shutil.which("qemu-x86_64"):
            qemu_bin = "qemu-x86_64"
        elif target == "linux-riscv64" and shutil.which("qemu-riscv64"):
            qemu_bin = "qemu-riscv64"

        if qemu_bin:
            try:
                p = subprocess.run([qemu_bin, artifact_path], capture_output=True, text=True, timeout=10)
                stdout = p.stdout
                code = p.returncode
                if expected_stdout is not None and stdout.strip() != expected_stdout:
                    return "FAIL", code, stdout, p.stderr, f"qemu stdout mismatch: got {stdout!r}, expected {expected_stdout!r}"
                if code != expected_exit:
                    return "FAIL", code, stdout, p.stderr, f"qemu exit code mismatch: got {code}, expected {expected_exit}"
                return "PASS", code, stdout, p.stderr, f"Execution verified via {qemu_bin}"
            except Exception as e:
                return "FAIL", -1, "", str(e), f"QEMU execution failed: {e}"
        else:
            return "BLOCKED_NO_RUNNER", 0, "", "", f"No host runner (qemu-{target.split('-')[1]} or Linux container) available on macOS"

    # 4. Windows targets: check wine
    if target.startswith("windows-"):
        wine_bin = shutil.which("wine64") or shutil.which("wine")
        if wine_bin and target == "windows-x86_64":
            try:
                p = subprocess.run([wine_bin, artifact_path], capture_output=True, text=True, timeout=10)
                stdout = p.stdout
                code = p.returncode
                if expected_stdout is not None and stdout.strip() != expected_stdout:
                    return "FAIL", code, stdout, p.stderr, f"wine stdout mismatch: got {stdout!r}, expected {expected_stdout!r}"
                if code != expected_exit:
                    return "FAIL", code, stdout, p.stderr, f"wine exit code mismatch: got {code}, expected {expected_exit}"
                return "PASS", code, stdout, p.stderr, "Execution verified via wine"
            except Exception as e:
                return "FAIL", -1, "", str(e), f"Wine execution failed: {e}"
        else:
            return "BLOCKED_NO_RUNNER", 0, "", "", f"No host runner (Wine or Windows VM) available for {target} on macOS"

def extract_error_summary(out, err):
    combined = (err.strip() + "\n" + out.strip()).strip()
    lines = [l.strip() for l in combined.splitlines() if l.strip()]
    for line in reversed(lines):
        if "error" in line.lower() or "fail" in line.lower() or "cannot" in line.lower() or "unknown" in line.lower():
            return line
    return lines[-1] if lines else "Compilation failed"

def main():
    parser = argparse.ArgumentParser(description="Vir Compiler 8-Target Matrix Validation Runner")
    parser.add_argument("source", nargs="?", default="tests/vri/test_add.vri", help="Vir source file to test")
    parser.add_argument("--virc", default="bin/virc", help="Path to virc compiler binary")
    parser.add_argument("--target", choices=TARGETS, help="Run single target instead of full matrix")
    parser.add_argument("--outdir", default="scratch/matrix", help="Directory for generated artifacts")
    parser.add_argument("--json", action="store_true", help="Emit full JSON output")
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    expected_stdout, expected_exit = parse_expected(args.source)

    targets_to_run = [args.target] if args.target else TARGETS
    results = {}

    print(f"=== Matrix Runner: Testing '{args.source}' with '{args.virc}' ===")
    print(f"Expected stdout: {expected_stdout!r}, expected exit: {expected_exit}\n")

    for target in targets_to_run:
        ext = ".wasm" if target == "wasm32-wasi-p1" else (".exe" if "windows" in target else "")
        artifact_path = os.path.join(args.outdir, f"out_{target}{ext}")
        if os.path.exists(artifact_path):
            os.remove(artifact_path)

        cmd = [args.virc, args.source, "--target", target, "-o", artifact_path]
        t0 = time.time()
        try:
            cp = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            duration_ms = int((time.time() - t0) * 1000)
            compile_ok = (cp.returncode == 0)
            compile_stdout = cp.stdout
            compile_stderr = cp.stderr
        except Exception as e:
            duration_ms = int((time.time() - t0) * 1000)
            compile_ok = False
            compile_stdout = ""
            compile_stderr = str(e)

        # Truncate verbose compile stdout to avoid huge reports
        short_stdout = ""
        if not compile_ok and compile_stdout:
            lines = compile_stdout.strip().splitlines()
            short_stdout = "\n".join(lines[-20:])

        result_entry = {
            "target": target,
            "compile_ok": compile_ok,
            "compile_exit": cp.returncode if compile_ok else -1,
            "compile_duration_ms": duration_ms,
            "compile_stdout": short_stdout,
            "compile_stderr": compile_stderr.strip(),
            "artifact_path": artifact_path,
            "artifact_sha256": sha256_file(artifact_path) if compile_ok else "",
            "structural_valid": False,
            "structural_msg": "",
            "run_status": "FAIL",
            "run_exit": -1,
            "run_stdout": "",
            "run_stderr": "",
            "status_reason": ""
        }

        if not compile_ok:
            err_summary = extract_error_summary(compile_stdout, compile_stderr)
            result_entry["run_status"] = "FAIL"
            result_entry["status_reason"] = f"Compilation failed: {err_summary}"
        else:
            struct_ok, struct_msg = validate_artifact_structure(target, artifact_path)
            result_entry["structural_valid"] = struct_ok
            result_entry["structural_msg"] = struct_msg

            if not struct_ok:
                result_entry["run_status"] = "FAIL"
                result_entry["status_reason"] = f"Structural validation failed: {struct_msg}"
            else:
                status, code, out, err, reason = run_target(target, artifact_path, expected_stdout, expected_exit)
                result_entry["run_status"] = status
                result_entry["run_exit"] = code
                result_entry["run_stdout"] = out
                result_entry["run_stderr"] = err
                result_entry["status_reason"] = reason

        results[target] = result_entry
        color = "\033[92m" if result_entry["run_status"] == "PASS" else ("\033[93m" if result_entry["run_status"] == "BLOCKED_NO_RUNNER" else "\033[91m")
        reset = "\033[0m"
        print(f"[{color}{result_entry['run_status']:<18}{reset}] {target:<24} {result_entry['status_reason']}")

    print("\n" + "=" * 60)
    pass_cnt = sum(1 for r in results.values() if r["run_status"] == "PASS")
    blocked_cnt = sum(1 for r in results.values() if r["run_status"] == "BLOCKED_NO_RUNNER")
    fail_cnt = sum(1 for r in results.values() if r["run_status"] == "FAIL")
    print(f"Summary: PASS={pass_cnt}, BLOCKED_NO_RUNNER={blocked_cnt}, FAIL={fail_cnt}, TOTAL={len(results)}")

    if args.json:
        print("\nJSON Output:")
        print(json.dumps(results, indent=2))

    report_path = os.path.join(args.outdir, "matrix_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"Saved JSON report to {report_path}")

    # Return exit code 0 if all runnable tests passed and others are properly blocked
    sys.exit(0 if fail_cnt == 0 else 1)

if __name__ == "__main__":
    main()
