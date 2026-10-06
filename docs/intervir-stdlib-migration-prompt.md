# Prompt: hoàn tất phân lớp InterVir ↔ Vir stdlib

Làm việc trong hai checkout:

- Vir và stdlib: `/Users/gengyang/Vir-3.0`
- InterVir: `/Users/gengyang/Desktop/Repo/intervir`

Mục tiêu: mọi chức năng thư viện tổng quát phải có một implementation chuẩn trong Vir stdlib; InterVir chỉ giữ phần tích hợp HTTP, middleware, runtime và framework. Tiếp tục audit, chuẩn hoá và migrate code theo bằng chứng thực tế, không coi việc chuyển file là đã hoàn tất API migration.

## Nguồn sự thật bắt buộc

1. Đọc `module.list` đang hoạt động của InterVir để lấy **đúng Module ID InterVir**.
2. Đọc `stdlib/stdlib.vri` để lấy **đúng Module ID và đường dẫn source stdlib**. Không suy ra tên module từ tên thư mục, không tự tạo alias hoặc prefix như `protocol.*`.
3. Đọc source, `export` và test của từng API trước khi đổi caller. Checkout `Repo` có thể chưa đồng bộ với stdlib; không giả định hai bản có cùng API hoặc semantic.
4. Đọc `stdlib/registry/SCHEMA.md` trước khi tạo hoặc sửa bất kỳ Markdown registry nào. `stdlib.vri` là registry ánh xạ module → file; `stdlib/registry/*.md` là hợp đồng **public API**, không được thay thế cái này bằng cái kia.
5. Bảo toàn toàn bộ thay đổi đang có ở cả hai worktree. Không reset, xoá, ghi đè, commit hoặc push thay đổi ngoài phạm vi được yêu cầu.

## Quy tắc phân lớp và quyết định

- Cái gì dùng được độc lập ngoài InterVir (JSON, env, data, DB, wire protocol, MIME, v.v.) thì thuộc stdlib. Cái gì phụ thuộc vòng đời ứng dụng/worker, dispatch, routing, middleware policy, ingress hoặc orchestration thì ở InterVir. Nếu stdlib đang host chức năng tầng framework, ghi rõ vi phạm ranh giới và đề xuất vị trí đúng; không lặng lẽ chuyển ngược hay xoá.
- Nếu chỉ InterVir có thư viện tổng quát: so sánh với các module stdlib liên quan, thiết kế API chuẩn rồi chuyển implementation vào stdlib khi đã qua các gate bên dưới.
- Nếu cả hai có: so sánh logic, edge case, an toàn bộ nhớ, giới hạn và test. Giữ hoặc hợp nhất phần hoàn thiện hơn tại **stdlib**; không duy trì hai semantic implementation.
- Nếu stdlib đã có API chuẩn: đổi caller InterVir sang bản chuẩn và xoá implementation trùng sau khi xác minh tương đương. Vẫn dùng `include <Module ID>` đúng theo registry; không tự đổi thành `import`, không sáng tác Module ID mới.
- **Chỉ migrate caller sau khi stdlib có public API dot-style đã đăng ký, export, compile và được test bằng lời gọi thực tế.** Hàm tự do `snake_case` không đủ điều kiện. Helper nội bộ có thể còn snake_case, nhưng không được quảng bá nó là public API đã chuẩn hoá.
- Nếu stdlib chưa chuẩn hoá registry, còn alias trùng, thiếu export, API mới chỉ là tên dự kiến, không compile, hoặc semantic chưa khớp: ghi blocker cụ thể và **chưa di chuyển thêm caller/module đó**. Không bọc tên mới quanh code lỗi để đánh dấu “xong”.
- Các file đã được chuyển vật lý ở lượt trước nhưng chưa đạt dot-style vẫn là **migration chưa hoàn tất**. Kiểm tra lại từng file; chuẩn hoá và kiểm thử hoặc nêu rõ vì sao phải tạm giữ/hoàn nguyên. Không báo cáo chúng là hoàn tất chỉ vì `stdlib.vri` đã có entry.

## Bắt buộc viết Markdown registry cho mỗi thư viện được chuyển hoặc chuẩn hoá

Trong **cùng thay đổi** với source/API/registry, tạo hoặc cập nhật tài liệu đúng namespace tại `stdlib/registry/<namespace>.md`, tuân thủ toàn bộ `stdlib/registry/SCHEMA.md`. Không gom tất cả vào một báo cáo audit thay cho registry.

Với mỗi module/public API đã chuyển hoặc chuẩn hoá, Markdown registry phải có:

1. Front matter `module`, `title`, `summary`, `source` (Module ID **đúng theo `stdlib.vri`** và đường dẫn source thật), `status`; tên file phải khớp `module`.
2. Ranh giới: thư viện chuẩn sở hữu logic nào, InterVir còn adapter/framework nào, và module nào chỉ là nội bộ. Nếu module nội bộ không có namespace public riêng, cập nhật registry Markdown của namespace chủ quản; **không bịa một public API** chỉ để có file Markdown.
3. `## Migration map` khi đang tái cấu trúc: tên cũ → tên dot-style, signature, source, hành động và trạng thái. Hoàn tất map trước khi đổi tên `.vri`.
4. `## API` index cho mọi entry public đã công bố. Mỗi row phải có section chi tiết cùng stable ID/anchor, signature Vir thật, semantic, parameters, returns, errors và example hợp lệ theo schema.
5. Trạng thái trung thực: `stable` chỉ khi tên, export, semantic và test đều khớp; dùng `draft`, `proposed`, `planned`, `incomplete` hoặc `deprecated` khi còn gate. Không đánh dấu `stable` chỉ vì `virc --check` qua.
6. Ghi rõ compatibility alias còn tồn tại, alias đã bỏ, giới hạn, khác biệt semantic và test chứng minh migration. Không ghi symbol chưa có trong source như API đã phát hành.

Áp dụng lại yêu cầu này cho **những module đã chuyển/chuẩn hoá trong các lượt trước**, không chỉ module mới xử lý. Lấy danh sách thực tế bằng diff giữa `module.list`, `stdlib.vri`, source và test. Các ID đã thấy ở stdlib để bắt đầu rà soát gồm `memory.slice`, `http.types`, `http.status`, `http1.parser`, `http1.serializer`, `binding.form`, `binding.multipart`, `binding.query`, `static.mime`, `static.etag`, `realtime.sse`, `proxy.protocol`, `json.slice`, `http2.frame`, `http2.hpack`, `http2.stream`, `http2.session`; **phải xác minh lại** từng ID và mức độ hoàn tất, không dùng danh sách này thay registry.

## Trình tự triển khai

1. Chụp baseline đọc-only: `git status`, hai registry, source/export, tests; lập danh sách overlap và phân loại stdlib / InterVir / chưa quyết định.
2. Với từng module, so sánh behavior và xác định public dot-style contract. Viết/cập nhật Markdown registry và migration map theo schema trước khi rename source.
3. Sửa canonical stdlib source và `stdlib.vri`; kiểm tra duplicate key, alias/path trùng, path thiếu và dependency cycle. Thêm positive test gọi API dot-style cùng negative/edge tests thích hợp. Với API pointer/buffer, kiểm tra bounds, ownership và lifetime trước khi công bố.
4. Khi stdlib qua gate, đổi caller InterVir bằng `include` đúng Module ID; cập nhật `module.list` trong cùng thay đổi nếu thực sự di chuyển hoặc xoá module InterVir. Không để InterVir giữ bản sao thư viện tổng quát.
5. Chạy compiler và test tập trung **trước và sau** mỗi nhóm thay đổi; kiểm tra cả behavior, không chỉ exit code của `--check`. Không sửa lỗi không liên quan để che regression. Nếu một file đã lỗi từ trước, tách rõ baseline và lỗi mới.
6. Đối chiếu cuối: mọi module đã chuyển/chuẩn hoá đều có source, registry mapping, Markdown registry đúng schema, explicit public API, test và caller migration tương ứng. Mọi blocker còn lại có file/dòng, lỗi compiler hoặc khác biệt semantic cụ thể.

## Kết quả phải bàn giao

- Danh sách module **đã hoàn tất**, **đã chuyển vật lý nhưng chưa hoàn tất API**, **giữ ở InterVir**, và **bị chặn**; mỗi mục nêu Module ID từ registry, lý do và đường dẫn tài liệu `stdlib/registry/*.md` liên quan.
- Các API cũ → mới đã đổi trong caller; các lời gọi còn dùng snake_case và lý do chưa đổi.
- Test/command đã chạy, kết quả, regression hoặc giới hạn chưa xác minh.
- Diff các file registry Markdown đã tạo/sửa. Không tuyên bố “migration xong” nếu thiếu bất kỳ gate nào ở trên.
