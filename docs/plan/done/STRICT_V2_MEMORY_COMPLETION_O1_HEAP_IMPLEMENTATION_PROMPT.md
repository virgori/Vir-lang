# Prompt hoàn thiện 100% Vir Memory Model và O(1) Free-List Heap

## Vai trò

Bạn là AI chịu trách nhiệm hoàn thiện end-to-end memory model của compiler Vir
tự host trên codebase hiện tại. Đây là nhiệm vụ implementation, verification và
hardening; không phải chỉ audit, viết kế hoạch hoặc đổi tài liệu.

Hãy tiếp tục làm việc qua từng phase cho đến khi mọi gate trong Definition of
Done đều đạt. Nếu gặp blocker thật sự từ môi trường ngoài, ghi bằng chứng và
trạng thái `BLOCKED`; không gọi một phần implementation là “100%”.

## Mục tiêu cuối cùng

1. Ownership, move, borrow, lexical region, explicit `arena:`, implicit
   per-iteration sub-arena, escape placement/promotion, cleanup/unwind và runtime
   allocator thống nhất từ semantic analysis tới executable.
2. Owned value escape an toàn qua assignment, call và `out`; toàn bộ reachable
   owned graph sống đúng lifetime, không shallow-copy header và không dangling
   backing storage.
3. Borrow sai bị từ chối ở compile time với diagnostic ổn định; raw pointer
   không được dùng để kéo dài lifetime.
4. Mọi Arena được reset đúng một lần trên mọi cạnh normal/early/error exit, sau
   khi owned graph escape đã được bảo toàn.
5. Mọi backend được quảng cáo lower cùng semantics hoặc reject bằng diagnostic
   unsupported; cấm silent NOP.
6. General heap thay first-fit scan O(k) bằng segregated free-list kiểu TLSF:
   allocation/free/coalescing metadata có worst-case O(1), độc lập với số block
   trống.
7. `free`/`vir_free` trong generated native code gọi đường giải phóng thật;
   không còn bị map thành `LIR_RT_NOP`.
8. Self-host fixed point, full regression, memory contract, allocator contract,
   optimization matrix và target matrix đều đạt gate.

## Nguồn sự thật và phạm vi được phép sửa

Trước khi thay đổi code, đọc đầy đủ:

- `docs/MEMORY_MANAGEMENT.md`
- `docs/VIR_EXECUTION_MODEL.md`
- `docs/plan/STRICT_V2_MEMORY_OWNERSHIP_ARENA_IMPLEMENTATION_PROMPT.md`
- `docs/plan/STRICT_V2_ARENA_SIMD_MULTI_TARGET_IMPLEMENTATION_PROMPT.md`
- `docs/ai-spec/vir-lang/references/types.md`
- `docs/ai-spec/vir-lang/references/functions.md`
- `docs/ai-spec/vir-lang/references/control-flow.md`
- `docs/ai-spec/vir-lang/references/errors.md`
- `stdlib/vir/rt/alloc.vri`
- `stdlib/vir/mem/alloc.vri`
- `stdlib/vir/mem/arena.vri`
- `stdlib/vir/compiler/sem_pass8_borrow.vri`
- `stdlib/vir/compiler/ast_to_mir.vri`
- `stdlib/vir/compiler/mir.vri`
- `stdlib/vir/compiler/mir_opt.vri`
- `stdlib/vir/compiler/lir.vri`
- mọi backend direct, MC, assembly và Wasm đang active
- `tests/memory_contract/**`
- `tools/gap_contract_runner.py`
- `run_tests.sh`

Không sửa các file language specification sau trừ khi owner yêu cầu riêng:

- `docs/ai-spec/vir-lang/**`
- `docs/vir_language_spec_v2.0_vi.md`
- `docs/vir_language_spec_v2.0_en.md`

Nếu implementation và spec khác nhau, sửa implementation trong task này và ghi
gap/evidence vào báo cáo. Không âm thầm đổi semantics.

`stdlib/vir/compiler/virc.vri` chứa source đã expand. Xác định quy trình canonical
để generate/pre-expand nó; sửa source module trước rồi regenerate bằng tool của
repo. Không duy trì hai bản logic allocator/compiler bằng copy-paste thủ công.

## Baseline bắt buộc phải reproduce

Các nhận định dưới đây là baseline cần kiểm lại trên working tree hiện tại, không
được tin mù quáng:

1. Memory contract hiện có 36 case và từng PASS 36/36 trên `macos-arm64`.
2. Positive escape fixtures hiện chưa ép tái sử dụng vùng vừa reset.
3. Probe sau phải fail trên compiler cũ: move `[1, 2, 3]` ra khỏi `arena:`, thoát
   block, allocate `[7, 8, 9]` trong Arena kế tiếp, rồi giá trị escaped phải vẫn
   là `2, 3`; compiler cũ từng đọc thành `8, 9`.
4. `pass8_check_arena_escape_assign` hiện là no-op đối với owned escape.
5. Pass mang tên `mir_opt_escape_analysis_and_arena_promotion` hiện chủ yếu đánh
   dấu non-escaping allocation cho Arena fast path, chưa promote graph.
6. `out`/`throw` chưa restore toàn bộ active Arena trên live exit edge.
7. `when`, `loop`, `for` chưa có implicit per-iteration mark/reset trong active
   AST-to-MIR lowering.
8. `arena(capacity: N)` được parse nhưng capacity chưa được enforce trong
   compiler-managed lexical Arena.
9. ARM64 và x86-64 có xử lý `MIR_INTR_ARENA`; RISC-V/Wasm chưa có parity đầy đủ.
10. `stdlib/vir/rt/alloc.vri` dùng singly linked first-fit free list O(k), chỉ
    coalesce một trường hợp đặc biệt và có lỗi accounting khi trừ merged size.
11. Native LIR codegen hiện có thể map `free`, `vir_free`, `dealloc` thành
    `LIR_RT_NOP`.
12. `rt_page_size()` dùng target constants; page rounding chưa harden đầy đủ cho
    zero, negative và overflow.

Ghi commit hash, compiler binary hash/version, target, command và output baseline
trước khi sửa. Đọc `git status`; không overwrite, restore, stage hoặc format các
thay đổi không liên quan có sẵn.

## Luật tuyệt đối chống “pass giả”

- Không sửa expected output, manifest hoặc spec để hợp thức hóa bug.
- Không đổi compile-fail thành runtime-fail.
- Không giữ toàn bộ child Arena sống để né promotion.
- Không promote mọi allocation lên global heap.
- Không shallow-copy string/array/dict/entity/enum header.
- Không bỏ reset/drop hoặc làm `free` thành NOP để tránh crash.
- Không dùng leak có chủ ý như một implementation lifetime.
- Không gọi một linked-list scan là O(1) vì benchmark nhỏ.
- Không giới hạn số block trong bin rồi silently fail hoặc scan fallback.
- Không dùng benchmark trung bình để chứng minh worst-case complexity.
- Không để backend unsupported bỏ qua operation rồi vẫn sinh artifact.
- Không chạy test bằng `bin/virc` cũ hơn source vừa build.
- Không chỉ kiểm artifact tồn tại; phải chạy artifact hoặc có structural proof.
- Không tuyên bố allocator thread-safe nếu chưa có synchronization và stress
  test thực.

## Kiến trúc bắt buộc cho O(1) free-list heap

Thay single first-fit list bằng two-level segregated fit kiểu TLSF hoặc một thiết
kế tương đương có proof worst-case O(1). Không dùng linear/best-fit scan.

### Định nghĩa complexity

- `heap_alloc`: O(1) metadata trong fixed-width word-RAM model, không tính page
  mapping syscall khi heap phải grow.
- `heap_free`: O(1) metadata, gồm remove, coalesce cả hai phía và insert.
- `heap_realloc`: O(1) metadata; nếu buộc chuyển block thì copy payload là O(n)
  theo số byte và phải được ghi riêng, không quảng cáo toàn bộ realloc là O(1).
- Số phép toán lookup không phụ thuộc số block trống, số allocation lịch sử hay
  fragmentation state.
- `clz`/`ctz`/bit-scan hoặc fallback bị chặn bởi độ rộng word cố định là hợp lệ;
  loop qua free blocks hoặc loop theo số bin động là không hợp lệ.

### Cấu trúc dữ liệu tối thiểu

Heap phải có:

- first-level bitmap;
- second-level bitmap cho từng first-level class;
- head array cho `(FL, SL)` bins;
- mapping function `size -> (fl, sl)` với rounding/search semantics rõ ràng;
- intrusive doubly linked list trong payload của free block để remove O(1);
- physical-neighbor metadata: `sizeAndFlags` và `prevPhysicalSize`, hoặc boundary
  tag tương đương;
- allocated/free, previous-free và large/direct-map flags;
- prologue/epilogue sentinel cho từng mapped segment;
- segment/mapping extent đủ để unmap và validate operation hợp lệ;
- exact counters cho mapped, allocated, free và peak bytes.

Không bắt buộc giữ header 16 byte nếu contract mới cần metadata lớn hơn. Nếu đổi
layout, cập nhật toàn bộ ABI nội bộ, bootstrap path, generated runtime và test;
không đọc block cũ bằng layout mới.

Chọn số FL/SL cố định cho miền size 64-bit được support, ví dụ số SL là power of
two. Ghi rõ:

- minimum block size;
- alignment chuẩn và over-aligned policy;
- cách map exact size, rounded size và search-next-nonempty-bin;
- overflow checks trước mọi add/align/multiply;
- split threshold;
- invariant footer/`prevPhysicalSize` sau split, merge và realloc;
- behavior của size 0, OOM và request quá lớn.

### Allocation O(1)

`heap_alloc` phải:

1. validate size và alignment, kiểm overflow;
2. normalize requested size;
3. map size sang `(fl, sl)`;
4. dùng bitmaps để tìm bin phù hợp hiện tại hoặc bin lớn hơn bằng bounded
   bit-scan;
5. remove một block trực tiếp từ bin O(1);
6. split nếu remainder đủ lớn, cập nhật neighbor metadata và insert remainder
   O(1);
7. nếu không có bin, map thêm segment hoặc direct-map large allocation rồi thực
   hiện số bước metadata bị chặn;
8. trả pointer đúng alignment hoặc failure contract xác định.

Không scan block trong một bin để tìm fit. Mapping/rounding phải bảo đảm mọi
block trong bin được chọn đủ lớn, hoặc dùng TLSF search mapping chuẩn để chuyển
sang bin kế tiếp.

### Free và coalescing O(1)

`heap_free` phải:

1. xử lý null theo public contract;
2. lấy block header và segment metadata hợp lệ;
3. phát hiện double-free/corrupt flags trong debug/hardened path;
4. tìm previous/next physical block trực tiếp bằng header metadata;
5. nếu neighbor free, unlink neighbor khỏi đúng bin qua `prevFree/nextFree` O(1);
6. merge cả trái và phải, cập nhật size, flags, next block `prevPhysicalSize`;
7. insert merged block vào đúng bin O(1);
8. cập nhật accounting chỉ theo bytes vừa chuyển từ allocated sang free, không
   trừ lại bytes của neighbor vốn đã free;
9. unmap whole empty segment theo policy xác định mà không scan toàn heap.

Mọi invariant phải được kiểm bằng heap verifier chạy được trong test/debug mode.

### Realloc

- `realloc(null, n)` tương đương alloc theo contract.
- `realloc(p, 0)` có behavior rõ ràng và được test.
- Shrink phải split tail khi hợp lý và insert/coalesce tail đúng invariant.
- Grow thử merge next physical free block O(1) trước.
- Nếu không grow tại chỗ được, allocate-copy-free; khi allocation mới fail,
  block cũ phải còn nguyên.
- Copy đúng số byte `min(oldPayload, newSize)`, kể cả tail không chia hết word.
- Self-overlap và integer overflow phải được xử lý xác định.

### Large allocation và multi-segment

- Request trên threshold xác định dùng direct mapping hoặc bin policy có proof.
- Header phải lưu mapping extent/segment owner cần thiết cho free/realloc.
- Heap growth không được làm mất danh sách segment hoặc khiến destroy/stats sai.
- Không dùng scan qua mọi segment trên hot path alloc/free.
- Segment hoàn toàn free có thể cache hoặc unmap; policy phải deterministic và
  counters phải đúng.

### Thread safety và reentrancy

- Nếu API/runtime được quảng cáo thread-safe, implement synchronization thật:
  global lock correctness trước, hoặc per-heap/per-bin lock với lock-order rõ.
- Lock/atomic primitive phải có lowering đúng cho target được support.
- Không allocate, log hoặc gọi code có thể re-enter cùng allocator khi đang giữ
  allocator lock.
- Test concurrent alloc/free/realloc, contention, ABA/corruption và accounting.
- Nếu một target chưa có atomic/lock support, target phải reject thread-safe heap
  mode rõ ràng; không quảng cáo complete.

## Phase 0 — Baseline, runner và failure-preserving tests

1. Reproduce toàn bộ baseline bên trên.
2. Thêm fixture escape-reuse thực sự fail trên compiler cũ.
3. Thêm structural tests cho Arena mark/reset trên mọi exit edge.
4. Thêm test chứng minh `free` không còn là NOP: allocate/free/reuse, bounded RSS
   và structural runtime-call check.
5. Tạo allocator contract runner/manifest hoặc mở rộng runner hiện có với
   positive, negative, structural, stress và complexity cases.
6. Mọi test mới phải nối vào `run_tests.sh` release gate.

Gate: test mới fail đúng root cause trên baseline; không có false positive do
stdout đơn giản, địa chỉ ngẫu nhiên hoặc artifact cũ.

## Phase 1 — Owner, region, provenance và memory-effect IR

- Tạo stable owner ID, allocation ID, region ID, parent relation, epoch,
  provenance, size/alignment và source origin.
- Không dùng tên binding làm identity chính; xử lý shadowing, projection, SSA
  version, call, capture, phi/merge và loop-carried state.
- Chuẩn hóa MIR operation riêng cho Arena mark, alloc, reset, promotion và drop;
  không dùng một intrinsic mơ hồ cho nhiều semantics.
- Arena reset/drop là hard memory+lifetime barrier.
- Thêm deterministic MIR/LIR dump và verifier trước optimizer, sau optimizer và
  trước backend.

Gate: malformed/missing/double cleanup, wrong-region promotion, live borrow qua
reset và unknown Arena op bị reject trước emission.

## Phase 2 — Borrow checker path-sensitive

- Hoàn thiện Copy/Move cho mọi type và call mode, không chỉ array special-case.
- Dataflow qua branch/loop/phi; end borrow tại real last use khi chứng minh được.
- Reject move/mutate/reset/drop khi borrow xung đột còn live.
- Reject borrowed return/store/capture và borrow qua suspension không đủ
  lifetime.
- Raw pointer conversion không xóa provenance hoặc hợp thức hóa dangling access.
- Diagnostic có primary span, owner/borrow origin và lifetime boundary.

Gate: toàn bộ negative ownership/borrow fail ở semantic hoặc verifier layer,
non-zero và không sinh artifact.

## Phase 3 — Escape placement và complete owned-graph promotion

- Phân loại `NoEscape`, `ScopeEscape`, `GlobalEscape` theo contract hiện có.
- Ưu tiên direct placement vào nearest sufficient ancestor region.
- Khi phải promote, traverse/copy toàn bộ reachable owned graph đúng một lần,
  cập nhật alias hợp lệ, xử lý nested graph và cycle theo ownership contract.
- Invalidate source owner sau move.
- Không retain toàn child Arena vì một escaped node.
- Không reset child trước khi graph đã được secure.
- Implement assignment escape, argument move, return `out`, nested function và
  task/activation-frame boundary applicable.

Gate: escape-reuse và deep-graph-reuse pass cho string, array, dict, entity,
payload enum và graph kết hợp; mutation proof phá promotion phải fail.

## Phase 4 — Cleanup/unwind và implicit loop Arena

- Xây cleanup stack/CFG representation chung thay vì ad-hoc global mark stack.
- Emit exactly-once reset/drop cho fallthrough, `break`, `skip`, `out`, `throw`,
  `revert`, `ensure`, retry/resume, cancellation và mọi unwind edge được support.
- Giữ thứ tự body → throw → revert → ensure → function exit.
- Thêm implicit sub-arena cho từng iteration của `when ... loop` theo contract;
  xác định tương tự cho loop forms khác bằng spec, không tự phát minh.
- `arena(capacity: N)` phải tạo/enforce bounded child region hoặc compile-time
  reject nếu target chưa support; cấm bỏ qua N.
- Resource cleanup không được thay bằng Arena reset.

Gate: structural MIR plus runtime watermark/RSS tests chứng minh cleanup; loop
dài không escape có bounded memory; early exit không leak/double-reset.

## Phase 5 — O(1) TLSF-style heap và allocator hardening

- Thay implementation first-fit trong canonical runtime source.
- Viết mapping/bitmap/bin helpers cohesive, tên Vir idiomatic, không copy logic
  giữa source và expanded compiler bundle.
- Implement split, bidirectional coalesce, realloc, large mapping, multi-segment,
  accounting, OOM và overflow theo kiến trúc bắt buộc ở trên.
- Nối `free`/`vir_free`/`dealloc` tới runtime free thật ở ARM64, x86-64, RISC-V,
  Wasm và mọi active execution path; xóa silent NOP mapping.
- Phân biệt lexical Arena allocation với general heap allocation. Không cho
  `free` individual pointer của Arena nếu contract không cho phép.
- Thêm heap verifier: bitmap↔bin consistency, no allocated block in bin, no free
  block missing from bin, link symmetry, size/alignment, neighbor tags,
  non-overlap, segment bounds và exact counters.

Gate functional:

- exact-size, near-class-boundary và maximum-size allocations;
- randomized allocate/free/realloc với deterministic seed;
- fragmentation/coalescing trái, phải và cả hai phía;
- split/merge lặp lại;
- multi-segment và large direct-map;
- realloc shrink/grow/move/failure preservation;
- zero/negative/overflow/alignment/OOM;
- double-free/corruption behavior trong hardened mode;
- concurrent stress nếu thread-safe được quảng cáo.

Gate complexity:

- instrument số node/bin inspected trên mỗi alloc/free;
- tạo adversarial heap với ít nhất hàng trăm nghìn free blocks;
- chứng minh lookup/remove/insert/coalesce count bị chặn bởi một hằng số không
  tăng theo số block;
- test fail nếu tái đưa linear scan vào allocator;
- benchmark latency p50/p95/p99 và throughput trước/sau, nhưng benchmark chỉ là
  evidence performance, không thay complexity proof.

## Phase 6 — Backend parity và runtime paths

Audit riêng:

- direct executable;
- LIR → native machine code;
- LIR/MC → assembly/object;
- interpreter/JIT nếu active;
- macOS ARM64;
- Linux ARM64;
- Linux x86-64;
- Linux RISC-V64;
- Wasm/WASI;
- Windows targets nếu vẫn được quảng cáo.

Mỗi memory operation phải được lower thật hoặc trả diagnostic gồm target, stage
và operation. Test matrix phải phân biệt compile-verified,
artifact-structural-verified, runtime-verified và expected-unsupported.

Gate: không target/path nào silently NOP Arena reset, promotion, drop, heap free
hoặc synchronization primitive.

## Phase 7 — Optimizer equivalence và barriers

- Chạy memory/allocator contracts ở mọi optimization level thực sự được support.
- Nếu CLI chưa expose O0/O1/O2/O3, thêm test hook/flag canonical; không giả lập
  bằng cách chạy cùng một pipeline bốn lần.
- Preserve region/provenance metadata qua SSA, inlining, SROA, DCE, GVN, LICM,
  PRE, vectorization và ARC trial passes.
- Unknown calls, raw pointer effects, allocator grow, reset/drop/free và locks là
  conservative clobber/barrier cho tới khi có effect proof.
- Cấm DCE `free`, reset hoặc cleanup observable.

Gate: exact behavior, diagnostics, watermark, heap invariants và artifact
structure giống nhau ở mọi optimization level.

## Phase 8 — Self-host, bootstrap và release evidence

- Build compiler từ canonical modules, regenerate expanded source đúng tool.
- Stage 1 → Stage 2 → Stage 3; áp dụng fixed-point gate của project cho binary
  hoặc normalized artifact.
- Chạy full `run_tests.sh`, memory contracts, allocator contracts, mutation
  tests, target matrix, concurrency stress và long-running RSS tests.
- Kiểm compiler itself dưới workload lớn vì compiler dùng `vir_alloc` rộng rãi.
- Update `docs/MEMORY_MANAGEMENT.md` theo evidence sau implementation; không cập
  nhật trước để tuyên bố sớm.

Gate: compiler không crash/corrupt heap; Stage 2/3 đạt fixed point; không còn
known memory contract fail hoặc allocator invariant violation.

## Test bắt buộc chi tiết

### Ownership và promotion

- Copy, Move, reassignment after move, double move, branch move merge.
- Escape qua assignment/call/`out` từ 1, 2, 8+ Arena levels.
- Reuse child storage ngay sau reset trước khi đọc escaped graph.
- Shared subgraph chỉ khi ownership contract cho phép.
- Projection move, field/container ownership và payload enum.
- Recursive call, capture và async/task boundary nếu feature active.

### Cleanup

- fallthrough, `break`, `skip`, `out`, `throw`, nested `revert`, `ensure`.
- callee throw xuyên nhiều caller/Arena.
- retry/resume/cancel paths applicable.
- exactly-once reset/drop; no missing or duplicate cleanup.
- implicit loop Arena bounded RSS và structural reset on backedge/exit.

### Heap correctness

- every FL/SL boundary ± alignment;
- empty bitmap, one bin, multiple bins và top size class;
- remove head/middle/tail trong intrusive list;
- coalesce none/left/right/both;
- segment prologue/epilogue boundaries;
- accounting after arbitrary interleavings;
- payload isolation, alignment và preservation through realloc;
- failure injection cho page mapping;
- no stale bin bit after last removal; no missing bit after first insertion.

### Complexity/mutation proof

- counter cho number of inspected free nodes phải có fixed maximum.
- thêm 10, 1,000, 100,000 free blocks không làm counter tăng.
- thay bitmap lookup bằng list scan phải làm complexity test fail.
- bỏ `prevFree`, neighbor tag, reset edge, promotion edge hoặc real free lowering
  phải làm ít nhất một targeted test fail.

## Kỷ luật implementation và commit

- Dùng Vir syntax thật: `func`, `out`, `eif`, `when ... loop`, `skip`, `end` và
  `end.` đúng context; không viết Rust/C/Go syntax trong `.vri`.
- Code mới dùng tên type PascalCase, function/local camelCase, parenthesized
  parameters/calls; signature lớn dùng `in`/`ref`/`out` sections hợp lý.
- Không rename public ABI ngoài scope nếu chưa audit callers/exports/FFI.
- Mỗi phase hoàn chỉnh có commit riêng:
  `compiler: complete memory phase N <short-name>`.
- Commit body ghi exact tests, target, mutation proof, benchmark/complexity
  counters và known unsupported boundaries.
- Chỉ stage file thuộc phase; không amend/squash để che regression.
- Không push/tag/release nếu owner chưa yêu cầu.

## Báo cáo bắt buộc sau mỗi phase

Ghi:

1. root cause đã chứng minh;
2. file/function/invariant thay đổi;
3. before/after failing test;
4. exact commands và kết quả;
5. mutation proof;
6. target/optimization coverage;
7. complexity counter và benchmark nếu phase allocator;
8. commit hash;
9. remaining gaps, không dùng từ “complete” nếu gate chưa đạt.

## Definition of Done — chỉ lúc này mới được nói 100%

Tất cả điều kiện sau phải đồng thời đúng:

- Escape-reuse và deep owned-graph tests pass; không dangling sau child reset.
- Borrow/move/lifetime negative tests fail đúng tầng, đúng diagnostic, no
  artifact.
- Mọi CFG exit cleanup đúng một lần và đúng lexical/unwind order.
- Implicit per-iteration Arena thực sự reclaim memory; `arena(capacity:)` được
  enforce.
- Arena/promotion/reset/drop/free có structural IR evidence và verifier.
- Heap allocation/free/coalescing metadata có worst-case O(1) proof bằng thiết
  kế bitmap + instrumentation; không scan theo số free blocks.
- General heap coalesce hai phía, accounting chính xác, multi-segment và realloc
  đúng contract.
- Generated `free` không còn là NOP và runtime test chứng minh storage reuse.
- Thread-safety claim có implementation + stress proof, hoặc target/mode chưa
  support bị reject rõ và không quảng cáo complete.
- O0/O1/O2/O3 có observable memory behavior tương đương.
- Mọi advertised backend/path lower đầy đủ hoặc expected-unsupported rõ ràng;
  không silent fallback.
- Stage 2/3 fixed point đạt, full regression sạch, compiler workload lớn không
  corrupt allocator.
- `docs/MEMORY_MANAGEMENT.md` được cập nhật bằng evidence thật và không còn mục
  “not yet accurate” nào thuộc phạm vi task.
- Báo cáo cuối có commit hash từng phase, test matrix, complexity counters,
  performance/RSS before-after và mọi intentionally unsafe raw/FFI boundary.

Nếu còn bất kỳ mục nào chưa đạt, kết luận phải là `PARTIAL` hoặc `BLOCKED`, tuyệt
đối không phải `100% COMPLETE`.
