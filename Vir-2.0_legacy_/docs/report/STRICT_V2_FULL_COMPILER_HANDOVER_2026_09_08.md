# STRICT V2 full compiler — handover 2026-09-08

## Trạng thái bàn giao

INCOMPLETE / BLOCKED — chưa đạt cổng nghiệm thu tổng.

Phiên triển khai được tạm ngưng theo yêu cầu của người dùng. Không được công bố
`complete`, `100%` hoặc release-ready từ trạng thái này. FMA số nguyên trên
macOS ARM64 đã chạy đúng và các semantic gate mới đã có bằng chứng, nhưng toàn
bộ hợp đồng trong
`docs/plan/STRICT_V2_FULL_COMPILER_END_TO_END_PROMPT.md` chưa hoàn tất trên năm
target công khai.

## Yêu cầu gần nhất của người dùng

1. Thực thi toàn bộ prompt STRICT V2 end-to-end.
2. Bổ sung toán tử `><`  với nghĩa **FMA** (không phải “FWA”).
3. Triển khai đủ nhóm AI/ML:
   `tensor<T>[S...]`, `**`, `><`, `infer`, `train`/`.backward()` và `quantize`.

Prompt đã được mở rộng tương ứng, gồm contract frontend, semantic, MIR/LIR,
backend, mutation test, integration và ma trận năm target. File prompt hiện là
file mới chưa được track trong Git.

### Prompt canonical và tài liệu lịch sử

Mọi yêu cầu interpolation/literal, tensor/matmul/FMA và FFI hiện đã được hợp
nhất trực tiếp vào một prompt canonical:

```text
docs/plan/STRICT_V2_FULL_COMPILER_END_TO_END_PROMPT.md
```

Ba prompt con đã bị supersede và được chuyển vào `docs/plan/done/`:

```text
STRICT_V2_STRING_INTERPOLATION_AND_LITERAL_VALUES_PROMPT.md
STRICT_V2_TENSOR_MULTI_INDEX_MATMUL_PROMPT.md
STRICT_FFI_EXTERN_IMPORT_END_TO_END_PROMPT.md
```

Không tiếp tục chỉnh riêng các prompt lịch sử. Mọi scope/checklist mới phải
được thêm vào prompt tổng để tránh divergence.

## Những phần đã triển khai

### 1. FMA `><` từ token đến native integer backend

- Lexer có token riêng cho `><`; parser tạo `OpType.FmaOp`, precedence cùng
  nhóm với `**`.
- AST giữ hai toán hạng; scalar FMA bị semantic reject.
- Semantic kiểm tra cả hai operand là tensor rank 2, cùng element type, inner
  dimension tương thích và không đoán shape 2×2.
- MIR có `MirOp.Fma`, LIR có `LirOp.Fma`; shape `M/K/N` được đóng gói trong
  `aux` và được giữ qua `lir_lower`.
- ARM64 và x86_64 có kernel dot-product chữ nhật dùng chung cho `**`/`><` ở
  đường integer. Không còn tham số accumulator thứ ba ẩn hoặc giá trị thanh ghi
  cũ.
- x86_64 tensor index/index-store đã được sửa để dùng payload offset 16 byte và
  stride 8 byte.

Bằng chứng macOS ARM64 đã chạy:

```text
PASS: fma=19,22,43,50 rect=58,64,139,154
compile exit = 0
run exit     = 0
codesign --verify --strict = pass
```

Fixture mutation cố tình mong giá trị sai trả `71`, chứng minh test không còn
pass giả.

Giới hạn quan trọng: FMA `f32`/`f16` single-rounding bằng primitive fused chưa
được triển khai. Kernel hiện có bằng chứng đúng chỉ cho lane integer i64.

### 2. Sửa mã thoát startup — điều kiện tiên quyết của mọi runtime assertion

Trước khi sửa, entry stub ARM64/x86_64 luôn ghi đè kết quả `main` bằng `0`, vì
vậy mọi fixture trả mã lỗi vẫn có thể bị báo pass.

- ARM64 giữ nguyên X0 sau khi gọi `main`; chỉ tạo `0` khi không có function.
- x86_64 chuyển RAX của `main` sang RDI trước syscall `exit(2)`.

Bằng chứng sau sửa:

```text
/private/tmp/if_mutation_sanity       exit = 71
/private/tmp/fma_mutation_expected    exit = 71
/private/tmp/fma_tensor_e2e           exit = 0
```

Landmark:

- `stdlib/vir/compiler/lir_codegen.vri` gần dòng 3242.
- `stdlib/vir/compiler/lir_codegen_x86.vri` gần dòng 1189.

### 3. Tensor và matmul semantic/backend đã được siết chặt

- Tensor multi-index kiểm rank và kiểu index.
- Index assignment kiểm element type.
- Matmul/FMA rank, shape và element type được kiểm compile-time.
- ARM64/x86_64 integer rectangular matmul/FMA không hard-code 2×2.
- RISC-V không còn sinh ELF rỗng giả thành công; hiện fail
  `E-CODEGEN-EMPTY`.
- WASM quét LIR và fail `E-WASM-UNSUPPORTED` nếu gặp op/intrinsic chưa hạ,
  thay vì sinh artifact giả.

### 4. `infer`, `train`, `.backward()` semantic state

- Semantic context phân biệt normal/infer/train.
- Cấm `infer` lồng `train` và ngược lại (`E3016`).
- Cấm `.backward()` trong `infer` (`E3009`).
- Cấm `.backward()` ngoài `train` (`E3017`).
- Trong `train`, receiver phải là giá trị float/tensor được tạo trong chính
  block train; integer hoặc giá trị khai báo ngoài block bị `E3020`.
- Danh sách value sinh trong infer/train được theo dõi trong pass 6.

Các negative test sau đều compile exit `1`, không sinh artifact:

```text
infer_backward_negative.vri          E3009
infer_train_nested_negative.vri      E3016
backward_outside_train_negative.vri  E3017
train_backward_integer_negative.vri  E3020
train_backward_external_negative.vri E3020
```

Giới hạn quan trọng: `MIR_INTR_INFER` và `MIR_INTR_TRAIN` vẫn là marker no-op ở
native codegen. Chưa có tape, gradient buffer, reverse traversal hoặc gradient
rules compiler-native. Một `.backward()` hợp lệ về semantic vẫn đi vào đường
method call chưa có runtime autodiff thật.

### 5. `quantize` frontend và type-state

- Parser nhận dạng canonical `quantize(value, bits: N)` và giữ cả value lẫn
  bits trong AST. Positional bits còn được giữ để tương thích.
- Bits phải là literal compile-time trong `{4, 8, 16, 32}` (`E3019`).
- Input phải là tensor có element type float (`f32`/`f16` được quy về
  `TypeKind.Float`), tensor integer bị `E3018`.
- Đã thêm `TypeKind.QuantizedTensor = 22`, tách quantized handle khỏi Tensor
  thường để không vô tình cho phép mutation/autodiff.
- Helper `pass6_tensor_type_name` phục hồi annotation element/shape xuyên qua
  identifier và quantize wrapper.

Bằng chứng:

```text
quantize_frontend_positive.vri       compile exit = 0
quantize_bits_negative.vri           E3019
quantize_dynamic_bits_negative.vri   E3019
quantize_input_negative.vri          E3018
quantize_integer_tensor_negative.vri E3018
```

Giới hạn nghiêm trọng: `MIR_INTR_QUANTIZE` vẫn bị codegen coi là marker no-op.
Positive frontend test chỉ chứng minh parser/semantic; artifact hiện chưa chứa
compact storage. Không được tính nó là E2E pass.

### 6. String interpolation

Dynamic interpolation đã chạy đúng trên macOS ARM64 cho:

- integer và biểu thức integer;
- boolean `true`/`false`;
- `none`;
- string variable/pass-through.

Bằng chứng exact output:

```text
n=42; ok=true; nope=false; nothing=none; sum=43
```

`print` của string variable đã được sửa để dùng `PRINT_STR`, không in địa chỉ
pointer. Float formatting/interpolation chưa được triển khai.

### 7. Mach-O, ELF và FFI

- Mach-O ARM64 có ad-hoc code signature nội bộ; artifact trực tiếp qua
  `codesign --verify --strict` và chạy được, không cần post-process bằng
  `codesign` ngoài compiler.
- ELF headers đã dùng đúng machine id cho AArch64, x86_64, RISC-V.
- Parser/semantic FFI đã giữ provider, return type, arity và argument types.
- macOS `getpid` extern đã chạy.
- Linux extern động hiện bị gate rõ `E-FFI-ELF-UNSUPPORTED`; chưa có dynamic
  loader/relocation/import implementation.

## Ma trận target gần nhất

Fixture integer FMA được compile bằng compiler tạm trước semantic type-state
cuối cùng:

| Target | Trạng thái gần nhất |
| --- | --- |
| `macos-arm64` | artifact signed, chạy exact output, exit 0 |
| `linux-arm64` | ELF đúng AArch64, compile 0; chưa chạy trên Linux |
| `linux-x86_64` | ELF đúng x86_64, compile 0; chưa chạy trên Linux |
| `linux-riscv64` | compile 1, không artifact, `E-CODEGEN-EMPTY` |
| `wasm32-wasi-p1` | compile 1, không artifact, `E-WASM-UNSUPPORTED` |

Không được diễn giải hai gate “unsupported” là target pass. Chúng chỉ loại bỏ
false-positive artifact.

Remote Linux `quizzman` có qemu, nhưng lần xin upload/chạy trước bị approval
reviewer từ chối vì egress source/artifact. Không retry hoặc tìm cách né approval;
nếu cần chạy remote phải xin người dùng cho phép rõ ràng.

## Compiler artifacts hiện tại

- `bin/virc`: đã được promote sau phần FMA/interpolation/FFI trước đó, nhưng
  **chưa chứa** các edit mới nhất (xóa debug lexer, exit-code fix, quantized
  type-state và semantic train mới). Nó còn có thể in dòng debug lexer khi tự
  compile.
- `/private/tmp/virc_exit_fix`: build thành công với exit-code fix, trước patch
  type-state cuối.
- `/private/tmp/virc_ai_sem`: build thành công từ source mới nhất tại thời điểm
  bàn giao, gồm exit-code fix và semantic/type-state AI mới.

Các file trong `/private/tmp` không bền vững qua reboot/cleanup. Người tiếp quản
nên bootstrap lại từ `bin/virc`, chạy smoke, rồi mới promote.

## Các blocker kỹ thuật còn lại

1. **Typed numeric pipeline:** MIR không lưu type cho instruction; `lir_lower`
   đang tạo mọi instruction với `LirType.Int64`. Float literal được chuyển dưới
   dạng raw IEEE-754 bits nhưng phép Add/Mul hiện vẫn là integer ALU. Đây là
   blocker chung của float interpolation, float tensor, FMA fused, quantize và
   autodiff float.
2. **Tensor ABI:** built-in tensor hiện dùng layout Vec-like
   `[len, cap, i64 payload...]`, allocation chưa chứng minh 64-byte aligned và
   không phản ánh element width `f32/f16/i8/u8/i32`.
3. **FMA float:** chưa có typed ARM `FMADD/FMLA`, x86 FMA3/AVX path, WASM
   simd128 hoặc policy reject target thiếu primitive.
4. **Quantize backend:** chưa có header/metadata, scale/zero-point, saturation,
   INT8 byte storage, INT4 nibble packing, f16/f32 storage hoặc transparent
   dequantized infer.
5. **Infer backend:** chưa có region metadata/lifetime proof rằng không tape,
   activation hay gradient buffer được tạo.
6. **Train/autodiff:** chưa có graph/tape compiler-native, fan-out gradient
   accumulation, backward rules cho add/sub/mul/matmul/FMA/reduction, `.grad`
   access hay cleanup.
7. **WASM:** calls, CFG/tensor/memory và nhiều intrinsics còn unsupported.
8. **RISC-V:** backend chưa phát machine code thực.
9. **Linux FFI:** ELF dynamic imports/relocations chưa triển khai.
10. **Float interpolation:** chưa có deterministic float-to-string runtime.
11. **Full E2E:** chưa có tối thiểu 60 lượt standalone pass, integration năm
    target, mutation đầy đủ, reproducibility và artifact inspection theo prompt.

## Thứ tự tiếp tục đề xuất

### P0 — Không cho phép success giả

Trước khi viết runtime lớn, thêm pre-codegen validator để reject có mã lỗi rõ
nếu artifact vẫn chứa:

- `MIR_INTR_QUANTIZE` chưa được hạ;
- train graph hoặc `.backward()` chưa được hạ;
- float tensor/FMA trên backend chưa có typed implementation.

Sau khi từng backend thật hoàn tất thì gỡ đúng gate tương ứng. Hiện positive
quantize semantic compile vẫn có thể sinh artifact no-op, nên đây là lỗ hổng
nghiệm thu cần xử lý đầu tiên.

### P1 — Typed MIR/LIR và tensor ABI

1. Thêm type/element metadata thật vào MIR instruction/operand hoặc bảng vreg.
2. Hạ đúng sang `LirType.F32/F64/Int8/Int32/Vector`, không hard-code Int64.
3. Chuẩn hóa tensor handle gồm rank, shape, strides, element kind, numel và
   payload 64-byte aligned row-major.
4. Sửa index/get/set/matmul theo element width; thêm overflow/bounds policy.
5. Viết ABI/layout tests trước khi nối quantize/autodiff.

### P2 — `**` và `><` float

1. Scalar oracle đúng IEEE cho rectangular matrices.
2. FMA path dùng instruction fused thực; không tách mul+add.
3. Adversarial single-rounding test và disassembly assertion.
4. Implement/reject có chủ đích cho từng target.

### P3 — Quantize

1. Chuyển `MIR_INTR_QUANTIZE` từ marker thành op/payload thật, giữ bits và
   source shape/element type qua LIR.
2. Chốt ABI versioned cho `QuantizedTensor` và raw-size formula.
3. Per-tensor symmetric scale; zero tensor policy; round/clamp deterministic.
4. INT8 mỗi phần tử một byte; INT4 hai signed nibble mỗi byte, thứ tự nibble
   được test; bits 16/32 có storage đúng width.
5. Infer matmul dequantize đúng và không tạo tape.
6. Test raw bytes, nibble, saturation, scale, byte size và oracle output.

### P4 — Infer/train native state

1. Hạ block enter/exit thay vì marker đơn; giữ mode trong typed MIR.
2. Infer chỉ forward và reject value provenance khi `.backward()` ngoài block.
3. Train tạo tape/graph arena; mỗi op lưu parent/type/shape cần thiết.
4. `.backward()` seed loss, reverse traversal, cộng gradient fan-out.
5. Rules ít nhất add/sub/mul/`**`/`><`/reduction; gradient shape/type checks.
6. Cleanup tape và chứng minh infer không allocation phần gradient.

### P5 — Target completion và nghiệm thu

1. Hoàn thiện Linux ARM64/x86_64 runtime execution.
2. Viết RISC-V backend và WASM calls/CFG/tensor/SIMD.
3. Viết ELF FFI imports.
4. Chạy hai lượt sạch mỗi case/target; exact stdout/stderr/exit; mutation.
5. Promote `bin/virc`, bootstrap lại compiler, rồi chạy toàn bộ suite bằng
   chính compiler vừa promote.
6. Viết report cuối; chỉ đánh dấu complete khi toàn bộ checklist có bằng chứng.

## Test files đã thêm

```text
tests/strict_v2/fma_tensor_e2e.vri
tests/strict_v2/fma_scalar_negative.vri
tests/strict_v2/fma_shape_negative.vri
tests/strict_v2/fma_element_negative.vri
tests/strict_v2/interpolation_dynamic_primitives.vri
tests/strict_v2/infer_backward_negative.vri
tests/strict_v2/infer_train_nested_negative.vri
tests/strict_v2/backward_outside_train_negative.vri
tests/strict_v2/quantize_frontend_positive.vri
tests/strict_v2/quantize_bits_negative.vri
tests/strict_v2/quantize_dynamic_bits_negative.vri
tests/strict_v2/quantize_input_negative.vri
tests/strict_v2/quantize_integer_tensor_negative.vri
tests/strict_v2/train_backward_integer_negative.vri
tests/strict_v2/train_backward_external_negative.vri
```

## Lệnh tiếp tục tối thiểu

```sh
cd /Users/gengyang/Vir
git status --short
git diff --check

./bin/virc stdlib/vir/compiler/virc.vri -o /private/tmp/virc_resume -q
/private/tmp/virc_resume tests/strict_v2/fma_tensor_e2e.vri -o /private/tmp/fma_resume -q
/private/tmp/fma_resume
codesign --verify --strict /private/tmp/fma_resume

/private/tmp/virc_resume tests/strict_v2/quantize_integer_tensor_negative.vri -o /private/tmp/q_bad -q
/private/tmp/virc_resume tests/strict_v2/train_backward_integer_negative.vri -o /private/tmp/train_bad -q
```

Expected hiện tại: FMA in đúng chuỗi PASS và exit 0; hai negative compile exit 1
với `E3018` và `E3020`, không có artifact.

Chỉ promote sau khi compiler mới build và focused tests pass:

```sh
VIRC_PROMOTE_QUIET=1 bash tools/promote_virc.sh --install
```

## Cảnh báo worktree

Worktree đang rất dirty và có nhiều file/binary/submodule thay đổi không thuộc
task này. Không dùng `git add -A`, `git reset --hard`, `git checkout -- .` hoặc
xóa artifact hàng loạt. Chỉ stage từng file đã kiểm tra. Các nhóm file task liên
quan chính:

```text
docs/plan/STRICT_V2_FULL_COMPILER_END_TO_END_PROMPT.md
docs/report/STRICT_V2_FULL_COMPILER_HANDOVER_2026_09_08.md
stdlib/vir/compiler/{lexer,parser,type_table,sem_pass2_symbols,
  sem_pass4_types,sem_pass6_typecheck,sem_pass10_diagnostics,
  ast_to_mir,lir,lir_lower,lir_target_desc,lir_codegen,
  lir_codegen_x86,lir_codegen_wasm,macho,ffi_imports,virc}.vri
stdlib/vir/rt/elf.vri
tests/strict_v2/*.vri
bin/virc
```

`git diff --check` pass tại thời điểm tạo handover.
