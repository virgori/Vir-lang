# Prompt nghiêm ngặt: FFI `extern from` end-to-end trên mọi target công khai

## Mục tiêu

Bạn là compiler/linker engineer của Vir. Hoàn thiện dynamic extern import trên
**pipeline active** cho **mọi target mà driver `virc` công khai nhận**, không
chỉ host Mach-O ARM64. Mỗi artifact do `bin/virc` mới sinh phải được loader
của target bind đúng external symbol, thật sự gọi external function, in kết
quả đúng và thoát với exit code `0`.

Đây không phải task “có sections Mach-O”, “otool nhìn thấy `LC_LOAD_DYLIB`”,
hay “compiler compile thành công”. Đó chỉ là kiểm tra trung gian.

## Hiện trạng tái hiện được

Source regression hiện có:

```vir
extern from os func getpid() -> int
extern from "/usr/lib/libSystem.B.dylib" func getuid() -> int

func main:
    let pid = getpid()
    if pid > 0 do
        print "PASS: ffi extern getpid verified"
    end
end.
```

Lệnh hiện tại:

```sh
./bin/virc tests/test_extern_from_os.vri -o /private/tmp/virc_ffi_e2e
/private/tmp/virc_ffi_e2e
```

Luôn chạy lại repro trước khi sửa và ghi output thật; **không** tin một claim
PASS/FAIL cũ hay chỉ output compile. Với Mach-O, artifact phải có metadata
động nhất quán như `__stubs`, `__la_symbol_ptr`, bind data và
`LC_LOAD_DYLIB`; các dấu hiệu đó vẫn không thay thế execution E2E.

## Nguồn sự thật và phạm vi

1. Đọc parser, `ast_to_mir`, `ffi_imports`, LIR codegen và `macho.vri` trước
   khi sửa. Đây là các file active; không chỉ sửa `virc_stage1.vri` hoặc binary
   prebuilt.
2. Giữ public syntax:

   ```vir
   extern func getpid() -> int
   extern from os func getpid() -> int
   extern from "/absolute/path/libX.dylib" func symbol() -> int
   ```

   `extern func` là compatibility spelling của `extern from os`.
3. Registry import phải target-neutral; format-specific writer chỉ consume
   import đã được gọi. Không gắn field Mach-O vào parser/AST/MIR.
4. Với Mach-O ARM64, hoàn thiện mọi phần cần thiết: callable stub, relocation/
   binding opcode hoặc chained fixup hợp lệ, lazy symbol pointer, indirect
   symbols, undefined external `nlist`, dylib ordinal và load command, section
   offsets/VM addresses, entrypoint và ABI call/return convention.
5. Chọn **một** cơ chế dyld hợp lệ và implement nhất quán. `LC_DYLD_INFO_ONLY`
   là chấp nhận được nếu bind stream đúng; không ghi “chained fixups” nếu binary
   không phát `LC_DYLD_CHAINED_FIXUPS` hợp lệ.
6. Không làm regress local call, syscall/runtime stubs, static executable,
   hoặc bất kỳ target public nào. Không target nào được phép chỉ có metadata.

## Ma trận target bắt buộc

Chốt ma trận từ driver active (`virc --help`, parser `--target` và
`target_triple.vri`) trước khi sửa; không tự thu hẹp ma trận để task dễ pass.
Ở tree hiện tại, các target công khai tối thiểu là:

| Target | Artifact/import thực sự phải hoàn thiện | Bằng chứng runtime bắt buộc |
|---|---|---|
| `macos-arm64` | Mach-O ARM64: dyld bind, stub/pointer, undefined symbol và `LC_LOAD_DYLIB` | Chạy native trên macOS ARM64 hai lần |
| `linux-arm64` | ELF AArch64: dynamic symbol, relocation/PLT-GOT (hoặc cơ chế ELF tương đương), `DT_NEEDED` | Chạy native hoặc QEMU/container AArch64 |
| `linux-x86_64` | ELF x86-64: dynamic symbol, relocation/PLT-GOT (hoặc cơ chế ELF tương đương), `DT_NEEDED` | Chạy native Linux x86-64 container/runner |
| `linux-riscv64` | ELF RISC-V 64: dynamic symbol, relocation/PLT-GOT (hoặc cơ chế ELF tương đương), `DT_NEEDED` | Chạy QEMU hoặc runner RISC-V 64 |
| `wasm32-wasi-p1` | Wasm import section và ABI call đúng theo runtime WASI/module host được chọn | Chạy bằng WASI runtime/module host thật |

Nếu driver sau khi rà soát công khai thêm Mach-O x86-64, PE/COFF hoặc target
khác, target đó tự động vào ma trận: phải có importer/linker/ABI/runtime test
tương ứng. Không được ghi "future", "metadata-only", hay bỏ target khỏi
matrix trong khi driver vẫn nhận nó.

## Cấm tuyệt đối

- Không thay `getpid()` bằng syscall nội bộ, constant, local function, hoặc
  pre-print `PASS`.
- Không dùng `clang`, `ld`, `dyld` wrapper hay binary cũ để tạo/chạy artifact
  chứng minh. Artifact phải do `bin/virc` sau sửa tạo trực tiếp.
- Không sửa test để bỏ lời gọi extern, chỉ kiểm tra metadata, hay chấp nhận
  `pid > 0` mà không thực thi nhánh output.
- Không chỉ thêm `LC_LOAD_DYLIB`/`__stubs` cho đẹp; dyld binding và `BL` qua
  stub phải thực sự hoạt động.
- Không reset/restore thay đổi người dùng, không claim cross-target E2E khi
  chưa có format emitter, loader binding và runtime test cho **từng** target.
- Không dùng compile/link, `readelf`/`otool`, Wasm validation, hoặc
  cross-compile thành công làm thay cho chạy artifact của target.

## Test bắt buộc

1. E2E primary cho từng dòng trong ma trận: compile source extern tương đương
   vào đường dẫn tạm bằng `--target` cụ thể, chạy **chính artifact đó** trong
   native runner/emulator/WASI runtime của target, assert exact stdout
   `PASS: ffi extern getpid verified\n` (hoặc marker target được chỉ rõ) và
   exit code `0`. macOS ARM64 dùng `tests/test_extern_from_os.vri`; các target
   khác phải thêm fixture target-appropriate nhưng vẫn gọi extern thật.
2. Bổ sung regression không thể bị giả mạo: lưu kết quả `getpid()` và xác thực
   `pid > 0`; nếu assertion fail, trả exit code khác 0. Thêm ít nhất một call
   extern thứ hai hoặc một đường test khác để bắt lỗi ordinal/indirect-symbol
   indexing nhiều import.
3. Kiểm tra binary artifact với `otool -l`, `nm`/`dyld_info` khi có sẵn:
   dylib path, undefined `_getpid`, stub/pointer section và cơ chế bind phải
   phù hợp chính xác với implementation.
4. Regression local calls và extern declaration chưa được gọi: local call vẫn
   chạy, unused extern không sinh import binding/stub.
5. Chạy từng target ít nhất hai lần từ clean temporary output path để loại trừ
   dùng nhầm binary cũ hoặc cache. Lưu raw command, stdout, stderr, exit code,
   target triple, runner/emulator version và inspection artifact tương ứng.

## Cổng nghiệm thu end-to-end — không ngoại lệ

Chỉ đánh dấu hoàn thành khi **mọi** target trong ma trận đều có hai lần chạy
artifact mới sinh, exact stdout PASS và exit code `0`. Compile-success,
inspection Mach-O/ELF/Wasm, code signing, parser/AST test, hoặc binary có sẵn
không đủ. Nếu một target crash, bị kill, im lặng, không bind/import được, hoặc
chưa có runner để chạy, task là **incomplete/blocked cho toàn task**. Báo raw
command, stdout/stderr, exit code, architecture/OS, runner và file đã sửa;
không làm tròn kết quả thành PASS.

## Bàn giao

1. Viết root-cause ngắn gọn, theo từng bước parser → registry → call lowering
   → stub → Mach-O bind → dyld → ABI return.
2. Sửa nhỏ nhất nhưng đầy đủ, thêm regression tests và chạy `git diff --check`.
3. Commit nguyên tử chỉ các file task, ví dụ:

   ```text
   fix Mach-O extern imports end to end
   ```

4. Cập nhật báo cáo FFI/hardening chỉ theo output E2E thật; không giữ claim
   chained-fixups hoặc `100% PASS` nếu verification không chứng minh được.
