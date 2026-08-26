# Soft Path Debug Handoff — Hướng dẫn viết / kiểm thử / rollback

**Ngày:** 2026-07-30  
**Branch tip (khi viết):** `d8125275` (`fix(soft): RA with PARAM defs and callee-saved colors`)  
**Đối tượng:** AI / người tiếp tục debug soft compiler tới PROD  
**Bối cảnh đầy đủ:** [`CURRENT_STATUS_2026_07_30.md`](CURRENT_STATUS_2026_07_30.md), [`REGISTER_ALLOCATION_ARCHITECTURE.md`](REGISTER_ALLOCATION_ARCHITECTURE.md)

---

## 0. Nhiệm vụ còn lại (ưu tiên)

Soft `virc` **đã** lex→parse→semantic→MIR→LIR→RA→ARM64→Mach-O và chạy được arith/call. Còn:

| # | Việc | Evidence hiện tại | File nghi ngờ |
|---|------|-------------------|---------------|
| 1 | Control flow `if` / `when` / `eif` | `cg_if`, `cg_when` → stdout rỗng | `ast_to_mir.vri` (JumpIf*), `lir_codegen.vri` (JmpCond fixup), `lir_lower.vri` |
| 2 | `let x = f(st, …)` arg resolve | `cg_let_call_arg` → `0` (expect `42`) | `ast_to_mir.vri` call/let lowering; soft chưa có `alloc`/`read_word`/`write_word` RT? |
| 3 | Spill `StackMem` emit | RA gán slot nhưng emit bỏ qua | `lir_codegen.vri` `resolve_reg` / Load-Store |
| 4 | Mở suite `manifest.json` | Spot-check vài file PASS | soft `virc` + RT stubs |
| 5 | Soft self-host → fixed-point → kill C | Chưa bắt đầu | toàn pipeline |

**Không** đụng thin Stage-0/1 fixed-point trừ khi regression rõ. Thin đã xanh (`tools/bootstrap_fixed_point.sh`).

---

## 1. Kiến trúc hai đường (đừng nhầm)

**Official IR (một mô hình):** `AST → HIR → MIR → LIR → Codegen`  
(Spec §1.2, `docs/ARCHITECTURE.md` §0; SoT: `hir.vri` / `mir.vri` / `lir.vri`). Soft hôm nay có thể còn AST→MIR trực tiếp — gap wiring HIR, không phải kiến trúc thứ hai. Không dùng QIR-H/M/L / flat Q-IR làm chuẩn.

```
Thin (đã PROD-ish bootstrap):
  virc_boot.vri → dist/virc-stage1 → stage2/stage3 fixed-point

Soft (đang debug — mục tiêu thay C-VM):
  ./core/build/vir run stdlib/vir/compiler/virc.vri -- <input.vri>
       └─ C-VM host chạy soft compiler Vir → a.out (Mach-O ARM64)
```

- **C-VM** (`core/src/*`) = runtime/host hiện tại của soft. Sửa C chỉ khi soft treo/SEGV do host (nested call ABI, field assign, borrow…).
- **Soft** (`stdlib/vir/compiler/*.vri`) = compiler thật cần đúng. Hầu hết việc còn lại nằm đây.
- Đo soft bằng **`tests/bootstrap_codegen/manifest.json`**, **không** bằng `run_tests.sh` (expected lệch nội dung file).

---

## 2. Quy tắc viết code (bắt buộc)

### 2.1 Ngôn ngữ Vir (soft)

- Spec: `docs/vir_language_spec_v2.0_vi.md`
- `;` **không bắt buộc** khi đã xuống dòng; `,`/`;` vẫn cần giữa phần tử cùng dòng.
- Phép modulo là **`mod`**, không phải `%` (`%` = percent).
- Include thư viện: **dot-path** `include vir.rt.vec_rt` — không slash path trên surface.
- String từ lexer/AST là **fat string** `{data, byte_len, char_len}`. So sánh bằng `fat_str_eq` / hash nội dung — **không** `rt_streq` trên pointer fat, **không** hash pointer.

### 2.2 Field access qua `vec_get_rt` (bug class #1)

`vec_get_rt` trả pointer không kiểu. `.name` / `.op_type` / `.vreg` dễ resolve nhầm entity khác (Mir vs Lir).

**Luôn** bọc accessor có tham số typed:

```vir
func lir_instr_dst(ins: LirInstr)
    out ins.dst
end.
# dùng: d = lir_instr_dst(vec_get_rt(instrs, i))
```

Đã có pattern trong `lir_liveness.vri`, `lir_func_name` trong `lir_codegen.vri`.

### 2.3 Nested field assign + `vec_push_rt`

- Gán `a.b.c = x` cần C-VM đã fix — nếu soft host SEGV/silent no-op, kiểm tra lại.
- `vec_push_rt` **có thể realloc**: luôn ghi lại pointer  
  `tree.scopes = vec_push_rt(tree.scopes, node)`.

### 2.4 Container type annotations

Khai báo `[T]` trên field entity (`blocks: [LirBlock]`, `matrix: [i64]`) để inference offset đúng. Tránh `i64` + comment “là vec”.

### 2.5 ABI / RA (đã chốt — đừng phá)

- Param: `MIR_INTR_PARAM` (kind **100**) — DEF `dst ← X[abi]`.
- Colors 0..7 → **X19..X26** (callee-saved); prologue/epilogue save/restore.
- X0..X7 chỉ ở biên Call / SetArg / print / PARAM.
- Print i64: RT stub `MIR_INTR_PRINT` (syscall write). Stub **clobber X0** (return của `write`).

### 2.6 Phạm vi diff

- Một việc = một commit nhỏ, message theo style: `fix(soft): …` / `feat(soft): …`.
- Không commit: `.DS_Store`, `core/build/*`, `dist/*`, `node_modules`, `a.out`, probe `/tmp`, semicolon-sweep toàn stdlib không liên quan.
- Không `git push` / force / amend trừ khi user yêu cầu rõ.

---

## 3. Kiểm thử — quy trình chuẩn

### 3.1 Build C-VM (khi đụng `core/src`)

```bash
cd /Users/gengyang/Vir/core && make -j8
# binary: ../core/build/vir
```

### 3.2 Soft compile + chạy một fixture

```bash
cd /Users/gengyang/Vir
SRC=tests/bootstrap_codegen/cg_if.vri

# Compile (soft virc dưới C-VM). Timeout ~45–60s bình thường.
perl -e 'alarm 60; exec @ARGV' -- \
  ./core/build/vir run stdlib/vir/compiler/virc.vri "$SRC" \
  > /tmp/soft_compile.txt 2>&1
echo "compile exit=$?"

# Bắt buộc re-sign (LC_CODE_SIGNATURE soft có thể stale)
codesign -s - -f ./a.out

# Chạy binary (timeout ngắn — treo = thiếu epilogue / nhảy sai)
out=$(perl -e 'alarm 5; exec @ARGV' -- ./a.out 2>&1)
echo "stdout=[${out}]"
```

Expected: lấy từ manifest:

```bash
python3 -c "
import json,sys
m=json.load(open('tests/bootstrap_codegen/manifest.json'))
f=sys.argv[1]
for t in m['tests']:
    if t['file']==f: print(repr(t['stdout'])); break
" cg_if.vri
```

### 3.3 Smoke “không regress” (chạy sau mọi fix)

Các case **đã PASS** — phải giữ:

| File | stdout |
|------|--------|
| `cg_arith.vri` | `30\n90\n` |
| `cg_mul.vri` | `30\n90\n` |
| `cg_var.vri` | `30\n` |
| `cg_assign.vri` | `42\n` |
| `cg_call.vri` | `42\n` |
| `cg_multiparam.vri` | `42\n` |

Script nhanh:

```bash
cd /Users/gengyang/Vir
for f in cg_arith cg_mul cg_var cg_assign cg_call cg_multiparam; do
  perl -e 'alarm 45; exec @ARGV' -- \
    ./core/build/vir run stdlib/vir/compiler/virc.vri \
    tests/bootstrap_codegen/${f}.vri >/dev/null 2>&1 || { echo "FAIL compile $f"; continue; }
  codesign -s - -f ./a.out 2>/dev/null
  out=$(perl -e 'alarm 5; exec @ARGV' -- ./a.out 2>&1 | tr '\n' '|')
  echo "$f => [$out]"
done
```

**Không** chạy full `run_tests.sh` (chậm + expected sai).  
**Không** chạy cả `manifest.json` (~100 file × ~5s) trừ khi chuẩn bị PR lớn — dùng spot-check theo nhóm (ctrl / call / mem).

### 3.4 Disassemble khi stdout sai

```bash
otool -tvV a.out | head -80
# So: _start bl main? PARAM mov từ x0? JmpCond patch? print bl stub?
```

### 3.5 Debug soft treo / SEGV dưới C-VM

1. Thêm `print_ln("DBG …")` **có kiểm soát** — nhớ xóa trước commit.
2. Khoanh: parse xong chưa? semantic? pipeline? emit?
3. Nếu chỉ fail khi include thêm module → nghi field-offset / entity layout collision.
4. Nested call trong arg C-VM: đã fix `mir_lower.c` (stage vào vreg tạm). Repro cũ: `outer(1, inner(b.n))` phải ra đúng, không 606.

### 3.6 Regression C-VM (chỉ khi sửa `core/src`)

So với baseline HEAD trước khi sửa (copy tree + rebuild), hoặc chạy subset `tests/*.vri`. Chấp nhận diff số instruction count; không chấp nhận đổi stdout logic.

### 3.7 Thin path (chỉ khi đụng boot/stage1)

```bash
./tools/bootstrap_fixed_point.sh   # expect FIXED_POINT_PASS
```

---

## 4. Rollback

### 4.1 Rollback cả commit soft gần nhất

```bash
git log -5 --oneline
# Soft RA:     d8125275
# Soft e2e:    3dbdeff1

# An toàn — tạo reverse commit (khuyên dùng nếu đã share branch)
git revert d8125275 --no-edit

# Hoặc reset local chưa push (chỉ khi user đồng ý):
# git reset --hard HEAD~1
```

### 4.2 Rollback từng file về tip tốt

```bash
git checkout d8125275 -- stdlib/vir/compiler/lir_codegen.vri
# hoặc về commit trước RA:
git checkout 3dbdeff1 -- stdlib/vir/compiler/lir_regalloc_color.vri
```

### 4.3 Rollback C-VM riêng

```bash
git checkout HEAD -- core/src/mir_lower.c core/src/ir_lower.c \
  core/src/parser.c core/src/borrow_check.c
cd core && make -j8
```

### 4.4 Giữ điểm khôi phục trước khi thử nghiệm lớn

```bash
git branch wip/soft-ctrl-flow-$(date +%Y%m%d)
# hoặc stash có tên:
git stash push -m "before jmpcond experiment" -- stdlib/vir/compiler/
```

### 4.5 Không rollback

- `dist/virc-stage*` binaries (tái tạo bằng script)
- Toàn bộ semicolon-sweep unstaged trong working tree — đó là noise, đừng `add -A`

---

## 5. Playbook debug từng blocker

### 5.1 `cg_if` / `cg_when` (stdout rỗng)

**Mục tiêu:** `cg_if` → `1\n`.

1. Soft compile + `otool -tvV a.out` — có `b.eq`/`b.ne` không? offset có trỏ vào `print` không?
2. Trace soft:
   - `ast_to_mir`: `JumpIf` / `JumpIfNot` + block ids
   - `lir_lower`: `LirOp.JmpCond`, `aux` = `LIR_JMP_IF` / `LIR_JMP_IFNOT`
   - `lir_codegen`: `fixups` kind 1/2 patch `imm19` đúng chiều?
3. Lưu ý: fall-through epilogue luôn emit sau body — nhảy sai có thể rơi vào epilogue/ret sớm → không print.
4. Sau fix: chạy lại smoke §3.3 + `cg_if_else` + `cg_when*`.

### 5.2 `cg_let_call_arg` → `0`

Fixture dùng `alloc` / `read_word` / `write_word`. Soft có thể:
- Chưa hạ được builtin → call unresolved stub (trả 0), hoặc
- Sai resolve tên `st` khi hạ `let site = take(st, 9)`.

Thứ tự khoanh:
1. Disasm: `bl` tới đâu? stub unresolved?
2. Nếu thiếu RT: thêm stub soft hoặc intrinsic (không giả vờ PASS).
3. Nếu có call đúng nhưng arg sai: dump LIR SetArg — arg0 có phải param `st` không.

### 5.3 Spill

Khi `assigned_stack[v] != 0`: emit `str` trước clobber / `ldr` khi use. Chưa có → đừng tăng áp lực spill (giữ K=8 trên X19..X26).

---

## 6. Definition of Done (cho PR/debug session)

Một session/PR soft được coi là xong khi:

1. Í tiêu session PASS theo manifest (stdout + exit).
2. Smoke §3.3 vẫn PASS.
3. Không còn `print_ln("DBG…")` trong tree.
4. `git commit` chỉ gồm file liên quan; message giải thích **why**.
5. Cập nhật ngắn [`CURRENT_STATUS_2026_07_30.md`](CURRENT_STATUS_2026_07_30.md) (hoặc ngày mới) — dòng status + next blocker.
6. Nếu sửa `core/src`: ghi rõ trong commit; cân nhắc corpus smoke.

---

## 7. Bản đồ file (đọc trước khi sửa)

| Path | Vai trò |
|------|---------|
| `stdlib/vir/compiler/virc.vri` | Driver soft |
| `stdlib/vir/compiler/pipeline.vri` | MIR→LIR→RA |
| `stdlib/vir/compiler/ast_to_mir.vri` | AST→MIR, PARAM, if/when/call |
| `stdlib/vir/compiler/lir_lower.vri` | MIR→LIR |
| `stdlib/vir/compiler/lir_liveness.vri` | Intervals (typed) |
| `stdlib/vir/compiler/lir_regalloc_color.vri` | Chaitin–Briggs + rewrite |
| `stdlib/vir/compiler/lir_codegen.vri` | ARM64 + stubs + `_start` |
| `stdlib/vir/compiler/mir.vri` | `MIR_INTR_*` (PARAM=100) |
| `stdlib/vir/compiler/scope_tree.vri` | Semantic scopes |
| `core/src/mir_lower.c` | Nested-call ABI (host) |
| `tests/bootstrap_codegen/manifest.json` | Golden stdout |
| `tools/bootstrap_fixed_point.sh` | Thin gate — đừng phá |

---

## 8. Pitfall đã biết (đọc 2 phút trước khi đoán)

1. Soft “treo ở parsing” từng là **false lead** — thật ra nested call-in-arg C-VM làm hỏng `sb_append_int` sau parse.
2. `_start` từng gọi hàm index 0 (`bump`) vì `rt_streq` trên fat name / đọc `.name` nhầm `.id`.
3. `add x0,x0,x0` = RA identity / thiếu PARAM / màu trên caller-saved — đã xử lý; nếu tái diễn, kiểm tra rewrite có còn typed không.
4. Print hai lần: giá trị sống qua `bl print` phải ở X19+; X0 sau print = độ dài write.
5. `run_tests.sh` expected sai — bỏ qua.

---

## 9. Lệnh “bắt đầu session” (copy-paste)

```bash
cd /Users/gengyang/Vir
git status -sb
git log -3 --oneline
cd core && make -j8 && cd ..

# Baseline smoke
for f in cg_arith cg_call cg_mul; do
  perl -e 'alarm 45; exec @ARGV' -- \
    ./core/build/vir run stdlib/vir/compiler/virc.vri \
    tests/bootstrap_codegen/${f}.vri >/dev/null 2>&1
  codesign -s - -f ./a.out 2>/dev/null
  echo -n "$f: "; perl -e 'alarm 5; exec @ARGV' -- ./a.out; echo
done

# Việc tiếp: cg_if
perl -e 'alarm 60; exec @ARGV' -- \
  ./core/build/vir run stdlib/vir/compiler/virc.vri \
  tests/bootstrap_codegen/cg_if.vri > /tmp/cg_if_compile.txt 2>&1
codesign -s - -f ./a.out && ./a.out; echo "exit=$?"
otool -tvV a.out | head -60
```

Khi xong một milestone: commit + cập nhật status doc + để lại 3–5 dòng “next” cho AI sau.
