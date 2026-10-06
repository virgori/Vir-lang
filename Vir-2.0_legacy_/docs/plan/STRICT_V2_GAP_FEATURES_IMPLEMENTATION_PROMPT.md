# Prompt triển khai các tính năng Strict v2 còn thiếu/no-op

## Vai trò

Bạn là AI triển khai compiler Vir tự host. Nhiệm vụ là biến các feature đang
frontend-only, partial hoặc no-op thành implementation đúng Vir Language Spec
v2.0, dùng bộ test contract có sẵn làm chuẩn bất biến.

## Nguồn chuẩn bắt buộc

Đọc đầy đủ trước khi sửa code:

1. `docs/vir_language_spec_v2.0_vi.md`
2. `docs/VIR_EXECUTION_MODEL.md`
3. `docs/report/checklist/UNFINISHED_AND_NOOP_FEATURES_CHECKLIST.md`
4. `docs/report/checklist/STRICT_V2_GAP_TEST_CONTRACT.md`
5. `tests/spec_gap_contract/README.md`
6. `tests/spec_gap_contract/manifest.tsv`

Language spec quyết định semantics. Test contract quyết định observable
acceptance. Implementation hiện tại không được dùng để hạ thấp hai nguồn này.

## Luật tuyệt đối

- Không sửa language spec.
- Không sửa/xóa fixture, expected output, oracle hoặc manifest để làm test pass.
- Không đổi runtime test thành parser-only/compile-only test.
- Không coi intrinsic NOP/pass-through là implementation.
- Không coi cross-compile thành công là target support.
- Không dùng fixture không liên quan để đại diện cho feature.
- Không tự bịa API cho mục `blocked_contract`.
- Không động vào JSON/XML; chúng ngoài scope.
- Không phá hoặc ghi đè thay đổi hiện có của người dùng trong worktree.
- Không tuyên bố complete nếu còn test required fail, skip ngoài danh sách
  `blocked_contract`, hoặc target được quảng cáo chưa chạy artifact thật.

Nếu cho rằng test mâu thuẫn spec, dừng feature đó và báo chính xác trích dẫn
spec + test ID. Không tự sửa test.

## Phase 0 — Test runner và baseline

1. Viết runner riêng cho `tests/spec_gap_contract/manifest.tsv`.
2. Runner phải hỗ trợ:
   - `run`: compile, chạy, so exact stdout và exit code;
   - `compile_fail`: yêu cầu non-zero và diagnostic oracle;
   - `run_fail`: compile thành công, artifact chạy phải trap/thoát non-zero bằng
     conversion-error path và không in raw/saturated value;
   - `structural`: chạy behavioral gate rồi kiểm MIR/artifact/section/symbol;
   - `blocked_contract`: báo BLOCKED, tuyệt đối không tính PASS.
3. Mỗi test có timeout để phát hiện deadlock async/Port.
4. Lưu baseline theo ID: PASS/FAIL/BLOCKED, compile exit, run exit, stdout,
   stderr và target.
5. Không nối suite này vào `run_tests.sh` cho tới khi một nhóm feature đạt toàn
   bộ gate của nhóm.

## Phase 1 — Numeric semantics và precedence

Làm `PREC-001..008`, `NEG-001..004`, `FLOAT-001..003` và `CAST-001..008` pass
trước các feature nâng cao:

- `^` kết hợp phải và ưu tiên hơn unary `-`;
- `*`/`/`, `mod`/`%`, shift/cast, cộng/trừ, comparison, equality và logic đúng
  bảng precedence;
- assignment kết hợp phải;
- bốn dạng power thiếu toán hạng fail ở parser và không sinh artifact;
- số âm giữ signed numeric semantics qua literal, arithmetic, call và array;
- integer overflow theo wrapping contract;
- float là IEEE-754 binary64 và `print` không lộ raw bit pattern;
- int→float dùng round-to-nearest ties-to-even;
- float→int truncate toward zero;
- NaN, infinity và out-of-range phải đi qua conversion-error trap;
- cast fixed-width kiểm range;
- cast vẫn đúng qua call, store và register spill pressure.

Mutation bắt buộc: đổi power sang left-associative, đổi unary precedence, dùng
bit-copy thay numeric cast, bỏ range check hoặc saturate out-of-range thì test
phải fail.

### Baseline đã đo trên virc 3.2.0

Kết quả audit ngày 2026-09-17: 16/23 case đạt observable oracle cơ bản, 7 case
chưa đạt. Phải chạy lại để xác nhận trước khi sửa; không được mặc định binary
hoặc worktree vẫn giống baseline này.

- `PREC-001`: compile/run thành công nhưng `-2^2` in `4`, phải là `-4`. Các
  dòng precedence còn lại của fixture đúng.
- `PREC-004`: chained assignment `left = right = 7` fail parser với `E1004`
  tại toán tử `=` thứ hai; assignment chưa right-associative E2E.
- `NEG-001`: ba kết quả signed integer đúng (`-7`, `-5`, `-9`) nhưng bool cuối
  in `1` thay vì oracle `true`. Không được sửa oracle. Nếu normative spec không
  quy định textual formatting của `print bool`, báo đây là contract gap cho
  owner thay vì quy kết sai cho biểu diễn số âm.
- `FLOAT-002`: `print 1.5` và `print -0.25` đang lộ raw IEEE-754 bit pattern
  `4609434218613702656` và `-4625196817309499392`.
- `FLOAT-003`: `-0.0 != 0.0` đang dẫn tới exit `71`; float equality có dấu hiệu
  so raw bits thay vì IEEE numeric equality.
- `CAST-003`: fail typecheck `E3007` tại `convert(values[1])`; phải giữ đúng
  float representation/type qua array element, function call và spill pressure.
- `CAST-004`: compile thành công nhưng trap `133` trước khi in `127`/`-128`;
  fixed-width cast phải truncate toward zero rồi range-check giá trị integral,
  không reject `127.9` hoặc `-128.9` chỉ vì nguồn float vượt biên phân số.

Các case baseline đã đạt: `PREC-002/003/005/006/007/008`, `NEG-002/003/004`,
`FLOAT-001`, `CAST-001/002/005/006/007/008`. Với `CAST-005..008`, exit `133`
chỉ chứng minh có trap; runner Phase 0 vẫn phải xác minh đó là conversion-error
path đúng, không phải một trap ngẫu nhiên.

## Phase 2 — Precomp

Làm cho `PRECOMP-001..007` pass:

- evaluator compile-time cho integer, comparison, branch, call và recursion;
- precedence thấp nhất đúng spec;
- inline kết quả vào artifact;
- loại call/precomp runtime khỏi call graph;
- I/O, allocation/array và phép chia zero phải fail tại compile time;
- `throw` trong precomp trở thành compile diagnostic.

Mutation bắt buộc: vô hiệu evaluator hoặc để call chạy runtime thì structural
gate phải fail.

## Phase 3 — Generic

Làm cho `GENERIC-001..006` pass:

- giữ generic params/type args trong AST, symbols và type metadata;
- kiểm arity và unresolved type;
- specialization/monomorphization ổn định;
- không rò type/layout giữa các specialization;
- entity hai type parameter hoạt động E2E.

Mutation bắt buộc: dùng một body/layout chung không specialize phải làm ít nhất
một test fail.

## Phase 4 — FFI và Bundle/Isolate semantic

Làm các test `FFI-*`, `UI-002`, `UI-003`, `UI-006..009` pass:

- `@bind(c)`/`@bind(wasm)` declaration-only và bắt buộc type annotation;
- `@bind(asm)` bắt buộc body và bypass optimizer;
- Wasm import section có signature đúng;
- `bundle` nhúng bytes thật theo đường dẫn tương đối và fail khi file thiếu;
- standalone `isolate` reject direct I/O, implicit outer-memory access và call
  chưa expose.

Không xử lý `UI-004/UI-005` trước khi contract quan sát được quyết định.

## Phase 5 — SIMD

Làm `SIMD-001..006` pass:

- type/layout `flux<T,N>`;
- read swizzle cho `xyzw` và `rgba`, cho phép lane lặp;
- write-mask giữ lane không ghi, cấm lane lặp;
- kiểm width và lane range;
- reject width không phải lũy thừa hai;
- backend lowering thật, không pass-through.

Sau scalar-correctness proof mới thêm NEON/SSE/AVX/Wasm SIMD optimization.

## Phase 6 — Async/Task và Port

Chỉ bắt đầu sau khi owner đóng `ASYNC-003` — cách test harness chọn/link executor
tuần tự chính thức mà không tạo runtime mặc định.

Sau đó làm `ASYNC-001..008` và `PORT-001..006` pass:

- compiler hạ async thành activation frame + state machine;
- local sống qua nhiều suspension point;
- `task`, `await`, `wait`, `await pass`, cancel và select có semantics thật;
- cancel chạy `revert` rồi `ensure` đúng một lần;
- select chỉ chạy một winner;
- Port typed MPSC, bounded queue, FIFO, wraparound, empty recv suspension,
  cooperative backpressure và move semantics;
- không hard-code scheduler policy vào compiler.

Không xử lý quiet completion cho tới khi `ASYNC-009` được đóng.

Deadlock, timeout hoặc output đúng do synchronous pass-through đều là FAIL.

## Phase 7 — AI/ML

Làm `AI-001`, `AI-003..009` pass mà không phá suite AI hiện có:

- quantize transparent trong infer;
- INT4 odd-element packing không đọc byte rác;
- bits phải là literal thuộc tập cho phép;
- rectangular matmul không hard-code 2x2;
- shape mismatch fail compile;
- infer/backward và infer/train nesting bị reject.

Không tổng quát hóa autodiff bằng raw pointer/layout test. `AI-002` chỉ được mở
khi có API quan sát gradient công khai hoặc contract tương đương được owner duyệt.

## Phase 8 — Optimizer

Làm `OPT-001/002` pass ở O0/O1/O2/O3 với exact output giống nhau. Sau đó:

- bật từng pass đang disabled riêng lẻ;
- thêm differential và mutation fixture cho LICM, unroll, idiom collapse,
  polyhedral transform, SIMD, TCO, IRC và shrink-wrap;
- bất kỳ pass nào chưa có proof phải giữ disabled, không quảng cáo implemented.

## Phase 9 — Target và zero-overhead

- Chạy `TARGET-001/002` trên target thật trước khi quảng cáo support.
- Kiểm exact stdout và exit code 37.
- Wasm phải thực thi bằng WASI runtime, không chỉ sinh file.
- Windows phải có PE import/startup proof trên Windows thật.
- Linux compiler artifact phải qua self-execution smoke.
- `ZERO-001` phải chứng minh binary không async không chứa executor/scheduler.

## Regression và self-host gates

Sau mỗi phase:

1. Chạy toàn bộ nhóm contract vừa mở.
2. Chạy full regression suite hiện tại.
3. Rebuild self-host compiler.
4. Kiểm Stage 2/Stage 3 fixed point trên target phát hành.
5. Chạy mutation test của phase.
6. Ghi báo cáo bằng test ID, command, exit code và exact output.
7. Chỉ sau khi toàn bộ gate trên đạt, tạo một commit kết thúc phase trước khi
   chuyển sang phase tiếp theo.

Không được giảm số test, comment-out fixture hoặc dùng binary cũ để vượt gate.

## Kỷ luật commit theo phase

- Phase 0 đến Phase 9 phải có commit kết thúc riêng; tuyệt đối không dồn nhiều
  phase vào một commit rồi mới báo cáo.
- Trước mỗi commit, kiểm tra `git status` và `git diff`; chỉ stage file thuộc
  phase hiện tại. Không stage, sửa, restore hoặc ghi đè thay đổi không liên quan
  đã có sẵn trong worktree.
- Commit chỉ được tạo khi Definition of Done của phase đã đạt. Nếu phase bị
  BLOCKED hoặc còn test required fail, dừng và báo blocker; không tạo commit có
  tên hoặc nội dung ngụ ý phase đã hoàn thành.
- Commit message bắt buộc có dạng `compiler: complete phase N <short-name>`.
  Body phải ghi các test ID đã mở, regression/self-host gate đã chạy và mutation
  proof tương ứng.
- Sau commit, ghi commit hash vào báo cáo phase và xác nhận worktree không còn
  thay đổi chưa commit do chính phase đó tạo ra.
- Không amend, squash hoặc rewrite commit phase trước để che regression. Fix về
  sau phải là commit mới và báo rõ phase bị ảnh hưởng.
- Không push, tag hoặc promote chỉ vì đã commit; các thao tác đó cần yêu cầu
  riêng của owner.

## Definition of Done

Chỉ báo hoàn thành một phase khi:

- mọi test required trong phase PASS;
- không có skip ngoài `blocked_contract`;
- mutation proof FAIL đúng như dự kiến;
- full regression không regress;
- self-host fixed point còn đúng;
- artifact target chạy thật;
- báo cáo nêu rõ phần còn BLOCKED/PARTIAL.

Khi toàn bộ phase hoàn tất, cập nhật checklist bằng bằng chứng; không sửa spec và
không tự động promote release/tag/push nếu chưa có yêu cầu riêng của owner.
