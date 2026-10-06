# Prompt nghiêm ngặt: chặn UFCS receiver chưa resolve trước lowering

## Vai trò và kết quả bắt buộc

Bạn là compiler engineer chịu trách nhiệm sửa một lỗi memory-safety trong
compiler Vir tự host 3.5.0. Compiler hiện có thể chấp nhận một member call sai,
hạ identifier chưa resolve thành địa chỉ hàm `0`, rồi sinh binary segfault ở
request đầu tiên.

Ca lỗi đã xác nhận trong InterVir:

```vir
let opt_u = url.parse(raw_uri)
```

`stdlib/vir/net/url.vri` không khai báo namespace value `url`, method `parse`
hay export `parse`. API thật đang active là:

```vir
func url_parse(raw_url: string)
export Url, url_new, url_parse, ...
```

Trong cùng compile graph lại có một free function HTTP trùng bare name:

```vir
func parse(buf: ptr, nread: int) -> ValidatedRequest
```

Compiler đã coi `url.parse(raw_uri)` là free-function UFCS
`parse(url, raw_uri)`. Receiver `url` không resolve và có type `Void`, nhưng
type checker vẫn cho qua. Lowering sau đó biến `url` thành `MIR_INTR_ADDR_OF`;
backend không tìm thấy function `url` nên materialize số `0`. Function HTTP
`parse` nhận `buf = 0`, gọi `parse_into(buf, nread, req)`, và lần đọc byte đầu
tiên segfault với exit code `139`.

Kết quả cuối cùng bắt buộc:

1. `url.parse(raw_uri)` bị từ chối ở compile time với diagnostic ổn định tại
   receiver/member call;
2. compiler không được chọn một free function chỉ vì bare member name và arity
   trùng;
3. receiver chưa resolve hoặc không có static type không bao giờ được coi là
   tương thích với tham số đầu của UFCS;
4. semantic failure không được đi tiếp tới AST-to-MIR, LIR hay backend;
5. lowering/backend có fail-closed guard để unresolved callable/address không
   thể âm thầm trở thành null;
6. `url_parse(raw_uri)` vẫn compile và chạy đúng;
7. entity method, callable field và free-function UFCS hợp lệ không regression;
8. self-host fixed point và regression suite của project đều pass.

Đây là task sửa compiler end-to-end, không phải chỉ đổi dòng source trong
InterVir. Có thể dùng `url_parse(raw_uri)` làm workaround phía project, nhưng
workaround đó không đóng bug compiler.

## Nguồn sự thật và phạm vi

Trước khi sửa, đọc và đối chiếu ít nhất:

- `docs/vir_language_spec_v2.0_vi.md`, mục UFCS/method/member access;
- `docs/vir_language_spec_v2.0_en.md`, mục tương ứng;
- `docs/ai-spec/vir-lang/references/functions.md`;
- `docs/ai-spec/vir-lang/references/modules.md`;
- `docs/ai-spec/vir-lang/references/types.md`;
- `docs/MEMORY_MANAGEMENT.md`;
- `stdlib/vir/net/url.vri`;
- `stdlib/vir/compiler/sem_pass3_names.vri`;
- `stdlib/vir/compiler/sem_pass6_typecheck.vri`;
- `stdlib/vir/compiler/ast_to_mir.vri`;
- `stdlib/vir/compiler/lir_codegen.vri`;
- `stdlib/vir/compiler/lir_codegen_x86.vri`;
- các backend public khác có xử lý function address hoặc unresolved symbol;
- test UFCS, module resolution, negative diagnostics và self-host hiện có.

Không sửa language specification để hợp thức hóa behavior hiện tại. Không
hard-code `url`, `parse`, `raw_uri`, InterVir hay HTTP vào compiler.

Source canonical của compiler nằm trong các module dưới
`stdlib/vir/compiler/`. Không sửa riêng bundle
`stdlib/vir/compiler/virc.vri`; sửa module canonical rồi đồng bộ bằng workflow
đang được repo xác nhận, bao gồm `python3 tools/sync_virc.py --check`.

Đọc `git status` trước khi làm. Worktree có thể đang chứa thay đổi của owner;
không reset, restore, overwrite, stage hoặc commit file ngoài task.

## Baseline bắt buộc phải tái hiện

Ghi commit/ref, `./bin/virc --version`, SHA-256 compiler, target, optimization
level, command, stdout, stderr và exit code. Baseline hiện được quan sát với
`virc 3.5.0`:

- `server.vri` compile thành công;
- chỉ còn ba warning `W4001` tại `json_lookup`;
- server listen thành công;
- request đầu tiên kết thúc bằng signal/exit `139`;
- LLDB dừng ở `parse_into` tại lệnh đọc byte qua địa chỉ `0`;
- crash vẫn xuất hiện ở `-O0`, nên không được phân loại là lỗi optimizer;
- một test gọi trực tiếp `parse_into` với buffer hợp lệ chạy đúng;
- thêm marker chứng minh HTTP wrapper `parse` bị gọi sau dispatch parser ban
  đầu;
- thay riêng `url.parse(raw_uri)` bằng `url_parse(raw_uri)` cho phép execution
  đi tiếp qua router dispatch.

Không dùng các bullet trên thay cho reproduction mới. Nếu repo InterVir ngoài
tree không có sẵn trong môi trường test, dựng fixture tối thiểu độc lập trong
repo Vir và ghi rõ phần E2E ngoài repo nào chưa chạy được.

Fixture tối thiểu phải giữ collision theo tên và arity, ví dụ tương đương:

```vir
include net.url

func parse(buf: ptr, raw_uri: string) -> int:
    out 7
end.

func main:
    let raw_uri = "/health?ready=1"
    let bad = url.parse(raw_uri)
    print(bad)
    out 0
end.
```

Fixture này phải fail compilation. Không được sửa fixture thành direct call để
làm test xanh. Tạo thêm positive control dùng API thật:

```vir
include net.url

func main:
    let raw_uri = "/health?ready=1"
    let parsed = url_parse(raw_uri)
    out 0
end.
```

Positive control phải compile; nếu harness hỗ trợ runtime assertion cho `Url`,
kiểm tra cả path/query thay vì chỉ exit `0`.

## Root cause phải được xác nhận trên source active

Không tin line number cố định; tìm lại symbol trên HEAD. Baseline hiện chỉ ra
chuỗi lỗi sau.

### 1. Name/module resolution không khóa nghĩa receiver

`url` trong `url.parse(raw_uri)` không phải local, global value, constant hay
function value. Nếu parser coi cú pháp này là module qualification, resolver
phải tra export table của module `net.url`; module đó không export `parse`. Nếu
parser coi đây là member/UFCS call, receiver `url` phải resolve thành một value
có static type trước khi tìm candidate.

Hai cách hiểu đều phải kết thúc bằng compile error. Cấm chuyển module-like
identifier chưa resolve thành một receiver value giả rồi tiếp tục UFCS lookup.

### 2. UFCS compatibility đang coi unknown là wildcard

Trong `sem_pass6_typecheck.vri`, kiểm tra lại:

```text
pass6_ufcs_types_compatible
  declared == 0 || actual == TypeKind.Void  => compatible
```

Trong nhánh `Priority 3: Free Function / Builtin UFCS`, receiver compatibility
chỉ được kiểm tra khi cả expected và actual đều khác `Void`. Vì vậy receiver
unknown có thể bỏ qua toàn bộ type check. Sau đó node vẫn được đánh dấu như
free-function UFCS (`builtin_id = 203`) nếu bare-name lookup và arity pass.

`TypeKind.Void` đang gộp nhiều trạng thái có nghĩa khác nhau: không có value,
chưa biết type, type lookup thất bại hoặc recovery. Không trạng thái nào được
dùng như bằng chứng receiver tương thích. Nếu cần giữ recovery để giảm
diagnostic cascade, recovery phải mang trạng thái lỗi rõ ràng và tuyệt đối
không tạo resolved callee.

### 3. AST-to-MIR vẫn hạ identifier chưa resolve

Trong `ast_to_mir.vri`, identifier không phải local/global/constant/bool/null
đang rơi xuống `MIR_INTR_ADDR_OF` theo bare name. Nhánh MethodCall/UFCS sau đó
normalize receiver và explicit arguments thành ordinary call.

Đây là fail-open behavior: semantic đã không chứng minh receiver là một value,
nhưng lowering tự diễn giải tên đó như function address.

### 4. Backend biến unresolved address thành zero

Trong ARM64 `lir_codegen.vri`, `MIR_INTR_ADDR_OF` lookup function theo string.
Nếu lookup thất bại, backend materialize `0` và tiếp tục. Kiểm tra cùng contract
trên x86-64, Wasm, RISC-V và mọi backend public.

Không được coi zero là representation hợp lệ cho một unresolved symbol. Null
function/data pointer chỉ hợp lệ khi source hoặc typed IR yêu cầu null rõ ràng,
không phải khi compiler lookup thất bại.

## Contract semantic cần triển khai

Với `receiver.member(args...)`, xử lý theo thứ tự sau:

1. resolve receiver expression thành value và static type;
2. nếu syntax có thể là module qualification, resolve module identity và
   exported member bằng module resolver; module không phải runtime receiver;
3. tìm entity method của đúng receiver type;
4. tìm callable field của đúng receiver type;
5. chỉ sau đó tìm visible free function `member(receiver, args...)`;
6. kiểm tra đầy đủ receiver type, explicit argument types, arity,
   `in`/`ref`/`out`, ownership và visibility;
7. annotate AST bằng resolved callee kind, stable identity/signature và source
   span;
8. nếu bất kỳ bước bắt buộc nào thất bại, emit diagnostic và không tạo resolved
   call node.

Các invariant bắt buộc:

- receiver unresolved là lỗi, không phải wildcard;
- `Void`/unknown/error type không được làm free-UFCS candidate hợp lệ;
- `declared == 0` chỉ được dùng cho unannotated source theo contract type
  inference rõ ràng, không được che lookup failure;
- arity match không đủ để chọn candidate;
- bare-name match không đủ để chọn candidate;
- module name không được truyền như runtime argument 0;
- backend không được resolve lại semantic identity bằng bare name;
- declaration order và unrelated imports không được đổi callee;
- một diagnostic recovery node không được sinh executable call.

Ưu tiên dùng diagnostic hiện có nếu đúng nghĩa:

- `E3021` cho unresolved UFCS/member candidate;
- `E3001` cho receiver/argument type mismatch sau khi cả hai type đã resolve;
- diagnostic name/module hiện có cho unknown receiver hoặc missing exported
  module member.

Không ép mọi lỗi thành `E3001`. Trường hợp `url` không phải value và module
`net.url` không export `parse` nên diagnostic phải nói đúng nguyên nhân. Code cụ
thể có thể theo taxonomy hiện hành, nhưng phải ổn định và được assert trong
negative test.

## Lowering và backend phải fail closed

Semantic fix là lớp phòng thủ chính, nhưng task chưa hoàn tất nếu malformed IR
vẫn có thể âm thầm trở thành địa chỉ `0`.

- AST-to-MIR chỉ được hạ identifier thành function address khi identifier đã
  resolve thành function/function value hợp lệ.
- MethodCall/UFCS chỉ được lower khi có resolved callee kind và identity.
- Nếu một node lỗi lọt tới lowering, compiler phải dừng có kiểm soát với
  internal diagnostic; không emit `0`, NOP hay artifact runnable.
- `MIR_INTR_ADDR_OF` phải phân biệt explicit null với unresolved symbol.
- Mỗi backend phải reject unresolved function address/call fixup. Không backend
  nào được silently materialize zero.
- Không thay segfault bằng runtime trap như giải pháp chính; source lỗi phải bị
  chặn trước code generation.

Nếu thêm MIR verifier, verifier phải chạy trên đường compile production và có
negative structural test. Một verifier không được gọi không tính là fix.

## Regression matrix bắt buộc

Thêm test tự động cho ít nhất các nhóm sau.

### Negative

1. Exact module-like receiver collision:
   `include net.url` + visible `parse` cùng arity + `url.parse(raw_uri)`.
2. Unknown receiver:
   `missing.process(x)` khi có visible `process(ptr, T)`.
3. Receiver type mismatch:
   receiver resolve được nhưng không tương thích first parameter.
4. Explicit argument type mismatch dù receiver hợp lệ.
5. Arity collision: nhiều bare-name candidate nhưng không signature nào hợp lệ.
6. Module tồn tại nhưng member không export.
7. Import alias/module short name trùng local/free function name.
8. Unresolved function address đi vào MIR verifier/backend guard phải fail
   deterministic, không tạo artifact.

Mỗi negative test phải assert:

- compiler exit khác `0`;
- diagnostic code và source location mong đợi;
- không có output artifact;
- process test không nhận signal `11`/exit `139`;
- behavior giống nhau ở `-O0`, `-O1`, `-O2`, `-O3` nếu các level này public.

### Positive

1. Direct `url_parse(raw_uri)`.
2. Free-function UFCS với receiver type chính xác.
3. Entity method đúng owner type.
4. Callable field đúng signature và không tự chèn receiver.
5. Builtin UFCS đang được hỗ trợ, gồm `.len()` nếu contract hiện hành cho phép.
6. Module import/include hợp lệ và exported symbol hợp lệ.
7. Chaining hợp lệ, receiver được evaluate đúng một lần.
8. Function value/address-of đã resolve vẫn lower và chạy đúng.

Giữ các regression hiện có như
`tests/bootstrap_codegen/cg_op_ufcs.vri` và
`tests/bootstrap_codegen/cg_array_len.vri`. Không dùng riêng happy path cũ làm
bằng chứng bug này đã được đóng.

## Phạm vi InterVir và lỗi không thuộc task

Sau compiler fix, chạy lại `server.vri` nếu checkout InterVir khả dụng. Acceptance
cho bug này là compiler từ chối source cũ và source đổi sang `url_parse` không
còn crash tại null buffer do call nhầm HTTP `parse`.

Nếu execution sau đó lộ crash khác trong middleware, ghi thành issue/repro riêng.
Không gộp một crash downstream vào root cause này và không tuyên bố nó do
`parse_into` nếu backtrace/call flow khác.

`parse_into` và helper có thể đang mutate `ValidatedRequest` qua tham số khai
báo `in`; audit đó là follow-up ownership/`ref` riêng trừ khi bằng chứng mới
chứng minh nó cần thiết để đóng chính repro này.

## Quy trình thực hiện

1. Capture baseline và tạo minimal reproducer trong test tree.
2. Xác nhận root cause ở pass 3, pass 6, AST-to-MIR và từng backend active.
3. Xác định representation riêng cho `unknown`, `error recovery`, `void/no
   value` nếu hiện đang bị gộp.
4. Sửa name/module resolution và UFCS candidate filtering trước.
5. Gắn resolved callee identity/signature vào node semantic.
6. Sửa lowering để chỉ nhận resolved call.
7. Thêm MIR/backend fail-closed guard.
8. Thêm toàn bộ negative/positive regressions.
9. Đồng bộ bundle từ modular sources và chạy check drift.
10. Rebuild compiler bằng workflow đang active của repo.
11. Chạy targeted tests, `./run_tests.sh min`, rồi `./run_tests.sh full` nếu
    không có blocker ngoài task.
12. Chạy self-host Stage 1 -> Stage 2 -> Stage 3 và xác nhận Stage 2/3 đạt
    fixed-point contract hiện hành; không tự phát minh command bootstrap.
13. Chạy lại InterVir E2E, LLDB/backtrace khi cần, và capture evidence.
14. Chạy `git diff --check` và rà soát diff chỉ chứa file thuộc task.

Không promote/replace `bin/virc` nếu regression hoặc fixed-point gate chưa đạt.

## Cấm tuyệt đối

- Không chỉ sửa `url.parse` thành `url_parse` rồi đóng compiler bug.
- Không special-case module `url` hay function `parse`.
- Không coi unknown/`Void` là tương thích để giảm diagnostic.
- Không chọn candidate theo bare name + arity.
- Không để unresolved receiver trở thành function address.
- Không materialize `0` khi symbol lookup thất bại.
- Không phát artifact sau semantic/lowering/backend unresolved-symbol error.
- Không đổi declaration/import order để né collision.
- Không xóa hoặc làm yếu các UFCS positive test.
- Không sửa trực tiếp generated bundle mà bỏ modular source.
- Không thay source/spec/test expectation để hợp thức hóa crash.
- Không tuyên bố hoàn tất chỉ vì server đi xa hơn rồi crash ở vị trí khác.

## Acceptance gates

Task chỉ hoàn tất khi có bằng chứng cho tất cả điều sau:

- minimal negative repro từng compile sai nay fail ở compile time;
- diagnostic chỉ đúng receiver/member và nguyên nhân module/value hoặc UFCS;
- không sinh executable cho repro;
- không còn đường semantic `unknown receiver -> resolved free UFCS`;
- không còn đường lowering `unknown identifier -> address-of -> zero` trên call
  path;
- mọi backend public reject unresolved symbol thay vì emit zero;
- direct `url_parse` và toàn bộ UFCS positive matrix pass;
- target test pass ở mọi optimization level public;
- bundle compiler không drift với modular source;
- `run_tests.sh min` pass;
- `run_tests.sh full` pass, hoặc blocker ngoài task được chứng minh bằng raw
  evidence và không liên quan diff;
- Stage 2 và Stage 3 đạt fixed point theo policy project;
- source InterVir cũ bị compiler từ chối;
- source InterVir dùng `url_parse` không còn segfault tại `parse_into` do null
  buffer từ call nhầm `parse`;
- không có thay đổi ngoài phạm vi task.

## Báo cáo bàn giao bắt buộc

Báo cáo cuối phải có:

- root cause theo từng tầng: parser/name/module resolution, type/UFCS semantic,
  AST-to-MIR, LIR/backend;
- giải thích ngắn vì sao compiler cũ không chặn lỗi;
- diagnostic contract cuối cùng;
- representation resolved callee và unknown/error type cuối cùng;
- danh sách file sửa/thêm;
- raw command, stdout, stderr, exit code và compiler hash cho baseline và sau
  fix;
- kết quả từng negative/positive fixture ở các optimization level;
- bằng chứng không sinh artifact cho negative test;
- kết quả `sync_virc.py --check`, targeted tests, min/full suite và fixed point;
- kết quả InterVir request đầu tiên sau fix;
- blocker, backend hoặc gate nào chưa chạy được.

Không ghi “đã hoàn thành” nếu compiler vẫn có thể biến bất kỳ unresolved
receiver/callee nào thành địa chỉ `0` và sinh binary runnable.
