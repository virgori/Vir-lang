# Vir Language Server — Đặc tả kiến trúc

Ngày: 2026-10-01. Trạng thái: thiết kế đề xuất, chưa triển khai trong repository này.
Tài liệu chuẩn cho thiết kế `vir-lsp`; yêu cầu gốc nằm ở
[USER_REQUIREMENTS.md](USER_REQUIREMENTS.md). Các schema dưới đây là mô hình
thiết kế, không phải cú pháp Vir hoặc API hiện có.

## 1. Mục tiêu và thẩm quyền

`vir-lsp` là giao diện realtime của semantic engine Vir: cùng name resolution,
type system, ownership, move, borrow, arena, visibility và diagnostic với
`virc`. Extension editor chỉ render dữ liệu và gửi thao tác, không suy luận
semantic state độc lập. Server không chạy code người dùng để phân tích.

Language spec Vir là thẩm quyền về ngữ nghĩa. Compiler implementation và test
cho biết khả năng hiện có. Thiếu capability phải trả unknown/unsupported,
không suy đoán kết quả hoặc thay đổi spec cho phù hợp editor.

Source language server nằm tại `vir-lsp/` trong repository Vir và dùng chung
history với compiler. Không sao chép type checker, borrow checker hoặc resolver
sang một bản riêng trong server. Không có dependency ngầm vào working directory;
đường dẫn compiler/sysroot được cấu hình và xác thực trước analysis.

## 2. Luồng kiến trúc

```text
Editor → Protocol/Transport → Workspace + Source DB (overlay)
                                  │
                         Incremental Syntax
                         Lexer → Recovery Parser → AST
                                  │
                  Shared semantic core / compiler adapter
                                  │
        Symbol · Scope · Type · Module · Reference · Call
                   Ownership · Borrow · Lifetime · Arena
                                  │
                         Incremental Query Engine
                                  │
                  LSP features + vir/* extensions
```

`vir-core` là tên cho ranh giới dùng chung được đề xuất, chưa khẳng định tồn tại
một module như vậy. Shared core cung cấp syntax và semantic model; compiler
có thể tiếp tục HIR/MIR → LIR → RA → codegen. LSP dừng ở semantic facts cần
cho truy vấn. Đặc tả không bắt compiler đổi đường lowering hay bắt HIR thành
nhánh mặc định. Nếu một fact cần analysis sâu hơn, adapter yêu cầu fact đó,
không sinh executable chỉ để trả hover.

## 3. Ranh giới thành phần

Cấu trúc triển khai dự kiến:

```text
protocol/    framing, JSON-RPC, lifecycle, capabilities, cancellation
workspace/   source_db, URI/path identity, file events, module graph
syntax/      adapter lexer/parser, recovery, syntax anchors
semantic/    adapter shared core, symbols, scopes, types, visibility
ownership/   adapter facts lifetime/borrow/move/arena từ compiler
analysis/    queries, invalidation, diagnostics, reachability, scheduler
features/    standard LSP handlers
extensions/  vir/lifetime, borrowGraph, valueFlow, arenaGraph,
             symbolState, moduleGraph, callGraph
```

Đây là layout đề xuất, không phải module resolver map. Các adapter không được
cài đặt luật ngôn ngữ riêng. Extraction hoặc bổ sung compiler API là công việc
triển khai sau, cần review riêng và compatibility test với compiler.

## 4. Source DB và snapshot

`SourceFile` gồm FileId, canonical URI, clientVersion, contentHash, immutable
text, lineMap, tokenTree, syntaxTree, originMap và trạng thái open/closed.
Nội dung chưa lưu trong editor là overlay có ưu tiên hơn disk. Đóng document
loại overlay và tái phân tích nội dung disk hoặc loại file nếu đã bị xoá.

Một `AnalysisSnapshot` mang workspaceRevision, file versions/hashes,
module/config revision, compiler identity, target và semantic schema version.
Mỗi request giữ một snapshot bất biến. Query không trộn facts từ hai revision.
Disk event không được ghi đè buffer đang mở. Các edit liên tiếp được áp dụng
đúng thứ tự; không dùng diagnostic hoặc edit từ snapshot cũ lên text mới.

Compiler byte offsets phải chuyển qua lineMap theo position encoding đã
negotiated với client; UTF-16 là fallback tương thích. Test phải bao gồm Unicode,
emoji, CRLF và end-of-file. originMap trả vị trí file gốc khi compiler mở rộng
include; không trả line trong generated bundle cho editor.

## 5. Incremental syntax và recovery

Lexer invalidates từ safe token boundary, đặc biệt khi edit string/comment.
Parser giữ lossless syntax/CST và AST projection có Missing/Error nodes để
không mất comment, trivia hoặc vùng còn hợp lệ. Recovery tại delimiter và
boundary của declaration; luôn tiến tới token tiếp theo để tránh loop vô hạn.
Không dùng regex để dựng semantic tree.

Một function lỗi không làm mất các declaration hợp lệ khác. Nếu shared parser
chưa recovery được, đây là gap cần bổ sung tại shared core; không viết parser
semantic thứ hai cho editor. Giai đoạn đầu được phép parse lại file bị sửa,
nhưng không được quảng cáo incremental node parsing trước khi có test.

## 6. Identity và các database

Identity gồm FileId, NodeId, SymbolId, TypeId, ScopeId, ModuleId, ArenaId và
BorrowId. ID có namespace workspace/session và generation. Syntax anchor giúp
reconcile declaration qua edit không liên quan; rename hoặc declaration bị
xoá có thể cấp ID mới. Không hứa ID bất biến xuyên mọi edit. Persistent index
chỉ phục hồi ID khi compiler/schema/config/content hash tương thích.

Symbol DB giữ name, kind, declaration/definition spans, module, scope, TypeId,
visibility và export/import provenance. Kinds gồm module, namespace, entity,
type, function, method, parameter, variable, constant, field, enum, generic.
Reference DB giữ SymbolId, span và kind: declaration, type, read, write,
readWrite, sharedBorrow, mutableBorrow, move, consume, call, import, export.
Find references và rename dựa identity, không search text theo tên.

Scope graph giữ parent, children, range và bindings. Type DB dùng canonical
TypeId cho primitive/entity/generic/function/reference/tensor/SIMD/inferred;
ErrorType và UnknownType truyền uncertainty, không so sánh type bằng chuỗi
hover. Generic instances chứa base TypeId và argument TypeIds.

Module graph giữ canonical identity, include/import edges, export set,
public signature hash và reverse dependencies. Call graph giữ call sites,
callers/callees, root classification và unresolved indirect edges. Unknown
callback target không đồng nghĩa unreachable.

## 7. Ownership, lifetime và arena

Lifetime fact gắn với symbol/value instance, projection và program point,
không chỉ một state toàn cục cho tên biến. Fact gồm initialization, owner,
region/epoch, read/write, move, borrow và invalidation sites, cleanup boundaries
và provenance. State query là `stateAt(symbol, position, snapshot)`.

Các trạng thái presentation: declared, uninitialized, active, sharedBorrowed,
mutBorrowed, moved, consumed, invalidated, outOfScope, freed; thêm unknown và
maybeMoved cho incomplete code hoặc control-flow join. Borrow state là fact
trực giao với initialization/ownership. Sau nhánh chỉ move một phía, không
được khẳng định value chắc chắn active hoặc chắc chắn moved.

Borrow graph lưu owner projection, borrower, kind, start/end, CFG liveness và
conflict evidence. Shared borrows có thể cùng tồn tại; mutable borrow phải
exclusive. End borrow theo last-use proof của core, không theo vị trí dòng
đơn giản. Diagnostic kèm owner, borrow origins, conflicting operation và boundary.

Arena graph lưu parent/child, creation/reset/destruction, region epochs và
allocation/value membership. Phải phân biệt:

- Owned value rời scope bằng move hoặc `out`: hợp lệ khi complete owned graph
  được đặt/promote vào region đủ dài theo contract compiler.
- Borrow rời lifetime owner: lỗi; raw pointer không kéo dài lifetime.
- Promotion chưa được compiler hỗ trợ hoặc fact thiếu: nêu gap/unknown,
  không báo mọi owned escape là vi phạm ngôn ngữ.

Cleanup facts phải phản ánh fallthrough, break, skip, out, throw, revert và
ensure. Static lifetime boundary không phải đo runtime free chính xác; heap
size và thời điểm runtime release chưa biết phải ghi unknown. Value flow
phân biệt copy, move, consume, borrow và projection theo type/ownership facts.

## 8. Module resolution, visibility và activation

Dùng chung resolver/compiler registry, project module mapping khi có, canonical
path identity, deduplication và cycle policy. Không hardcode module/API từ ví dụ.
Dependency scanner chỉ cung cấp candidate edges; core xác nhận nghĩa thực.
Phân biệt missing module, missing export, private symbol và unknown do lỗi syntax.
Auto-import tìm exported symbols trong verified index và dùng spelling hợp lệ
của resolver; không thêm include dư khi import đã đủ.

Không mặc định mọi cycle đều lỗi: lazy type dependency phải theo spec. Không
xoá include chỉ vì không thấy reference nếu còn initialization/effect hoặc
resolution chưa đầy đủ. Public/exported APIs, entrypoints, test roots và FFI
callbacks không bị coi dead vì thiếu local caller. Activation/reachability và
lifetime-active là các chiều khác nhau, không dùng chung một boolean `active`.

## 9. Query engine, invalidation và scheduling

Query key gồm query kind, identity, snapshot dependency stamps, target/options
và compiler/schema version. Query ghi dependency read-set; memoization chỉ hợp
lệ khi các stamps còn khớp. Cycles được phát hiện và resolve bằng shared core
policy, không chờ lẫn nhau vô hạn.

Edit local body invalidates syntax region và semantic consumers bị ảnh hưởng;
public signature/export change invalidates reverse module dependencies.
Registry/config/sysroot/target change invalidates resolution và downstream facts.
Một function body change vẫn có thể ảnh hưởng inferred public type hoặc effects;
không giới hạn invalidation bằng heuristic “body-only” khi chưa có proof.

Fast path: syntax, scope, local names/types cho hover, completion, definition,
signature và tokens. Deep path: type/borrow/arena/CFG, unused, reachability sau
configurable debounce hoặc save. Fast path chưa có borrow facts phải ghi
pending/unknown; không render moved dựa token.

Scheduler ưu tiên interactive requests, coalesce superseded revisions, có
cancellation checkpoints và bounded work queue. Cancellation không publish
partial cache entry. Snapshot cũ bị loại trước publishDiagnostics; workspace
revision và dependency revisions cũng phải khớp, không chỉ file version.

## 10. Protocol và feature contracts

Chuẩn tham chiếu: [LSP 3.17](https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/).
Transport stdio dùng JSON-RPC framing; stdout chỉ dành protocol, log ở stderr.
Capability chỉ advertise khi handler đã có validation. Lifecycle bao gồm
initialize, initialized, shutdown và exit; malformed message không làm hỏng
workspace state.

Feature baseline từ yêu cầu gốc gồm synchronization, diagnostics, completion
và resolve, hover, signature help, declaration/definition/typeDefinition/
implementation, references, documentHighlight, document/workspace symbols,
prepareRename/rename, codeAction, semantic tokens, inlay hints, call hierarchy,
folding/selection range và document/range formatting.

Completion xếp local, parameters, members, same module, imports, dependencies,
auto-import rồi workspace candidates; dùng fuzzy ranking trong từng nhóm.
Signature help dùng resolved callable và active parameter. Navigation và
reference query dựa identity; document highlight dùng read/write kinds client
hỗ trợ, borrow/move detail qua extension. Rename preview phải re-resolve và
phát hiện scope collision, shadowing, visibility và affected file versions.

Formatting dựa lossless syntax, preserve comments và block closing; broken
range không đủ structure phải từ chối hoặc chỉ format vùng an toàn. Code Lens,
workspace diagnostics, workspace folders/file operations và linked editing là
capability mở rộng triển khai sau. Client không hỗ trợ custom metadata vẫn
nhận feature LSP cơ bản.

## 11. Diagnostics và code actions

Giữ code/message/severity từ compiler, source `virc`, map location về source
và thêm relatedInformation có provenance. Không áp nhóm E1xxx…E7xxx trong bản
yêu cầu gốc thành registry mới: registry compiler hiện tại phân loại khác.
Protocol error code và language diagnostic code có namespace riêng.

ErrorType/poisoned expressions suppress cascading errors nhưng giữ lỗi độc lập.
Missing facts không được biến thành diagnostic chắc chắn. Push diagnostics
mang document version; pull diagnostics nếu triển khai dùng resultId gắn snapshot.
Close/remove document phải clear diagnostics đúng URI.

Code actions: import/include, unused include, export/visibility, explicit type,
create declaration/module và borrow fixes chỉ được đề xuất khi core/index có
đủ evidence. Không tự thêm clone/copy, đổi ownership hoặc di chuyển mutation
khi thay đổi observable behavior chưa được chứng minh. Mọi sửa đổi là preview
WorkspaceEdit có version guard; dependency read-only không được sửa tự động.

## 12. Semantic presentation và Vir extensions

Semantic token legend negotiated với client. Standard token kinds là baseline;
Vir modifiers như moved, consumed, borrowed, arenaOwned, reachable và exported
là custom legend entries, không giả định editor nào cũng render. Delta token
result chỉ dùng trên đúng previous resultId. Inlay hints và lens mặc định gọn,
không hiển thị kích thước allocation chưa được core xác định.

Custom methods đề xuất: `vir/lifetime`, `vir/borrowGraph`, `vir/valueFlow`,
`vir/arenaGraph`, `vir/symbolState`, `vir/moduleGraph`, `vir/callGraph`.
Negotiation qua experimental capability `vir` có schemaVersion và methods.

Request envelope: textDocument URI, expectedVersion, position khi áp dụng,
query-specific stable identity tùy chọn, maxNodes và continuationToken.
Response envelope: schemaVersion, snapshotId, documentVersion, status
(complete/partial/unknown), reason, nodes/edges hoặc state, source spans,
provenance và nextToken. Version mismatch dùng ContentModified theo protocol;
unknown semantic fact trả unknown với reason, không tự tạo state. Pagination
bị ràng buộc snapshot; continuation hết hạn yêu cầu query mới.

`vir/symbolState` trả type, visibility, reachability, ownership,
initialization, borrow state, move site, arena và scope dưới các trường riêng.
Graph edges gắn reference kind/program point; UI không suy ra facts từ màu.

## 13. Memory, isolation và an toàn workspace

Snapshot/cache bounded, version-aware, dependency-aware và evictable. Giữ
open/visible/recent files trước dependency interfaces và workspace index;
không giữ mọi historical tree. Request sống pin snapshot; eviction chờ release.
Unknown/crashed function chỉ poison facts phụ thuộc, không dùng stale facts như
current. Worker crash trả lỗi có kiểm soát và không restart loop vô hạn.

Phân tích offline, không tự tải package hoặc chạy build script. Canonical URI
và symlink policy theo resolver/workspace roots; navigation có thể đọc dependency
được cấu hình nhưng edits chỉ vào writable workspace. Giới hạn message size,
graph output và parse depth để tránh request làm server treo.

## 14. Performance và chứng cứ nghiệm thu

Budget đề xuất từ yêu cầu gốc: hover/definition dưới 30 ms; completion/signature
help dưới 50 ms; incremental syntax dưới 20 ms; local diagnostics dưới 100 ms.
Đây là mục tiêu, không phải số đo hoặc hard guarantee. Đo P50/P95/P99, peak RSS,
cache hit/miss và invalidated nodes trên workspace nhỏ/lớn, cold/warm session,
Unicode, broken code, rapid edits và module signature changes. Ghi hardware,
OS, compiler commit, protocol trace, debounce và concurrent load.

Latency đo từ nhận request đến response, tách deep debounce và core CPU time;
không loại queueing khỏi end-to-end headline. Memory đo bounded steady state
sau nhiều edit/close/cancel cycles. Chưa có benchmark trong repository này.

## 15. Hiện trạng đã quan sát và điểm tích hợp

Tại thời điểm viết, repository cha có các source dưới đây. Đây là inventory
source, không phải kết quả chạy test hay chứng nhận baseline-complete:

- `stdlib/vir/lsp/lsp.vri`: file tự mô tả là stub; không coi capabilities trong
  stub là proof server hỗ trợ đầy đủ.
- `stdlib/vir/compiler/ide_semantic.vri`: IDE snapshot buffers, states và symbol/
  call/module records; là candidate bridge, chưa chứng minh stable query API.
- `stdlib/vir/compiler/sem_pass_ide.vri`: thu thập modules, usage/reachability.
- `stdlib/vir/compiler/semantic.vri`, `symbol_table.vri`, `scope_tree.vri`,
  `type_table.vri`, `sem_pass8_borrow.vri`: semantic evidence cần adapter.
- `stdlib/vir/compiler/source_manager.vri`: source-origin mapping candidate.
- `stdlib/vir/compiler/error_codes.vri`: registry diagnostics hiện có.
- `tests/memory_contract/README.md`: ownership/borrow/arena contract oracle.

Một số file IDE đang là thay đổi local chưa commit ở repository cha. Implementation
phải pin compiler revision có đủ source; không dựa HEAD hash như bằng chứng
cho các file local đó. Không có compiler ABI pin hoặc integration build ở repo
này. Không migrate hay sửa bất kỳ file nào của compiler trong tác vụ đặc tả.

## 16. Quyết định còn mở

Shared core packaging/embedding hay worker IPC cần prototype và đo isolation/
latency trước khi chốt. Schema export từ compiler, stable anchor reconciliation,
cache format và exact capability rollout chưa có implementation contract.
Các tên component/query trong tài liệu là proposal, không phải exported Vir API.
Xem [kế hoạch nghiệm thu](IMPLEMENTATION_PLAN.md) để triển khai theo evidence.
