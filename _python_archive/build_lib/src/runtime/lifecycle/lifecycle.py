"""
lifecycle.py – Runtime Life-cycle Orchestrator
================================================
Spec §5 – Quy trình thực thi 4 giai đoạn:

  1. Soạn thảo:  Coder viết Tiếng Việt → Frontend dịch sang Q-IR.
  2. Chuẩn bị:   Backend tạo file nhị phân với các điểm Q_PATCH_POINT.
  3. Khởi chạy:  Chương trình xin quyền JIT từ OS.
  4. Tiến hóa:   AI Agent liên tục kiểm tra chip, vá Assembly khi rảnh.
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from typing import Optional

from src.frontend.tokenizer.ngram_tokenizer import NGramTokenizer, Token
from src.frontend.parser.parser import Parser, ProgramNode
from src.sublib.base import SubLibRegistry
from src.ir.instructions.ir_builder import IRBuilder
from src.ir.instructions.q_ir import QModule
from src.ir.optimizer.optimizer import IROptimizer
from src.backend.codegen.codegen import CodeGenerator, CodeVariant, TargetArch
from src.backend.monitor.pressure_monitor import RegisterPressureMonitor
from src.runtime.jit.jit_engine import JITEngine
from src.security.signer.internal_signer import InternalSigner


@dataclass
class CompilationResult:
    """Kết quả biên dịch 1 chương trình."""
    source: str
    tokens: list[Token]
    ast: ProgramNode
    ir_module: QModule
    optimized_ir: QModule
    variants: list[CodeVariant]
    ir_dump: str
    compile_time_ms: float


class VirRuntime:
    """
    Bộ điều phối toàn bộ lifecycle của Quizz-Core Engine.

    Sử dụng:
        runtime = VirRuntime()
        result = runtime.compile("Nếu máy rảnh, tính tổng A và B bằng thanh ghi.")
        runtime.run(result)
    """

    def __init__(
        self,
        lang: str = "vi",
        arch: TargetArch = TargetArch.X86_64,
        enable_jit: bool = True,
    ) -> None:
        # Frontend
        self._adapter = SubLibRegistry.get(lang)
        self._tokenizer = NGramTokenizer(self._adapter)

        # IR
        self._optimizer = IROptimizer()

        # Backend
        self._arch = arch
        self._codegen = CodeGenerator(arch=arch)

        # Runtime
        self._jit_engine = JITEngine(arch=arch) if enable_jit else None
        self._monitor = RegisterPressureMonitor()

        # Security
        self._signer = InternalSigner()

    # ═══════════════════════════════════════════════════════
    # Phase 1 – Soạn thảo (Compile)
    # ═══════════════════════════════════════════════════════

    def compile(self, source: str) -> CompilationResult:
        """
        Giai đoạn 1 & 2: Source → Tokens → AST → Q-IR → Optimized IR → Machine Code.
        """
        t0 = time.perf_counter()

        # 1a. Tokenize
        tokens = self._tokenizer.tokenize(source)

        # 1b. Parse
        parser = Parser(tokens)
        ast = parser.parse()

        # 1c. Lower to Q-IR
        builder = IRBuilder()
        ir_module = builder.build(ast)

        # 1d. Optimize
        optimized = self._optimizer.optimize(ir_module)
        ir_dump = optimized.dump()

        # 2. Code generation (multi-version)
        variants = self._codegen.generate(optimized)

        compile_time = (time.perf_counter() - t0) * 1000

        return CompilationResult(
            source=source,
            tokens=tokens,
            ast=ast,
            ir_module=ir_module,
            optimized_ir=optimized,
            variants=variants,
            ir_dump=ir_dump,
            compile_time_ms=compile_time,
        )

    # ═══════════════════════════════════════════════════════
    # Phase 3 & 4 – Khởi chạy & Tiến hóa
    # ═══════════════════════════════════════════════════════

    def run(self, result: CompilationResult) -> None:
        """
        Giai đoạn 3: Khởi chạy JIT.
        Giai đoạn 4: Bắt đầu evolution loop.
        """
        if not self._jit_engine:
            print("[VirRuntime] JIT disabled – skipping runtime.")
            return

        if not result.variants:
            print("[VirRuntime] No code variants to execute.")
            return

        # Phase 3
        print("[VirRuntime] Phase 3: Initializing JIT region…")
        self._jit_engine.initialize(result.variants)

        # Phase 4
        print("[VirRuntime] Phase 4: Starting evolution loop…")
        self._jit_engine.start_evolution()

    def stop(self) -> None:
        """Dừng evolution loop."""
        if self._jit_engine:
            self._jit_engine.stop_evolution()
            print("[VirRuntime] Stopped.")

    # ═══════════════════════════════════════════════════════
    # Diagnostics
    # ═══════════════════════════════════════════════════════

    def status(self) -> dict:
        """Trạng thái hệ thống hiện tại."""
        cpu = self._monitor.probe()
        modes = self._jit_engine.get_current_modes() if self._jit_engine else {}
        return {
            "arch": self._arch.value,
            "cpu_arch": cpu.arch,
            "cpu_load": cpu.cpu_load_percent,
            "estimated_free_regs": cpu.estimated_free,
            "execution_mode": cpu.mode.name,
            "patch_modes": modes,
            "jit_running": self._jit_engine.is_running if self._jit_engine else False,
        }

    def dump_ir(self, result: CompilationResult) -> str:
        """In Q-IR textual."""
        return result.ir_dump

    def dump_tokens(self, result: CompilationResult) -> str:
        """In danh sách tokens."""
        return "\n".join(str(t) for t in result.tokens)

    def dump_variants(self, result: CompilationResult) -> str:
        """In hex dump của tất cả code variants."""
        lines: list[str] = []
        for v in result.variants:
            lines.append(f"[{v.patch_id}]")
            lines.append(f"  Safe: {v.safe_code.hex_dump()}")
            lines.append(f"  Fast: {v.fast_code.hex_dump()}")
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════
# CLI Entry Point
# ═══════════════════════════════════════════════════════════

def main() -> None:
    """CLI entry point: vir <file.vri> hoặc interactive mode."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="vir",
        description="Vir – Quizz-Core Engine: Cú pháp Tiếng Việt, Lõi máy trừu tượng, Tự vá mã máy.",
    )
    parser.add_argument("file", nargs="?", help="File .vri để biên dịch")
    parser.add_argument("--no-jit", action="store_true", help="Tắt JIT")
    parser.add_argument("--dump-tokens", action="store_true", help="In tokens")
    parser.add_argument("--dump-ir", action="store_true", help="In Q-IR")
    parser.add_argument("--dump-asm", action="store_true", help="In machine code hex")
    parser.add_argument("--emit-sri", metavar="PATH", help="Xuất file .sri (binary)")
    parser.add_argument("--emit-vsib", metavar="PATH", help="Xuất file .vsib (library)")
    parser.add_argument("--interactive", "-i", action="store_true", help="Chế độ tương tác")

    args = parser.parse_args()

    runtime = VirRuntime(enable_jit=not args.no_jit)

    if args.interactive or args.file is None:
        _interactive_mode(runtime, args)
    else:
        source = Path(args.file).read_text(encoding="utf-8")
        _compile_and_run(runtime, source, args)


def _interactive_mode(runtime: VirRuntime, args) -> None:
    """REPL tương tác."""
    print("╔══════════════════════════════════════════════╗")
    print("║  Vir – Quizz-Core Engine v0.1.0             ║")
    print("║  Cú pháp Tiếng Việt • Q-IR • Tự vá mã máy  ║")
    print("╚══════════════════════════════════════════════╝")
    print("Gõ lệnh tiếng Việt. ':q' để thoát, ':status' để xem trạng thái.\n")

    while True:
        try:
            line = input("vir> ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not line:
            continue
        if line == ":q":
            break
        if line == ":status":
            import json
            print(json.dumps(runtime.status(), indent=2, ensure_ascii=False))
            continue

        _compile_and_run(runtime, line, args)

    runtime.stop()
    print("Tạm biệt!")


def _compile_and_run(runtime: VirRuntime, source: str, args) -> None:
    """Biên dịch và chạy 1 đoạn source."""
    result = runtime.compile(source)

    print(f"[Compiled in {result.compile_time_ms:.2f}ms]")

    if args.dump_tokens:
        print("\n── Tokens ──")
        print(runtime.dump_tokens(result))

    if args.dump_ir:
        print("\n── Q-IR ──")
        print(runtime.dump_ir(result))

    if args.dump_asm:
        print("\n── Machine Code ──")
        print(runtime.dump_variants(result))

    if getattr(args, "emit_sri", None):
        from src.backend.codegen.obj_emitter import compile_module_to_sri
        compile_module_to_sri(result.module, args.emit_sri)
        print(f"[Emitted .sri → {args.emit_sri}]")

    # Run
    runtime.run(result)
