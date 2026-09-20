# Prompt triển khai 100% Memory Ownership, Borrow và Arena Escape

## Vai trò và mục tiêu

Bạn là AI chịu trách nhiệm hoàn thiện end-to-end bộ quản lý bộ nhớ của compiler
Vir tự host. Hãy triển khai đầy đủ, không làm demo, không để NOP, không chỉ sửa
frontend và không dùng workaround runtime để che thiếu sót của compiler.

Mục tiêu cuối cùng:

1. Ownership, move, borrow, lexical arena, explicit `arena:`, escape analysis,
   region placement/promotion, drop/reset và allocator runtime hoạt động thống
   nhất từ parser đến mọi backend được quảng cáo.
2. Owned value được phép escape khỏi `if`/`when`/`loop`/`for`/`arena:` bằng move,
   assignment sang owner sống lâu hơn hoặc `out`; compiler tự chọn/promote sang
   vùng nhớ đủ lifetime. Không thêm keyword `escape`.
3. Borrow sai phải bị từ chối bằng diagnostic chi tiết ở compile time. Chương
   trình sai không được compile thành artifact rồi mới SIGSEGV/SIGBUS/trap mơ hồ.
4. Compiler cũng không được segfault khi gặp source, AST, MIR hoặc LIR malformed;
   phải trả diagnostic xác định, non-zero và không để lại artifact.

## Thứ tự chuyển việc

- Nếu một AI khác đang làm dở phase hiện tại, chỉ chuyển sang prompt này sau khi
  phase đó đạt gate và có commit sạch. Không giẫm lên diff đang chạy.
- Sau checkpoint đó, tạm dừng các phase feature nâng cao; hoàn thành memory
  foundation này trước Generic, FFI, SIMD, Async/Task, optimizer và production.
- JSON/XML nằm ngoài scope; không sửa test hoặc implementation JSON/XML trong
  công việc này.

## Nguồn chuẩn bắt buộc

Đọc đầy đủ trước khi sửa code:

1. `docs/vir_language_spec_v2.0_vi.md`, đặc biệt §4.5–4.8.5.
2. `docs/vir_language_spec_v2.0_en.md`, phần tương ứng để kiểm tính đồng bộ.
3. `docs/MEMORY_MANAGEMENT.md`.
4. `docs/VIR_EXECUTION_MODEL.md`.
5. `docs/ai-spec/vir-lang/references/types.md`.
6. `docs/ai-spec/vir-lang/references/control-flow.md`.
7. `docs/ai-spec/vir-lang/references/functions.md`.
8. `stdlib/vir/compiler/sem_pass8_borrow.vri`.
9. `stdlib/vir/compiler/ast_to_mir.vri`, `mir.vri`, `lir.vri` và các backend.
10. Runtime allocator thực tế dưới `stdlib/vir/rt/` và `stdlib/vir/mem/`.

Spec quyết định semantics. Implementation hiện tại chỉ là baseline để tìm gap,
không được dùng để hạ thấp contract.

## Trạng thái hiện tại cần thay thế

- `sem_pass8_borrow.vri` hiện theo dõi arena local và từ chối cả owned escape.
  Phải đổi thành: owned move được phân loại/promote; borrow escape vẫn bị reject.
- `ast_to_mir.vri` hiện hạ `ArenaBlock` chủ yếu thành cặp
  `MIR_INTR_ARENA` save/restore watermark. Cách này chưa biểu diễn region,
  promotion, owned graph hoặc cleanup trên mọi CFG edge.
- Sự tồn tại của borrow pass, arena intrinsic hoặc allocator API không chứng minh
  semantics đã hoàn chỉnh. Chỉ test E2E, structural IR và mutation proof mới được
  tính là bằng chứng.

Không được ghi đè thay đổi đang có trong worktree. Trước khi bắt đầu, đọc
`git status`, xác định owner của diff hiện có và chỉ stage file thuộc phase mình
thực hiện.

## Contract bộ nhớ bắt buộc

### Ownership và move

- Mỗi Move value có đúng một owner.
- Assignment, truyền owned argument, capture owned value và `out` chuyển
  ownership; source binding bị invalid ngay sau move.
- Copy types vẫn copy ngầm và không bị đánh dấu moved.
- Detect path-sensitive: use-after-move, double move, partial move, move trong
  một nhánh nhưng dùng sau merge, move trong loop, reassignment phục hồi binding,
  move qua tuple/entity/enum payload và move qua call/return.
- Không dùng tên biến đơn thuần làm identity nếu shadowing, field projection,
  index projection hoặc SSA version khác nhau.

### Borrow

- Nhiều shared borrow được phép; mutable borrow phải độc quyền.
- Shared và mutable borrow không được overlap.
- Borrow không được sống lâu hơn owner, region nguồn hoặc suspension boundary
  không cho phép.
- Return/capture/store một borrow local hoặc arena-local vào nơi sống lâu hơn
  phải fail compile.
- Mutation, move, reset hoặc drop owner khi borrow còn live phải fail compile.
- Phân tích phải dựa trên CFG/liveness hợp lý, không giữ borrow tới cuối function
  một cách giả tạo nếu last use đã kết thúc, và cũng không kết thúc borrow quá
  sớm chỉ để test pass.
- Raw pointer không kéo dài lifetime. Trường hợp statically trackable phải bị
  reject; vùng thật sự unsafe/FFI phải có boundary rõ và runtime không được tuyên
  bố memory-safe thay cho phần compiler không chứng minh được.

### Arena, region và escape

- Mọi lexical scope có region/lifetime identity; explicit `arena:` tạo child
  region có watermark/reset semantics.
- Allocation không escape được phép ở stack/register hoặc child arena.
- Owned graph escape sang scope cha phải đặt trực tiếp hoặc promote tới ancestor
  arena gần nhất sống đủ lâu.
- Escape qua `out`, global storage hoặc task/thread boundary phải chọn vùng có
  lifetime và synchronization phù hợp; không mặc định raw pointer sống mãi.
- Promotion phải transitive trên toàn bộ reachable owned graph, gồm backing
  storage của string/array/dict/entity/enum payload. Cấm shallow-copy header.
- Chỉ graph reachable từ value escape được promote. Các allocation còn lại của
  child arena vẫn reset hàng loạt ở `end`.
- Nested arena phải promote theo từng lifetime đích, không giữ toàn bộ ancestor
  hoặc child arena chỉ vì một value escape.
- Manual low-level `arena_reset`/`arena_free` không tự promote. Compiler phải
  reject khi còn borrow/live reference statically known; runtime phải trap có
  diagnostic nếu invariant kiểm được tại runtime bị vi phạm.

### Cleanup và control flow

- Chèn drop/reset đúng một lần trên mọi cạnh thoát: fallthrough, `break`, `skip`,
  `out`, `throw`, `revert`, `ensure`, cancel, timeout và unwind nội bộ.
- Không double-reset, double-drop hoặc bỏ cleanup khi optimizer biến đổi CFG.
- Resource phi-memory như file/socket/FFI handle không được coi là đã cleanup chỉ
  vì arena reset; dùng drop/resource contract tương ứng.
- Async frame chỉ giữ value thật sự sống qua suspension. Borrow/arena reference
  qua `await` phải được chứng minh lifetime hoặc reject trước codegen.

## Bắt lỗi sớm và diagnostic chi tiết

Mỗi lỗi phải dừng ở tầng sớm nhất có đủ thông tin:

- Lexer/parser: token, delimiter, `arena:` header, `&`/`&mut`, block/end và cú
  pháp malformed. Parser không được crash và không chịu trách nhiệm cho lỗi
  ownership semantic.
- Name/type/ownership passes: unresolved owner, type category Copy/Move, move
  state, borrow conflict, lifetime escape và allocator misuse có thể chứng minh.
- MIR verifier: region dominance, owner uniqueness, use-after-drop, reset khi còn
  live reference, missing cleanup edge, invalid promotion, graph/header mismatch,
  phi merge không nhất quán và intrinsic operand malformed.
- LIR/backend verifier: width/alignment/address-space/ABI sai, unsupported lowering
  hoặc region operation chưa hạ. Không phát machine code bằng placeholder.
- Runtime: chỉ dành cho điều kiện không thể chứng minh tĩnh như OOM hoặc lỗi từ
  FFI/raw unsafe. Phải trap có message/cause và exit non-zero xác định; SIGSEGV
  trống không được coi là diagnostic.

Diagnostic compile-time bắt buộc có:

1. Mã lỗi ổn định.
2. File, line, column và primary source span.
3. Loại vi phạm: use-after-move, conflicting borrow, dangling borrow,
   use-after-reset, invalid promotion, double drop, v.v.
4. Secondary span chỉ ra nơi owner được tạo/move/drop, borrow bắt đầu và lifetime
   kết thúc.
5. Tên binding/projection và type liên quan.
6. Giải thích ngắn vì sao lifetime không hợp lệ.
7. Gợi ý sửa phù hợp như move owner, rút ngắn borrow hoặc cấp phát ở scope cha;
   không gợi ý API/cú pháp không tồn tại.

Không phát hàng loạt diagnostic trùng cho cùng root cause. Không in địa chỉ raw
hoặc state nội bộ không ổn định trong oracle mặc định. Debug mode có thể thêm
region/owner ID nhưng output chuẩn phải deterministic.

Nếu compiler gặp invariant nội bộ sai, trả internal-compiler diagnostic kèm
stage, instruction/node ID và source origin nếu có; không dereference null, đọc
out-of-bounds hoặc tiếp tục codegen.

## Test contract phải viết trước implementation

Tạo `tests/memory_contract/` với manifest và runner riêng. Mỗi case phải quy định
`compile_pass`, `compile_fail`, `run`, `run_fail` hoặc `structural`. Negative test
phải yêu cầu non-zero, đúng diagnostic code/span và không có artifact.

### Positive bắt buộc

- Copy và Move cơ bản; reassignment sau move.
- Owned value escape khỏi `if`, `when`, `loop`, `for` và explicit `arena:` bằng
  assignment/move vào owner ngoài.
- `out` trực tiếp từ nested arena.
- Nested arena promote tới ancestor gần nhất.
- String, array, dict, entity, enum payload và owned graph sâu/nhiều nhánh.
- Hai graph chia sẻ dữ liệu chỉ khi type/ownership contract cho phép.
- Non-escaping temporary bị reset, escaping graph vẫn hợp lệ sau `end`.
- Early `break`/`skip`/`out`/`throw`/`revert`/`ensure` cleanup chính xác.
- Loop dài giữ RSS bounded khi không escape; escape có chủ ý sống đúng lifetime.
- Function call, recursion, closure/capture nếu được hỗ trợ, async frame và task
  boundary theo contract chính thức.
- O0/O1/O2/O3 cho exact behavior giống nhau.

### Negative bắt buộc

- Use-after-move, double move và move ở một CFG branch.
- Shared/mutable overlap; hai mutable borrow; mutate/move/drop khi borrowed.
- Return/store/capture local borrow hoặc arena borrow ra ngoài lifetime.
- Borrow/raw pointer dùng sau `end`, reset hoặc free.
- Manual reset/free khi còn reference live.
- Partial/nested projection move sai.
- Double drop, wrong-region drop/free và cleanup edge thiếu do early exit.
- Async borrow qua suspension không đủ lifetime.
- Malformed arena/borrow syntax và malformed MIR fixtures cho verifier.
- Allocation size overflow, alignment invalid và OOM fault injection.

### Structural và mutation proof bắt buộc

- Dump MIR phải hiện owner ID, region ID, allocation region, move/drop/reset và
  promotion decision đủ để verifier/test kiểm.
- Artifact non-escaping không chứa heap/ARC promotion thừa.
- Escape tới parent arena không bị hạ thành shallow header copy.
- Xóa một reset, drop, borrow check, graph edge hoặc promotion phải làm test fail.
- Ép allocation về child arena rồi reset phải bị structural/runtime test phát
  hiện trước khi thay đổi được chấp nhận.
- Chạy ASan/UBSan hoặc công cụ tương đương trên backend hỗ trợ, nhưng sanitizer
  không thay thế test semantic và verifier.

## Các phase triển khai

### Phase 0 — Baseline và crash corpus

- Viết runner/manifest trước.
- Thu thập mọi fixture hiện compile thành công rồi SIGSEGV/SIGBUS do memory.
- Ghi stage cuối, exit code, stdout/stderr, target và artifact hash.
- Thêm regression test tối thiểu cho từng crash trước khi sửa.

### Phase 1 — Ownership/region data model

- Thêm identity ổn định cho owner, projection, lexical region và allocation site.
- Giữ metadata xuyên AST/HIR/MIR; không dựa vào map tên biến toàn cục.
- Xây CFG/liveness và lattice trạng thái move/borrow/region cho branch/loop/merge.
- Thêm dump định dạng deterministic phục vụ structural test.

### Phase 2 — Borrow checker đầy đủ

- Thay kiểm tra arena cũ bằng path-sensitive ownership/borrow analysis.
- Cho owned move escape, giữ borrow escape là compile error.
- Triển khai diagnostic primary/secondary span và tránh diagnostic cascade.
- Tất cả negative ownership/borrow phải fail trước MIR codegen và không sinh
  artifact.

### Phase 3 — Escape analysis và placement/promotion

- Phân loại `NoEscape`, `ScopeEscape`, `GlobalEscape` theo spec.
- Chọn destination region gần nhất đủ lifetime.
- Promote toàn bộ owned graph; xử lý nested/cyclic graph theo ownership contract.
- Ưu tiên direct placement; không copy sau reset, không giữ cả arena vì một node.
- Thêm evidence trong MIR dump và mutation tests.

### Phase 4 — Drop/reset trên toàn CFG

- Hạ cleanup cho mọi cạnh normal/early/error exit.
- Đảm bảo `ensure`/`revert` order, arena watermark và resource drop đúng một lần.
- Chạy optimizer rồi verify lại cleanup invariants.

### Phase 5 — MIR/LIR verifier và compiler crash containment

- Verifier chạy bắt buộc trước optimizer, sau optimizer và trước backend emission.
- Mọi invariant sai trả diagnostic nội bộ deterministic, non-zero, no artifact.
- Parser/semantic/MIR fuzz corpus không được làm compiler segfault/hang.
- Không catch signal rồi gọi đó là diagnostic; sửa root cause và invariant.

### Phase 6 — Runtime allocator và mọi backend

- Hạ region allocation, promotion, drop/reset và trap path thật trên ARM64,
  x86_64, RISC-V64 và Wasm/WASI nếu target đang được quảng cáo.
- Chuẩn hóa OOM, overflow, alignment và allocation-failure behavior.
- Không để backend unsupported silently NOP hoặc sinh artifact không an toàn.
- Chạy artifact thật trên target/runtime tương ứng, không chỉ kiểm file tồn tại.

### Phase 7 — Self-host, stress và production gate

- Rebuild Stage 1 → Stage 2 → Stage 3; Stage 2/3 phải fixed-point theo gate dự án.
- Chạy full regression, memory contract, mutation, differential O0–O3, stress
  loop/graph và multi-target matrix.
- Compiler và artifact không có unexpected SIGSEGV/SIGBUS/abort trong corpus.
- Ghi rõ mọi raw/FFI unsafe boundary còn ngoài static guarantee.

## Kỷ luật commit

- Hoàn tất và kiểm chứng từng phase rồi commit riêng trước khi sang phase sau.
- Commit message: `compiler: complete memory phase N <short-name>`.
- Body ghi test IDs, exact command, regression/self-host result và mutation proof.
- Không commit phase dưới tên “complete” nếu còn required fail/skip.
- Không stage hoặc sửa thay đổi không liên quan có sẵn trong worktree.
- Không amend/squash phase trước để che regression; fix sau là commit mới.
- Không push, tag hoặc promote release nếu owner chưa yêu cầu riêng.

## Luật chống pass giả

- Không sửa spec/test/oracle để khớp implementation.
- Không đổi compile-fail thành runtime-fail.
- Không biến borrow/escape check thành warning.
- Không giữ toàn bộ arena sống để né graph promotion.
- Không promote mọi allocation lên global heap để test pass.
- Không shallow-copy header, leak có chủ ý, vô hiệu reset/drop hoặc dùng ARC cho
  mọi value để che thiếu region analysis.
- Không coi signal trap trống là diagnostic.
- Không chạy test bằng compiler binary cũ hơn source vừa sửa.

## Definition of Done — 100%

Chỉ được tuyên bố hoàn thành khi đồng thời đạt:

- Tất cả memory contract positive/negative/structural/run-fail PASS.
- Parser, semantic, MIR và LIR reject đúng tầng; compile error không để artifact.
- Không còn known valid-memory fixture compile xong rồi segfault vì arena,
  ownership, borrow, promotion, cleanup hoặc allocator lowering.
- Owned escape hoạt động cho mọi lexical scope và explicit `arena:`.
- Borrow diagnostics có primary/secondary span và nguyên nhân cụ thể.
- Nested owned graph không shallow-copy hoặc dangling backing storage.
- Cleanup đúng trên mọi CFG exit và sau optimizer.
- Mọi target được quảng cáo chạy artifact thật; target chưa đạt phải bị đánh dấu
  unsupported, không được quảng cáo partial như complete.
- Full regression sạch, Stage 2/3 fixed-point đạt, mutation proof hoạt động.
- Báo cáo cuối liệt kê commit hash từng phase, test evidence, performance/RSS
  trước-sau và mọi unsafe boundary còn chủ ý.

Nếu một điều kiện chưa đạt, trạng thái là PARTIAL hoặc BLOCKED, không phải 100%.
