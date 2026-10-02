# Kế hoạch triển khai và nghiệm thu

Trạng thái hiện tại: chỉ có đặc tả. Toàn bộ gate dưới đây chưa được thực hiện.
Yêu cầu chi tiết giữ ở [bản gốc](USER_REQUIREMENTS.md); các điều chỉnh ngữ nghĩa
và boundary được quy định trong [kiến trúc](ARCHITECTURE.md).

## Giai đoạn 1 — Bridge và protocol

Pin compiler revision chứa semantic bridge; chốt schema version và origin map.
Prototype adapter dùng core hiện có, không fork checker. Xây transport,
lifecycle, document overlay, snapshot, cancellation và bounded scheduler.
Gate: JSON-RPC transcript, UTF-16/Unicode/CRLF, open/change/close, disk overlay,
malformed input, stale versions và worker failure đều có expected response.

## Giai đoạn 2 — Syntax và semantic baseline

Recovery parser, scopes/types/symbol/reference index; hover/completion/signature,
navigation, outline, references và semantic rename. Add resolution/export
integration theo compiler, không tạo resolver riêng.
Gate: shadowed names, same basename modules, lazy dependencies, include/import
identity, missing/private export, missing import, public API và broken function
không ảnh hưởng declaration hợp lệ khác. Rename không sửa symbol trùng tên.

## Giai đoạn 3 — Ownership và Vir graphs

Expose program-point lifetime, projection borrows, move/copy flow, region
promotion và cleanup provenance. Implement custom extension negotiation,
bounded graph responses và version-safe diagnostics.
Gate: positive/negative contract fixtures dùng cùng compiler oracle; owned
escape hợp lệ, borrowed escape lỗi, move tại branch join, loop last-use,
sub-arena promotion và throw/revert/ensure cleanup. Không sửa oracle để chiều
implementation thiếu hỗ trợ. Unknown states phải có test riêng.

## Giai đoạn 4 — Feature completion và incremental engine

Semantic tokens/delta, inlay hints, call hierarchy, safe code actions, formatting,
range selection/folding; module signature invalidation và persistent index.
Gate: đổi body không invalidate workspace khi dependency proof cho phép;
đổi inferred/exported signature cập nhật consumers. Cold/warm parity;
cancellation không làm hỏng cache; compiler/config change xoá index không hợp lệ.

## Definition of Done

Mỗi feature trong yêu cầu gốc phải có implemented source, advertised capability,
executed test và giới hạn được ghi trong status trước khi đánh dấu hoàn tất.
Baseline gồm diagnostics syntax/name/type/module/borrow/move/arena, imports và
visibility, completion/hover/signature, navigation/references/rename, symbols,
tokens/hints, call hierarchy/actions, read/write/borrow/move classification,
activation, lifetime/borrow/arena/value-flow APIs, incremental analysis,
cancellation, recovery và version safety. Formatting/implementation navigation
cũng phải có test hoặc explicit unsupported status.

Compiler và LSP phân tích cùng snapshot/config phải thống nhất code, location,
root cause và semantic facts. Chạy replay rapid edits với diagnostics cũ;
đo P50/P95/P99 và memory theo architecture budgets. Green core unit tests
không thay thế end-to-end protocol/client tests. Release chưa được coi ready
nếu chỉ có tài liệu hoặc stub capabilities.
