# Legacy Python/C Files — Path Manifest
# ========================================
# Archived: 2026-03-19
# Reason: Vir is now self-hosting. The Python compiler (src/)
#         and C runtime (core/src/, core/include/) have been
#         replaced by pure Vir code in stdlib/vir/compiler/
#         and stdlib/vir/rt/.
#
# Total: 438 files (~279,000 LOC)
#   - Python (src/): 165 files, ~256,000 LOC
#   - C source (core/src/): 33 files, ~17,000 LOC
#   - C headers (core/include/): 33 files, ~6,400 LOC
#   - Build artifacts: .o files, .a/.dylib, vir binary
#   - Old scripts: 11 Python utility scripts
#   - Root test files: 2
#
# Replacement: stdlib/vir/compiler/ + stdlib/vir/rt/ (9,526 LOC pure Vir)
# Bootstrap: scripts/stage0_compile.py (still uses legacy/src/ for Stage 0)
#
# To restore: mv legacy/<path> <original_path>
# ========================================

## ═══════════════════════════════════════════════════════
## Python Compiler (src/) → legacy/src/
## Original: src/
## ═══════════════════════════════════════════════════════

### Frontend (lexer, parser, type checker)
src/frontend/__init__.py
src/frontend/type_check.py
src/frontend/vi_errors.py
src/frontend/parser/__init__.py
src/frontend/parser/parser.py
src/frontend/tokenizer/__init__.py
src/frontend/tokenizer/ngram_tokenizer.py
src/frontend/sublib/__init__.py
src/frontend/sublib/sublib_loader.py

### IR (Q-IR instructions, optimizer, register allocator)
src/ir/__init__.py
src/ir/monomorph.py
src/ir/opt_passes.py
src/ir/trait_resolve.py
src/ir/instructions/__init__.py
src/ir/instructions/ir_builder.py
src/ir/instructions/q_ir.py
src/ir/cost_model/__init__.py
src/ir/cost_model/cost_model.py
src/ir/optimizer/__init__.py
src/ir/optimizer/auto_tuner.py
src/ir/optimizer/bounds_check_elim.py
src/ir/optimizer/deterministic_free.py
src/ir/optimizer/escape_analysis.py
src/ir/optimizer/optimizer.py
src/ir/registers/__init__.py
src/ir/registers/linear_scan.py
src/ir/registers/virtual_registers.py

### Backend (codegen, GPU, WASM, Swift, monitor, patcher)
src/backend/__init__.py
src/backend/formats.py
src/backend/codegen/__init__.py
src/backend/codegen/codegen.py
src/backend/codegen/codegen_gpu.py
src/backend/codegen/codegen_wasm.py
src/backend/codegen/codegen_x86.py
src/backend/codegen/obj_emitter.py
src/backend/monitor/__init__.py
src/backend/monitor/pressure_monitor.py
src/backend/patcher/__init__.py
src/backend/patcher/binary_patcher.py
src/backend/swift/__init__.py
src/backend/swift/bridge.py
src/backend/swift/cli.py
src/backend/swift/mapping.py
src/backend/swift/transpiler.py
src/backend/swift/README.md

### Runtime (JIT engine, lifecycle, bridge)
src/runtime/__init__.py
src/runtime/bridge/__init__.py
src/runtime/bridge/bridge_api.py
src/runtime/jit/__init__.py
src/runtime/jit/jit_engine.py
src/runtime/lifecycle/__init__.py
src/runtime/lifecycle/lifecycle.py

### Viron CLI (system management)
src/viron/__init__.py
src/viron/alias_engine.py
src/viron/cli.py
src/viron/registry.py
src/viron/auth/__init__.py
src/viron/auth/identity.py
src/viron/auth/privilege.py
src/viron/commands/__init__.py
src/viron/commands/fs_cmd.py
src/viron/commands/maha.py
src/viron/commands/net.py
src/viron/commands/pkg.py
src/viron/commands/proc.py
src/viron/commands/svc.py
src/viron/commands/sys_info.py
src/viron/commands/user.py

### LSP & DAP servers
src/lsp/__init__.py
src/lsp/__main__.py
src/lsp/server.py
src/dap/__init__.py
src/dap/__main__.py
src/dap/server.py

### Package manager
src/pkg/__init__.py
src/pkg/installer.py
src/pkg/lockfile.py
src/pkg/manifest.py
src/pkg/registry.py
src/pkg/resolver.py

### SDK
src/sdk/__init__.py

### QIR (graph-based IR)
src/qir/__init__.py
src/qir/module.py
src/qir/opcodes.py
src/qir/schema.py
src/qir/builder/__init__.py
src/qir/builder/graph_builder.py
src/qir/infer/__init__.py
src/qir/infer/shape_type_infer.py
src/qir/lower/__init__.py
src/qir/lower/h_to_m.py
src/qir/lower/m_to_l.py
src/qir/verify/__init__.py
src/qir/verify/verifiers.py

### Security (code signing, validation)
src/security/__init__.py
src/security/signer/__init__.py
src/security/signer/internal_signer.py
src/security/validator/__init__.py
src/security/validator/code_validator.py

### Native FFI bindings
src/native/__init__.py
src/native/vir_native.py
src/native/lib/__init__.py
src/native/lib/libvir_core.a
src/native/lib/libvir_core.dylib

### Sub-libraries (i18n keyword adapters)
src/sublib/__init__.py
src/sublib/base.py
src/sublib/en.py
src/sublib/ja.py
src/sublib/ko.py
src/sublib/vi.py
src/sublib/zh.py
src/lib/__init__.py
src/lib/keywords.py

### ML/AI extensions
src/virdata/__init__.py
src/virdata/dataloader.py
src/virdata/dataset.py
src/virdata/transforms.py
src/virgrad/__init__.py
src/virgrad/backward_builder.py
src/virgrad/grad_rules.py
src/virgrad/tape_runtime.py
src/virmatrix/__init__.py
src/virmatrix/registry.py
src/virmatrix/kernels/__init__.py
src/virmatrix/kernels/avx2/__init__.py
src/virmatrix/kernels/neon/__init__.py
src/virmatrix/kernels/neon/ops.py
src/virmatrix/kernels/scalar/__init__.py
src/virmatrix/kernels/scalar/ops.py
src/virmem/__init__.py
src/virmem/arena.py
src/virmem/planner.py
src/virmem/pool.py
src/virnn/__init__.py
src/virnn/module.py
src/virnn/parameter.py
src/virnn/tensor.py
src/virnn/layers/__init__.py
src/virnn/layers/activations.py
src/virnn/layers/containers.py
src/virnn/layers/embedding.py
src/virnn/layers/linear.py
src/virnn/layers/normalization.py
src/viroptim/__init__.py
src/viroptim/adam.py
src/viroptim/sgd.py
src/viroptim/state_store.py

### Compiler passes & platform profiling
src/virpass/__init__.py
src/virpass/base_pass.py
src/virpass/pass_manager.py
src/virpass/passes/__init__.py
src/virpass/passes/auto_fusion.py
src/virpass/passes/builtin.py
src/virpass/passes/lowering.py
src/virplat/__init__.py
src/virplat/capability_profile.py
src/virplat/cpu_probe.py
src/virplat/microbench.py
src/virprof/__init__.py
src/virprof/startup_profile.py
src/virprof/timer.py

### FFI packaging
src/virpack/__init__.py
src/virpack/c_abi.py
src/virpack/python.py

### Runtime dispatch
src/virruntime/__init__.py
src/virruntime/dispatcher.py
src/virruntime/execution_plan.py

### Generated headers
src/generated/cost_table_arm64.h
src/generated/cost_table_rv64.h
src/generated/cost_table_x86_64.h
src/generated/opcode_dispatch.h

### Root init
src/__init__.py


## ═══════════════════════════════════════════════════════
## C Runtime & Compiler (core/) → legacy/core_src/, core_include/
## Original: core/src/, core/include/
## ═══════════════════════════════════════════════════════

### C source files (core/src/ → legacy/core_src/)
core/src/amx_accel.c            # AMX accelerator FFI
core/src/async_runtime.c        # kqueue/epoll/IOCP async I/O
core/src/atomic.c               # Atomic primitives
core/src/bridge.c               # C-JIT bridge
core/src/codegen.c              # Codegen CLI/driver
core/src/constraints.c          # Constraint solver
core/src/cpu_caps.c             # CPU capability detection
core/src/ffi_runtime.c          # Foreign function interface
core/src/gpu_cuda.c             # CUDA Driver API FFI
core/src/gpu_metal.c            # Apple Metal GPU FFI
core/src/gpu_pipeline.c         # GPU pipeline management
core/src/huge_alloc.c           # Large allocation support
core/src/intrinsics.c           # Built-in functions
core/src/ir_lower.c             # Q-IR → native lowering
core/src/jit_bridge.c           # JIT bridge
core/src/lexer.c                # Lexer (bootstrap compiler)
core/src/main.c                 # C runtime main entry
core/src/mem_manager.c          # Memory manager
core/src/micro_prober.c         # Microarchitecture profiler
core/src/net_runtime.c          # Network runtime
core/src/numa_alloc.c           # NUMA-aware allocation
core/src/parser.c               # Parser (bootstrap compiler)
core/src/patcher.c              # Binary patcher
core/src/ptx_gen.c              # Q-IR → PTX (NVIDIA GPU)
core/src/q_ir.c                 # Q-IR execution / VM
core/src/signer.c               # Code signer (HMAC-SHA256)
core/src/simd_dispatch.c        # SIMD dispatcher
core/src/simd_index.c           # SIMD indexing
core/src/slab_alloc.c           # Slab allocator
core/src/task.c                 # Task/fiber scheduler
core/src/thread_runtime.c       # Thread pool & sync
core/src/vir.c                  # Lifecycle API
core/src/vm.c                   # Q-IR interpreter VM

### C headers (core/include/ → legacy/core_include/)
core/include/amx_accel.h
core/include/async_runtime.h
core/include/atomic.h
core/include/bridge.h
core/include/codegen.h
core/include/constraints.h
core/include/cpu_caps.h
core/include/ffi_runtime.h
core/include/gpu_cuda.h
core/include/gpu_metal.h
core/include/gpu_pipeline.h
core/include/huge_alloc.h
core/include/intrinsics.h
core/include/ir_lower.h
core/include/jit_bridge.h
core/include/lexer.h
core/include/mem_manager.h
core/include/micro_prober.h
core/include/net_runtime.h
core/include/numa_alloc.h
core/include/parser.h
core/include/patcher.h
core/include/ptx_gen.h
core/include/q_ir.h
core/include/signer.h
core/include/simd_dispatch.h
core/include/simd_index.h
core/include/slab_alloc.h
core/include/task.h
core/include/thread_runtime.h
core/include/vir.h
core/include/vir_platform.h
core/include/vm.h

### Bootstrap C runtime (core/bootstrap/ → legacy/)
core/bootstrap/runtime.c        # C runtime stubs (now replaced by rt/)

### Assembly (core/asm/ → legacy/core_asm/)
core/asm/arm64/vir_arm64.S      # ARM64 assembly routines
core/asm/x86_64/vir_x86_64.S   # x86-64 assembly routines

### Build artifacts (core/build/ → legacy/core_build/)
core/build/vir                   # Compiled C-based vir binary (217KB)
core/build/*.o                   # 28 object files

### Static/dynamic libraries (core/lib/ → legacy/core_lib/)
core/lib/libvir_core.a          # Static library (354KB)
core/lib/libvir_core.dylib      # Dynamic library (269KB)

### Makefile (core/Makefile → legacy/core_Makefile)
core/Makefile                    # C build system


## ═══════════════════════════════════════════════════════
## Old Scripts → legacy/scripts/
## Original: scripts/
## ═══════════════════════════════════════════════════════

scripts/alignment_audit.py       # Binary alignment auditor
scripts/build_release.py         # Old release builder
scripts/build_stdlib.py          # Old stdlib builder
scripts/convert_phase2.py        # Phase 2 migration
scripts/convert_phase3.py        # Phase 3 migration
scripts/convert_to_english.py    # Localization converter
scripts/convert_to_v12.py        # v1.2 syntax migration
scripts/llvm_tablegen_parser.py  # LLVM TableGen parser
scripts/meta_compiler.py         # Metaprogramming/macro system
scripts/pmu_profiler.py          # PMU-based profiler
scripts/swift_build.py           # Swift build driver


## ═══════════════════════════════════════════════════════
## Root Test Files → legacy/
## ═══════════════════════════════════════════════════════

_test_fusion.py                  # Fusion test (experimental)
test_transpile.py                # Transpilation test


## ═══════════════════════════════════════════════════════
## KEPT (not archived)
## ═══════════════════════════════════════════════════════

# scripts/stage0_compile.py     — Still needed for bootstrap Stage 0
# scripts/bootstrap_selfhost.sh — New self-hosting bootstrap
# scripts/bootstrap.sh          — Original bootstrap (reference)
# core/bootstrap/*.vri          — Vir source files (not C)
# core/data/                    — Data files
# core/examples/                — Example programs
# core/tests/                   — Test suite
# tests/                        — Main test suite
# stdlib/                       — Pure Vir standard library
# pyproject.toml                — Project config (still references src/)
