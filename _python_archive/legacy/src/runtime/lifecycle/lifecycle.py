"""
lifecycle.py – Runtime Life-cycle Orchestrator
================================================
Spec §5 – 4-phase execution pipeline:

  1. Authoring:  Developer writes Vir source → Frontend compiles to Q-IR.
  2. Preparation: Backend generates binary with Q_PATCH_POINT entries.
  3. Launch:     Program acquires JIT permissions from OS.
  4. Evolution:  AI Agent continuously monitors CPU, patches Assembly when idle.
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
    """Compilation result for a single program."""
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
    Orchestrator for the full Quizz-Core Engine lifecycle.

    Usage:
        runtime = VirRuntime()
        result = runtime.compile("If CPU idle, compute sum of A and B in registers.")
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
    # Phase 1 – Authoring (Compile)
    # ═══════════════════════════════════════════════════════

    def compile(self, source: str) -> CompilationResult:
        """
        Phase 1 & 2: Source → Tokens → AST → Q-IR → Optimized IR → Machine Code.
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
    # Phase 3 & 4 – Launch & Evolution
    # ═══════════════════════════════════════════════════════

    def run(self, result: CompilationResult) -> None:
        """
        Phase 3: Launch JIT.
        Phase 4: Start evolution loop.
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
        """Stop evolution loop."""
        if self._jit_engine:
            self._jit_engine.stop_evolution()
            print("[VirRuntime] Stopped.")

    # ═══════════════════════════════════════════════════════
    # Diagnostics
    # ═══════════════════════════════════════════════════════

    def status(self) -> dict:
        """Current system status."""
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
        """Print Q-IR textual representation."""
        return result.ir_dump

    def dump_tokens(self, result: CompilationResult) -> str:
        """Print token list."""
        return "\n".join(str(t) for t in result.tokens)

    def dump_variants(self, result: CompilationResult) -> str:
        """Print hex dump of all code variants."""
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
    """CLI entry point: vir <file.vri> or interactive mode."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="vir",
        description="Vir – Quizz-Core Engine: Multilingual syntax, Abstract machine core, Self-patching machine code.",
    )
    parser.add_argument("file", nargs="?", help="Input .vri file to compile")
    parser.add_argument("--no-jit", action="store_true", help="Disable JIT")
    parser.add_argument("--dump-tokens", action="store_true", help="Print tokens")
    parser.add_argument("--dump-ir", action="store_true", help="Print Q-IR")
    parser.add_argument("--dump-asm", action="store_true", help="Print machine code hex")
    parser.add_argument("--emit-sri", metavar="PATH", help="Emit .sri binary file")
    parser.add_argument("--emit-vsib", metavar="PATH", help="Emit .vsib library file")
    parser.add_argument("--emit-wasm", metavar="PATH", help="Emit .wasm (WebAssembly) file")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive mode")
    parser.add_argument("--lsp", action="store_true", help="Start LSP server")
    parser.add_argument("--dap", action="store_true", help="Start DAP debug server")

    args = parser.parse_args()

    runtime = VirRuntime(enable_jit=not args.no_jit)

    # LSP / DAP server modes
    if args.lsp:
        from src.lsp.server import main as lsp_main
        lsp_main()
        return
    if args.dap:
        from src.dap.server import main as dap_main
        dap_main()
        return

    if args.interactive or args.file is None:
        _interactive_mode(runtime, args)
    else:
        source = Path(args.file).read_text(encoding="utf-8")
        _compile_and_run(runtime, source, args)


def _interactive_mode(runtime: VirRuntime, args) -> None:
    """Interactive REPL — with readline, history, tab completion, multi-line."""
    import atexit
    import os

    # ── Readline setup (history + completion) ──────────
    try:
        import readline
        _has_readline = True
    except ImportError:
        _has_readline = False

    HISTORY_FILE = os.path.expanduser("~/.vir_history")

    if _has_readline:
        # Load history
        try:
            readline.read_history_file(HISTORY_FILE)
        except FileNotFoundError:
            pass
        readline.set_history_length(2000)
        atexit.register(lambda: readline.write_history_file(HISTORY_FILE))

        # Tab completion
        _VIR_KEYWORDS = [
            "func", "end", "if", "eif", "else", "when", "loop", "out", "skip",
            "let", "var", "const", "entity", "method", "class", "include", "import",
            "from", "export", "share", "has", "in", "get", "case", "map",
            "print", "input", "async", "task", "wait", "break", "true", "false",
            "enum", "trait", "impl", "for", "match", "extern", "module",
        ]
        _REPL_COMMANDS = [":q", ":quit", ":status", ":help", ":clear", ":dump-ir",
                          ":dump-tokens", ":reset", ":history"]

        def _completer(text, state):
            candidates = _VIR_KEYWORDS + _REPL_COMMANDS
            matches = [c for c in candidates if c.startswith(text)]
            if state < len(matches):
                return matches[state]
            return None

        readline.set_completer(_completer)
        readline.parse_and_bind("tab: complete")

    # ── Banner ─────────────────────────────────────────
    print("╔══════════════════════════════════════════════════╗")
    print("║  Vir – Quizz-Core Engine v0.5.0                 ║")
    print("║  Multilingual Syntax • Q-IR • Self-patching     ║")
    print("║  REPL: Tab completion • History • Multi-line     ║")
    print("╚══════════════════════════════════════════════════╝")
    print("Type Vir code. :help for help, :q to quit.\n")

    # ── Multi-line buffer ──────────────────────────────
    buffer: list[str] = []
    _BLOCK_OPENERS = {"func", "if", "when", "loop", "entity", "method",
                      "class", "case", "map", "enum", "trait", "impl"}

    def _is_incomplete(lines: list[str]) -> bool:
        """Check if code block is incomplete (more 'openers' than 'end')."""
        depth = 0
        for line in lines:
            first = line.strip().split()[0] if line.strip() else ""
            if first in _BLOCK_OPENERS:
                depth += 1
            elif first == "async" and "func" in line:
                depth += 1
            elif first == "end":
                depth -= 1
        return depth > 0

    while True:
        try:
            prompt = "vir> " if not buffer else "...> "
            line = input(prompt)
        except (EOFError, KeyboardInterrupt):
            if buffer:
                buffer.clear()
                print()
                continue
            break

        # ── REPL commands ──────────────────────────────
        stripped = line.strip()
        if not buffer and stripped in (":q", ":quit"):
            break

        if not buffer and stripped == ":help":
            print("  :q / :quit        Quit")
            print("  :status           Runtime status")
            print("  :clear            Clear screen")
            print("  :dump-ir          Print last compiled Q-IR")
            print("  :dump-tokens      Print last compiled tokens")
            print("  :reset            Reset runtime")
            print("  :history          Show command history")
            print("  Tab               Auto-complete keywords")
            print("  Multi-line        Auto-detect for func/if/loop...")
            continue

        if not buffer and stripped == ":status":
            import json
            print(json.dumps(runtime.status(), indent=2, ensure_ascii=False))
            continue

        if not buffer and stripped == ":clear":
            os.system("clear" if os.name != "nt" else "cls")
            continue

        if not buffer and stripped == ":dump-ir":
            print("  (use :dump-ir after compiling source)")
            continue

        if not buffer and stripped == ":dump-tokens":
            print("  (use :dump-tokens after compiling source)")
            continue

        if not buffer and stripped == ":reset":
            runtime.stop()
            print("✓ Runtime reset.")
            continue

        if not buffer and stripped == ":history":
            if _has_readline:
                n = readline.get_current_history_length()
                start = max(1, n - 20)
                for i in range(start, n + 1):
                    print(f"  {i}: {readline.get_history_item(i)}")
            else:
                print("  readline not available")
            continue

        if not stripped and not buffer:
            continue

        # ── Multi-line input ───────────────────────────
        buffer.append(line)

        if _is_incomplete(buffer):
            continue  # Wait for more input

        # ── Compile & run ──────────────────────────────
        source = "\n".join(buffer)
        buffer.clear()

        try:
            _compile_and_run(runtime, source, args)
        except Exception as e:
            print(f"⛔ Error: {e}")

    runtime.stop()
    print("Goodbye!")


def _compile_and_run(runtime: VirRuntime, source: str, args) -> None:
    """Compile and run a source snippet."""
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

    if getattr(args, "emit_wasm", None):
        from src.backend.codegen.codegen_wasm import write_wasm
        write_wasm(result.optimized_ir, args.emit_wasm)
        print(f"[Emitted .wasm → {args.emit_wasm}]")

    # Run
    runtime.run(result)
