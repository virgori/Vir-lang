# Virgori/Vir Library Design Plan (Master Blueprint v2 -> Execution)

## 1. Muc tieu va pham vi

Tai lieu nay chuyen Master Blueprint v2 thanh ke hoach thiet ke va trien khai thu vien cho workspace `AI/Vir`.

Muc tieu:
- Giu DNA hien tai cua `Vir` (multilingual frontend + Q-IR + native backend).
- Mo rong thanh stack tensor compiler-runtime native, lean, AI-driven.
- Uu tien CPU-first, capability-first, memory-discipline-first.

Pham vi tai lieu:
- Kien truc dich cho Vir AI.
- Mapping hien trang -> thu vien muc tieu.
- Backlog theo `Must / Should / Later`.
- Roadmap 5 phase + sprint de co the code ngay.
- Definition of Done (DoD) va KPI ky thuat.

## 2. Hien trang codebase Vir (baseline)

Da ton tai cac khoi:
- Frontend: `src/frontend/*`, `src/sublib/*`
- IR: `src/ir/instructions/q_ir.py`, `src/ir/instructions/ir_builder.py`, `src/ir/optimizer/optimizer.py`, `src/ir/cost_model/cost_model.py`
- Backend: `src/backend/codegen/*`, `src/backend/patcher/*`, `src/backend/monitor/*`
- Runtime: `src/runtime/lifecycle/lifecycle.py`, `src/runtime/jit/*`
- Security: `src/security/*`

Nhan xet:
- Q-IR hien tai la instruction IR cho general language VM, chua du metadata tensor/training/memory semantics.
- Da co optimizer, cost model, codegen hooks -> rat phu hop de nang cap thanh compiler spine theo Blueprint v2.

## 3. Kien truc dich cho Vir AI (module map)

### 3.1 Layer map

- VirNN (frontend model semantics)
  - Du kien: `src/virnn/`
- Q-IR Spine (QIR-H, QIR-M, QIR-L)
  - Du kien: `src/qir/`
- Execution core
  - VirMatrix: `src/virmatrix/`
  - VirGrad: `src/virgrad/`
  - VirOptim: `src/viroptim/`
  - VirCodegen: mo rong `src/backend/codegen/` hoac `src/vircodegen/`
  - VirRuntime: mo rong `src/runtime/` hoac `src/virruntime/`
- System/Data layer
  - VirData: `src/virdata/`
  - VirMem: `src/virmem/`
  - VirPass: `src/virpass/`
  - VirProf: `src/virprof/`
  - VirPlat: `src/virplat/`

### 3.2 Nguyen tac migration

- Khong rewrite toan bo. Di theo huong strangler pattern:
  1. Tao package moi song song.
  2. Bridge voi runtime hien tai.
  3. Di chuyen logic dan dan.
- Q-IR instruction cu van ton tai cho language VM; Q-IR tensor moi dung namespace rieng (`qir/`).

## 4. Backlog theo muc do uu tien

## 4.1 MUST (MVP de chay duoc that)

### A. Q-IR spine toi thieu

1. QIR-H schema
- Node identity: node_id, op_code, input_ids, output_ids, block_id, region_id
- Tensor semantics: dtype, shape, rank, stride, layout, contiguous, broadcast
- Training: requires_grad, stop_gradient, saved_for_backward
- Memory: alias_group, is_view, mutable, inplace_safe, lifetime_region, buffer_hint

2. QIR-M schema
- Canonical tensor ops (matmul, add, mul, reduce, transpose, reshape, cast, softmax primitives)
- Normalized dataflow + inferred shape/type

3. QIR-L schema
- Tile/loop/vector metadata
- Dispatch/kernels nodes

4. Verifier bat buoc
- Shape verifier
- Type verifier
- Alias verifier
- Inplace legality verifier
- Gradient legality verifier
- Backend legality verifier

5. Pass framework toi thieu
- PassManager
- Pass ordering
- Pass hooks inspect/rewrite/annotate/replace/fuse/lower

### B. Execution core toi thieu

6. VirMatrix MVP
- GEMM (naive + tiled)
- Elementwise add/mul/relu
- Reduction sum/mean
- Scalar reference backend
- 1 vector backend dau tien: NEON (arm64 macOS) hoac AVX2 (x86)

7. VirGrad MVP
- Backward graph generation cho: add/mul/matmul/relu/mean
- Gradient accumulation
- stop_gradient + saved_for_backward policy co ban

8. VirOptim MVP
- SGD
- Adam
- In-place param update

9. VirRuntime MVP
- Dispatch by capability profile (minimal)
- Kernel registry + fallback chain
- Execution plan runner

10. VirMem MVP
- Aligned allocator
- Arena allocator
- Temp buffer reuse by lifetime intervals (basic)
- Peak memory tracker

11. VirData MVP
- File reader + buffered reader
- Batch builder
- Prefetch queue co ban

12. VirNN MVP
- Tensor/Parameter/Module abstraction
- Linear, Embedding, ReLU/GELU, LayerNorm/RMSNorm, MLP
- Sequential graph composition

13. Test khong duoc thieu
- Correctness vs reference numpy-like implementation
- Gradient check
- Backend equivalence (scalar vs vector)

## 4.2 SHOULD (MVP+)

- QIR-L day du scheduling metadata
- Fusion manager (elementwise chain, bias+activation, matmul epilogue)
- CapabilityProfile + microbench startup
- Optimizer update fusion
- Memory planner nang cao (reuse tot hon)
- Transformer block template
- Python thin binding

## 4.3 LATER

- Distributed metadata
- Quantization metadata
- Sparse tensor semantics
- GPU/NPU hooks
- Production-grade packaging

## 5. Ke hoach 5 phase (thuc thi)

## Phase 1 (Week 1-2): Compiler spine foundation

Deliverables:
- Tao `src/qir/`:
  - `schema.py` (QIRHNode/QIRMNode/QIRLNode)
  - `opcodes.py` (nhom opcode tensor)
  - `module.py` (QIRGraph, blocks, regions)
- Tao `src/virpass/`:
  - `pass_manager.py`
  - `base_pass.py`
- Tao verifier co ban trong `src/qir/verify/`

Acceptance:
- Build QIR-H from toy model graph (Linear -> ReLU -> Linear)
- Shape + type infer pass chay pass
- Verifier bat loi shape/type sai

## Phase 2 (Week 3-4): VirMatrix + Runtime dispatch can ban

Deliverables:
- Tao `src/virmatrix/`:
  - `kernels/scalar/*`
  - `kernels/neon/*` (neu arm64)
  - `registry.py`
- Tao `src/virplat/`:
  - CPU/ISA probe
  - vector width, cache line, page size
- Mo rong runtime:
  - execution plan runner cho QIR-M
  - fallback chain

Acceptance:
- `matmul/add/relu/reduce_sum` chay qua dispatch
- scalar va vector backend cho ket qua dung trong tolerance

## Phase 3 (Week 5-7): Autograd + Optimizer + Memory discipline

Deliverables:
- `src/virgrad/`: backward builder + tape runtime nhe
- `src/viroptim/`: SGD, Adam, state layout
- `src/virmem/`: arena + temp pool + lifetime reuse basic

Acceptance:
- Train MLP nho end-to-end (forward/backward/update)
- Gradient check pass voi sai so chap nhan duoc
- Co thong ke peak memory tren moi step

## Phase 4 (Week 8-9): Fusion + Scheduling + QIR-L

Deliverables:
- Fusion passes trong `src/virpass/passes/`
- Lowering QIR-H -> QIR-M -> QIR-L
- Scheduling metadata: tile, vector lane, parallel split hint

Acceptance:
- Fuse duoc elementwise chains + matmul epilogue
- Runtime chon kernel family dua capability + microbench

## Phase 5 (Week 10-12): VirData + Packaging + Demo

Deliverables:
- `src/virdata/`: async prefetch, mmap loader (toi thieu)
- `src/virpack/`: C ABI + Python thin binding
- Demo script train text mini-model

Acceptance:
- Chay duoc training loop voi dataset that
- Co benchmark startup + profile snapshot
- Co tai lieu API toi thieu cho Python

## 6. Kien truc thu muc de xay ngay

```text
src/
  qir/
    opcodes.py
    schema.py
    module.py
    builder/
    infer/
    verify/
    lower/
  virpass/
    base_pass.py
    pass_manager.py
    passes/
  virplat/
    cpu_probe.py
    capability_profile.py
    microbench.py
  virmatrix/
    registry.py
    kernels/
      scalar/
      neon/
      avx2/
  virruntime/
    dispatcher.py
    execution_plan.py
  virmem/
    arena.py
    pool.py
    planner.py
  virgrad/
    grad_rules.py
    backward_builder.py
    tape_runtime.py
  viroptim/
    sgd.py
    adam.py
    state_store.py
  virnn/
    tensor.py
    parameter.py
    module.py
    layers/
  virdata/
    readers/
    pipeline/
    prefetch/
  virprof/
    timer.py
    startup_profile.py
  virpack/
    c_abi/
    python/
```

## 7. KPI ky thuat va cong cu gate

KPI must-have:
- Correctness:
  - 100% pass test cho op core (matmul/add/relu/reduce)
  - gradient check pass cho MLP
- Performance:
  - vector backend nhanh hon scalar backend tren shape muc tieu
- Memory:
  - peak memory duoc report, khong tang vo han theo step
- Compiler health:
  - verifier khong cho IR sai di qua lowering

Gate moi phase:
- Co test unit + integration
- Co benchmark mini
- Co docs cap nhat

## 8. Risk va giam thieu rui ro

1. Scope qua lon
- Giam thieu: gioi han op MVP ro rang, khong nhay vao transformer day du som.

2. QIR design churn
- Giam thieu: schema versioning ngay tu dau, migration adapters.

3. Performance regressions
- Giam thieu: benchmark gate trong CI + scalar oracle bat buoc.

4. Memory bug/alias bug
- Giam thieu: alias verifier + lifetime tests + fuzz shape.

## 9. Ke hoach tiep theo (de bat dau ngay)

Sprint tiep theo (1 tuan) de khoi dong:
1. Tao skeleton package: `qir`, `virpass`, `virplat`, `virmatrix`.
2. Implement `CapabilityProfile` toi thieu + probe macOS arm64/x86.
3. Dinh nghia QIR-H node schema + shape/type infer pass dau tien.
4. Viet 10 test dau tien cho verifier + infer.

Neu can, tai lieu tiep theo nen la `Implementation Spec v0.1` cho tung module (API signatures + invariants + test matrix).
