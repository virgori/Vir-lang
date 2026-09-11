#!/bin/bash
# ==========================================================================
# Vir Compiler Self-Hosting Test Suite — Categorized by Spec v2.0 (§1 - §31)
# ==========================================================================
# Cách sử dụng:
#   ./run_tests.sh min     # Bộ test cốt lõi nhanh (85 bài / 31 nhóm)
#   ./run_tests.sh full    # Toàn bộ test suite (> 400 bài không trùng lặp)
#   ./run_tests.sh <1..31> # Chạy riêng 1 nhóm cụ thể (ví dụ: ./run_tests.sh 26)
# Mặc định: min
# ==========================================================================

cd "$(dirname "$0")"
VIRC="${VIRC:-./bin/virc}"
A_OUT="./scratch/a_test.out"
mkdir -p scratch

MODE="${1:-min}"
TARGET_GROUP=""

if [[ "$MODE" =~ ^[0-9]+$ ]]; then
    TARGET_GROUP="$MODE"
    if [ "$TARGET_GROUP" -lt 1 ] || [ "$TARGET_GROUP" -gt 31 ]; then
        echo "Lỗi: Nhóm phải từ 1 đến 31."
        exit 1
    fi
    MODE="single"
elif [ "$MODE" != "min" ] && [ "$MODE" != "full" ]; then
    echo "Chế độ không hợp lệ: $MODE"
    echo "Cách dùng: $0 [min|full|<1..31>]"
    exit 1
fi

TOTAL_PASS=0
TOTAL_FAIL=0
declare -a GP_PASS
declare -a GP_FAIL
for i in $(seq 1 31); do GP_PASS[$i]=0; GP_FAIL[$i]=0; done

run_test_in_group() {
    local g="$1"
    local test="$2"
    
    # Bóc tách expected value tự động qua Regex từ comment header
    local expected
    expected=$(perl -0777 -ne '
        if (/#\s*EXPECT_START\n((?:#[^\n]*\n)+?)#\s*EXPECT_END/m) {
            my $b = $1; $b =~ s/^#[ \t]?//mg; chomp $b; print $b;
        } elsif (/#\s*EXPECT:\s*\n((?:#[^\n]*\n)+)/m) {
            my $b = $1; $b =~ s/^#[ \t]?//mg; chomp $b; print $b;
        } elsif (/#\s*EXPECT:\s*([^\n]+)/m) {
            my $v = $1; $v =~ s/\\n/\n/g; chomp $v; print $v;
        }
    ' "$test")

    local expected_diag
    expected_diag=$(sed -n 's/^#[[:space:]]*EXPECT_DIAGNOSTIC:[[:space:]]*//p' "$test" | head -1)
    local expected_line
    expected_line=$(sed -n 's/^#[[:space:]]*EXPECT_DIAGNOSTIC_LINE:[[:space:]]*//p' "$test" | head -1)
    local expected_member
    expected_member=$(sed -n 's/^#[[:space:]]*EXPECT_DIAGNOSTIC_MEMBER:[[:space:]]*//p' "$test" | head -1)
    local expected_receiver
    expected_receiver=$(sed -n 's/^#[[:space:]]*EXPECT_DIAGNOSTIC_RECEIVER:[[:space:]]*//p' "$test" | head -1)

    # Negative test (compile rejection expected)
    if [[ "$test" == *_rejected.vri ]] || [[ "$test" == *_rejected_*.vri ]] || [[ "$test" == *_negative.vri ]]; then
        local reject_out
        reject_out=$($VIRC "$test" -o "$A_OUT" 2>&1)
        local reject_rc=$?
        if [ $reject_rc -ne 0 ]; then
            local fail_reason=""
            if [ -n "$expected_diag" ] && ! grep -Fq "[$expected_diag]" <<<"$reject_out"; then
                fail_reason="kỳ vọng diagnostic code: $expected_diag"
            elif [ -n "$expected_line" ] && ! grep -E -i -q "([Ll]ine[[:space:]]*:[[:space:]]*$expected_line\b|[Ll]ine[[:space:]]+$expected_line\b)" <<<"$reject_out"; then
                fail_reason="kỳ vọng diagnostic line: $expected_line"
            elif [ -n "$expected_member" ] && ! grep -Fq "$expected_member" <<<"$reject_out"; then
                fail_reason="kỳ vọng diagnostic member: $expected_member"
            elif [ -n "$expected_receiver" ] && ! grep -Fq "$expected_receiver" <<<"$reject_out"; then
                fail_reason="kỳ vọng diagnostic receiver: $expected_receiver"
            fi

            if [ -n "$fail_reason" ]; then
                echo "  [FAIL-WRONG-DIAGNOSTIC] $test"
                echo "    kỳ vọng diagnostic: $expected_diag"
                echo "    $fail_reason"
                echo "    thực tế: $(echo "$reject_out" | grep -m1 -E 'Code[[:space:]]*:' || true)"
                GP_FAIL[$g]=$((GP_FAIL[$g]+1))
                TOTAL_FAIL=$((TOTAL_FAIL+1))
            else
                echo "  [PASS-REJECT] $test"
                GP_PASS[$g]=$((GP_PASS[$g]+1))
                TOTAL_PASS=$((TOTAL_PASS+1))
            fi
        else
            echo "  [FAIL-EXPECT-REJECT] $test"
            GP_FAIL[$g]=$((GP_FAIL[$g]+1))
            TOTAL_FAIL=$((TOTAL_FAIL+1))
        fi
        return
    fi

    # Biên dịch với native virc
    # Positive test: compile
    local compile_out
    if ! compile_out=$($VIRC "$test" -o "$A_OUT" 2>&1); then
        echo "  [FAIL-COMPILE] $test"
        echo "    $compile_out"
        echo "$compile_out" | sed 's/^/    /' | head -20
        GP_FAIL[$g]=$((GP_FAIL[$g]+1))
        TOTAL_FAIL=$((TOTAL_FAIL+1))
        return
    fi

    # Ký mã ad-hoc (Apple Silicon arm64 bắt buộc codesign)
    codesign -s - -f "$A_OUT" >/dev/null 2>&1
    # Codesign on macOS Mach-O
    if [ "$(uname -s)" = "Darwin" ]; then
        codesign -s - -f "$A_OUT" >/dev/null 2>&1 || true
    fi

    # Thực thi với timeout 5 giây
    # Positive test: run
    local actual
    actual=$(perl -e 'alarm 5; exec @ARGV' -- "$A_OUT" 2>&1)
    local exit_code=$?
    actual=$("$A_OUT" 2>&1)
    local rc=$?

    # Chuẩn hoá whitespace
    actual=$(echo "$actual" | sed -e :a -e '/^\n*$/{$d;N;};/\n$/ba')
    if [ $rc -ne 0 ]; then
        echo "  [FAIL-RUNTIME] $test (exit code: $rc)"
        echo "    Output: $actual"
        GP_FAIL[$g]=$((GP_FAIL[$g]+1))
        TOTAL_FAIL=$((TOTAL_FAIL+1))
        return
    fi

    if [ -n "$expected" ]; then
        if [ "$actual" = "$expected" ]; then
            echo "  [PASS] $test"
            GP_PASS[$g]=$((GP_PASS[$g]+1))
            TOTAL_PASS=$((TOTAL_PASS+1))
        else
            echo "  [FAIL-OUTPUT] $test"
            echo "    Kỳ vọng: '$expected'"
            echo "    Thực tế: '$actual'"
            GP_FAIL[$g]=$((GP_FAIL[$g]+1))
            TOTAL_FAIL=$((TOTAL_FAIL+1))
        fi
    else
        echo "  [PASS] $test"
        GP_PASS[$g]=$((GP_PASS[$g]+1))
        TOTAL_PASS=$((TOTAL_PASS+1))
    fi
}

run_ufcs_mc_target() {
    local g=11
    local target="$1"
    local asm_path="./scratch/ufcs_${target}.s"
    local compile_out
    if compile_out=$($VIRC "tests/strict_v2/ufcs_cross_type_chain_e2e.vri" --target "$target" -S -o "$asm_path" -q 2>&1) \
        && grep -Fq "Box.score" "$asm_path" \
        && grep -Fq "Wrapper.to_box" "$asm_path"; then
        if [ "$target" != "linux-riscv64" ] || { grep -Eq '^[[:space:]]*la[[:space:]].*make_box' "$asm_path" && grep -Eq '^[[:space:]]*jalr[[:space:]]' "$asm_path"; }; then
            echo "  [PASS-MC] UFCS $target assembly"
            GP_PASS[$g]=$((GP_PASS[$g]+1))
            TOTAL_PASS=$((TOTAL_PASS+1))
            return
        fi
    fi
    echo "  [FAIL-MC] UFCS $target assembly"
    if [ -n "$compile_out" ]; then echo "    $compile_out"; fi
    GP_FAIL[$g]=$((GP_FAIL[$g]+1))
    TOTAL_FAIL=$((TOTAL_FAIL+1))
}

run_enum_mc_target() {
    local g=8
    local target="$1"
    local asm_path="./scratch/enum_${target}.s"
    local compile_out
    if compile_out=$($VIRC "tests/strict_v2/test_enum_tagged_union_e2e.vri" --target "$target" -S -o "$asm_path" -q 2>&1) \
        && [ -s "$asm_path" ]; then
        echo "  [PASS-MC] Enum $target assembly"
        GP_PASS[$g]=$((GP_PASS[$g]+1))
        TOTAL_PASS=$((TOTAL_PASS+1))
        return
    fi
    echo "  [FAIL-MC] Enum $target assembly"
    if [ -n "$compile_out" ]; then echo "$compile_out" | sed 's/^/    /' | head -20; fi
    GP_FAIL[$g]=$((GP_FAIL[$g]+1))
    TOTAL_FAIL=$((TOTAL_FAIL+1))
}

run_case_mc_target() {
    local g=21
    local target="$1"
    local asm_path="./scratch/case_${target}.s"
    local compile_out
    if compile_out=$($VIRC "tests/strict_v2/test_case_grammar_e2e.vri" --target "$target" -S -o "$asm_path" -q 2>&1) \
        && [ -s "$asm_path" ] \
        && grep -Fq "rt_str_eq" "$asm_path"; then
        echo "  [PASS-MC] Case $target assembly"
        GP_PASS[$g]=$((GP_PASS[$g]+1))
        TOTAL_PASS=$((TOTAL_PASS+1))
        return
    fi
    echo "  [FAIL-MC] Case $target assembly"
    if [ -n "$compile_out" ]; then echo "$compile_out" | sed 's/^/    /' | head -20; fi
    GP_FAIL[$g]=$((GP_FAIL[$g]+1))
    TOTAL_FAIL=$((TOTAL_FAIL+1))
}

run_interp_wasm_target() {
    local g=31
    local test="$1"
    local expected="$2"
    local label="$3"
    local wasm_path="./scratch/interp_${label}.wasm"
    local compile_out
    local actual
    local rc
    if ! command -v node >/dev/null 2>&1; then
        echo "  [FAIL-WASM] $label (node runtime unavailable)"
        GP_FAIL[$g]=$((GP_FAIL[$g]+1)); TOTAL_FAIL=$((TOTAL_FAIL+1))
        return
    fi
    if ! compile_out=$($VIRC "$test" --target wasm32 -q -o "$wasm_path" 2>&1); then
        echo "  [FAIL-WASM-COMPILE] $label"
        echo "$compile_out" | sed 's/^/    /' | head -20
        GP_FAIL[$g]=$((GP_FAIL[$g]+1)); TOTAL_FAIL=$((TOTAL_FAIL+1))
        return
    fi
    actual=$(node --no-warnings --experimental-wasi-unstable-preview1 -e '
        const fs = require("fs");
        const { WASI } = require("wasi");
        const wasi = new WASI({ version: "preview1", args: [], env: {} });
        WebAssembly.instantiate(fs.readFileSync(process.argv[1]), {
            wasi_snapshot_preview1: wasi.wasiImport
        }).then(({ instance }) => wasi.start(instance));
    ' "$wasm_path" 2>&1)
    rc=$?
    if [ $rc -eq 0 ] && [ "$actual" = "$expected" ]; then
        echo "  [PASS-WASM] $label"
        GP_PASS[$g]=$((GP_PASS[$g]+1)); TOTAL_PASS=$((TOTAL_PASS+1))
    else
        echo "  [FAIL-WASM-RUNTIME] $label (exit code: $rc)"
        echo "    Kỳ vọng: '$expected'"
        echo "    Thực tế: '$actual'"
        GP_FAIL[$g]=$((GP_FAIL[$g]+1)); TOTAL_FAIL=$((TOTAL_FAIL+1))
    fi
}

run_interp_mc_target() {
    local g=31
    local target="$1"
    local asm_path="./scratch/interp_${target}.s"
    local symbol="rt_bool_to_str"
    local compile_out
    if [ "$target" = "macos-arm64" ]; then symbol="_rt_bool_to_str"; fi
    if compile_out=$($VIRC "tests/strict_v2/interpolation_dynamic_primitives.vri" --target "$target" -S -o "$asm_path" -q 2>&1) \
        && [ "$(grep -Fc "$symbol" "$asm_path")" -ge 2 ]; then
        echo "  [PASS-MC] interpolation $target assembly"
        GP_PASS[$g]=$((GP_PASS[$g]+1)); TOTAL_PASS=$((TOTAL_PASS+1))
        return
    fi
    echo "  [FAIL-MC] interpolation $target assembly"
    if [ -n "$compile_out" ]; then echo "$compile_out" | sed 's/^/    /' | head -20; fi
    GP_FAIL[$g]=$((GP_FAIL[$g]+1)); TOTAL_FAIL=$((TOTAL_FAIL+1))
}

echo "=========================================================================="
if [ "$MODE" = "single" ]; then
    echo "  VIR COMPILER TEST SUITE — NHÓM $TARGET_GROUP"
else
    MODE_UPPER=$(echo "$MODE" | tr '[:lower:]' '[:upper:]')
    echo "  VIR COMPILER TEST SUITE — CHẾ ĐỘ [$MODE_UPPER]"
fi
echo "=========================================================================="
echo ""

run_group_1() {
    echo "──────────────────────────────────────────────────────────────────────────"
    echo "► Nhóm  1: Tổng quan (§1.0 Separator, §1.1 Mở khối, §1.2 Pipeline IR)"
    echo "──────────────────────────────────────────────────────────────────────────"
    if [ "$MODE" = "min" ]; then
        run_test_in_group 1 "tests/vri/test_48.vri"
        run_test_in_group 1 "tests/vri/test_add.vri"
        run_test_in_group 1 "tests/vri/test_add_rt.vri"
    else
        run_test_in_group 1 "tests/vri/test_48.vri"
        run_test_in_group 1 "tests/vri/test_add.vri"
        run_test_in_group 1 "tests/vri/test_add_rt.vri"
        run_test_in_group 1 "tests/vri/test_add_rt2.vri"
        run_test_in_group 1 "tests/vri/test_adv_003_divzero.vri"
        run_test_in_group 1 "tests/vri/test_adv_008_neg_not.vri"
        run_test_in_group 1 "tests/vri/test_adv_011_mem_offsets.vri"
        run_test_in_group 1 "tests/vri/test_adv_012_byte_rw.vri"
        run_test_in_group 1 "tests/vri/test_adv_015_large_alloc.vri"
        run_test_in_group 1 "tests/vri/test_adv_016_memset.vri"
        run_test_in_group 1 "tests/vri/test_adv_019_heap_frag.vri"
        run_test_in_group 1 "tests/vri/test_adv_020_memcopy.vri"
        run_test_in_group 1 "tests/vri/test_adv_021_nested5.vri"
        run_test_in_group 1 "tests/vri/test_adv_027_dead_code.vri"
        run_test_in_group 1 "tests/vri/test_adv_031_raw_write.vri"
        run_test_in_group 1 "tests/vri/test_adv_032_bubblesort.vri"
        run_test_in_group 1 "tests/vri/test_adv_038_hex.vri"
        run_test_in_group 1 "tests/vri/test_adv_048_linked_list.vri"
        run_test_in_group 1 "tests/vri/test_adv_050_aliasing.vri"
        run_test_in_group 1 "tests/vri/test_adv_051_bsearch.vri"
        run_test_in_group 1 "tests/vri/test_adv_052_gcd.vri"
        run_test_in_group 1 "tests/vri/test_adv_054_sieve.vri"
        run_test_in_group 1 "tests/vri/test_adv_060_spill30.vri"
        run_test_in_group 1 "tests/vri/test_adv_061_dead_store.vri"
        run_test_in_group 1 "tests/vri/test_adv_062_inline.vri"
        run_test_in_group 1 "tests/vri/test_adv_064_unused_arg.vri"
        run_test_in_group 1 "tests/vri/test_adv_065_redundant_load.vri"
        run_test_in_group 1 "tests/vri/test_adv_066_unroll.vri"
        run_test_in_group 1 "tests/vri/test_adv_067_bce.vri"
        run_test_in_group 1 "tests/vri/test_adv_074_minimal.vri"
        run_test_in_group 1 "tests/vri/test_adv_088_hanoi.vri"
        run_test_in_group 1 "tests/vri/test_adv_089_minmax.vri"
        run_test_in_group 1 "tests/vri/test_adv_091_tree.vri"
        run_test_in_group 1 "tests/vri/test_adv_092_compose.vri"
        run_test_in_group 1 "tests/vri/test_adv_094_reduce.vri"
        run_test_in_group 1 "tests/vri/test_adv_095_mutual_deep.vri"
        run_test_in_group 1 "tests/vri/test_adv_096_digit_sum.vri"
        run_test_in_group 1 "tests/vri/test_adv_098_large_arr.vri"
        run_test_in_group 1 "tests/vri/test_dot_simple.vri"
        run_test_in_group 1 "tests/vri/test_hello.vri"
        run_test_in_group 1 "tests/vri/test_nested_if.vri"
        run_test_in_group 1 "tests/vri/test_reassign.vri"
        run_test_in_group 1 "tests/vri/test_spill.vri"
        run_test_in_group 1 "tests/vri/test_this.vri"
    fi
    local pass_cnt=${GP_PASS[1]}
    local fail_cnt=${GP_FAIL[1]}
    local total_cnt=$((pass_cnt + fail_cnt))
    echo "  ↳ Kết quả Nhóm 1: $pass_cnt/$total_cnt PASS"
    echo ""
}

run_group_2() {
    echo "──────────────────────────────────────────────────────────────────────────"
    echo "► Nhóm  2: Chú thích (Comments)"
    echo "──────────────────────────────────────────────────────────────────────────"
    if [ "$MODE" = "min" ]; then
        run_test_in_group 2 "tests/bootstrap_codegen/cg_comment.vri"
        run_test_in_group 2 "tests/bootstrap_codegen/cg_edge_comment_eof.vri"
    else
        run_test_in_group 2 "tests/bootstrap_codegen/cg_comment.vri"
        run_test_in_group 2 "tests/bootstrap_codegen/cg_edge_comment_eof.vri"
    fi
    local pass_cnt=${GP_PASS[2]}
    local fail_cnt=${GP_FAIL[2]}
    local total_cnt=$((pass_cnt + fail_cnt))
    echo "  ↳ Kết quả Nhóm 2: $pass_cnt/$total_cnt PASS"
    echo ""
}

run_group_3() {
    echo "──────────────────────────────────────────────────────────────────────────"
    echo "► Nhóm  3: Hệ thống Module (include, import, export)"
    echo "──────────────────────────────────────────────────────────────────────────"
    if [ "$MODE" = "min" ]; then
        run_test_in_group 3 "tests/bootstrap_codegen/cg_include_basic.vri"
        run_test_in_group 3 "tests/bootstrap_codegen/cg_include_nested.vri"
        run_test_in_group 3 "tests/test_expose.vri"
        run_test_in_group 3 "tests/strict_v2/module_double_colon_rejected.vri"
        run_test_in_group 3 "tests/strict_v2/include_double_colon_rejected.vri"
        run_test_in_group 3 "tests/strict_v2/import_double_colon_rejected.vri"
        run_test_in_group 3 "tests/strict_v2/double_colon_in_data_e2e.vri"
    else
        run_test_in_group 3 "tests/bootstrap_codegen/cg_include_basic.vri"
        run_test_in_group 3 "tests/bootstrap_codegen/cg_include_nested.vri"
        run_test_in_group 3 "tests/test_expose.vri"
        run_test_in_group 3 "tests/strict_v2/module_double_colon_rejected.vri"
        run_test_in_group 3 "tests/strict_v2/include_double_colon_rejected.vri"
        run_test_in_group 3 "tests/strict_v2/import_double_colon_rejected.vri"
        run_test_in_group 3 "tests/strict_v2/double_colon_in_data_e2e.vri"
        run_test_in_group 3 "tests/test_module_system.vri"
        run_test_in_group 3 "tests/test_vir_pkg_native.vri"
        run_test_in_group 3 "tests/vri/test_expose.vri"
    fi
    local pass_cnt=${GP_PASS[3]}
    local fail_cnt=${GP_FAIL[3]}
    local total_cnt=$((pass_cnt + fail_cnt))
    echo "  ↳ Kết quả Nhóm 3: $pass_cnt/$total_cnt PASS"
    echo ""
}

run_group_4() {
    echo "──────────────────────────────────────────────────────────────────────────"
    echo "► Nhóm  4: Kiểu dữ liệu (Primitives, Casts, Nil-safety)"
    echo "──────────────────────────────────────────────────────────────────────────"
    if [ "$MODE" = "min" ]; then
        run_test_in_group 4 "tests/test_adv_001_i64_max.vri"
        run_test_in_group 4 "tests/test_adv_009_bool_chain.vri"
        run_test_in_group 4 "tests/test_cast_probe.vri"
    else
        run_test_in_group 4 "tests/test_adv_001_i64_max.vri"
        run_test_in_group 4 "tests/test_adv_009_bool_chain.vri"
        run_test_in_group 4 "tests/test_cast_probe.vri"
        run_test_in_group 4 "tests/test_float.vri"
        run_test_in_group 4 "tests/test_float2.vri"
        run_test_in_group 4 "tests/test_float3.vri"
        run_test_in_group 4 "tests/test_float4.vri"
        run_test_in_group 4 "tests/test_float_check.vri"
        run_test_in_group 4 "tests/test_float_literal_boundaries.vri"
        run_test_in_group 4 "tests/test_float_literal_e2e.vri"
        run_test_in_group 4 "tests/test_float_rw.vri"
        run_test_in_group 4 "tests/vri/test_adv_001_i64_max.vri"
        run_test_in_group 4 "tests/vri/test_adv_009_bool_chain.vri"
    fi
    local pass_cnt=${GP_PASS[4]}
    local fail_cnt=${GP_FAIL[4]}
    local total_cnt=$((pass_cnt + fail_cnt))
    echo "  ↳ Kết quả Nhóm 4: $pass_cnt/$total_cnt PASS"
    echo ""
}

run_group_5() {
    echo "──────────────────────────────────────────────────────────────────────────"
    echo "► Nhóm  5: Biến & Hằng số (var, let, const, Scoping)"
    echo "──────────────────────────────────────────────────────────────────────────"
    if [ "$MODE" = "min" ]; then
        run_test_in_group 5 "tests/test_10vars.vri"
        run_test_in_group 5 "tests/test_1p_novar.vri"
        run_test_in_group 5 "tests/test_adv_018_global_local.vri"
    else
        run_test_in_group 5 "tests/test_10vars.vri"
        run_test_in_group 5 "tests/test_1p_novar.vri"
        run_test_in_group 5 "tests/test_adv_018_global_local.vri"
        run_test_in_group 5 "tests/test_adv_059_shadowing.vri"
        run_test_in_group 5 "tests/test_adv_063_const_prop.vri"
        run_test_in_group 5 "tests/test_adv_086_global_counter.vri"
        run_test_in_group 5 "tests/test_global.vri"
        run_test_in_group 5 "tests/test_global2.vri"
        run_test_in_group 5 "tests/test_global_do.vri"
        run_test_in_group 5 "tests/test_ident.vri"
        run_test_in_group 5 "tests/test_let.vri"
        run_test_in_group 5 "tests/test_pass_ident.vri"
        run_test_in_group 5 "tests/vri/test_1p_novar.vri"
        run_test_in_group 5 "tests/vri/test_adv_018_global_local.vri"
        run_test_in_group 5 "tests/vri/test_adv_059_shadowing.vri"
        run_test_in_group 5 "tests/vri/test_adv_063_const_prop.vri"
        run_test_in_group 5 "tests/vri/test_adv_086_global_counter.vri"
        run_test_in_group 5 "tests/vri/test_global.vri"
        run_test_in_group 5 "tests/vri/test_global2.vri"
        run_test_in_group 5 "tests/vri/test_global_do.vri"
        run_test_in_group 5 "tests/vri/test_let.vri"
        run_test_in_group 5 "tests/vri/test_var_expr.vri"
        run_test_in_group 5 "tests/vri/test_var_ident.vri"
        run_test_in_group 5 "tests/vri/test_var_literal.vri"
        run_test_in_group 5 "tests/vri/test_var_one.vri"
    fi
    local pass_cnt=${GP_PASS[5]}
    local fail_cnt=${GP_FAIL[5]}
    local total_cnt=$((pass_cnt + fail_cnt))
    echo "  ↳ Kết quả Nhóm 5: $pass_cnt/$total_cnt PASS"
    echo ""
}

run_group_6() {
    echo "──────────────────────────────────────────────────────────────────────────"
    echo "► Nhóm  6: Hàm (Functions, out, Recursion, TCO)"
    echo "──────────────────────────────────────────────────────────────────────────"
    if [ "$MODE" = "min" ]; then
        run_test_in_group 6 "tests/boot_in_form2_call.vri"
        run_test_in_group 6 "tests/test_2var_loop_call.vri"
        run_test_in_group 6 "tests/test_adv_013_deep_recursion.vri"
    else
        run_test_in_group 6 "tests/boot_in_form2_call.vri"
        run_test_in_group 6 "tests/test_2var_loop_call.vri"
        run_test_in_group 6 "tests/test_adv_013_deep_recursion.vri"
        run_test_in_group 6 "tests/test_adv_023_tailcall.vri"
        run_test_in_group 6 "tests/test_adv_056_callee_save.vri"
        run_test_in_group 6 "tests/test_adv_057_func_ptr_arr.vri"
        run_test_in_group 6 "tests/test_adv_068_accum_func.vri"
        run_test_in_group 6 "tests/test_adv_076_fib_iter.vri"
        run_test_in_group 6 "tests/vri/test_2var_loop_call.vri"
        run_test_in_group 6 "tests/vri/test_adv_013_deep_recursion.vri"
        run_test_in_group 6 "tests/vri/test_adv_023_tailcall.vri"
        run_test_in_group 6 "tests/vri/test_adv_056_callee_save.vri"
        run_test_in_group 6 "tests/vri/test_adv_057_func_ptr_arr.vri"
        run_test_in_group 6 "tests/vri/test_adv_068_accum_func.vri"
        run_test_in_group 6 "tests/vri/test_adv_076_fib_iter.vri"
        run_test_in_group 6 "tests/vri/test_adv_085_nested_call.vri"
        run_test_in_group 6 "tests/vri/test_adv_090_deep_call.vri"
        run_test_in_group 6 "tests/vri/test_call.vri"
        run_test_in_group 6 "tests/vri/test_call2.vri"
        run_test_in_group 6 "tests/vri/test_eif_func.vri"
        run_test_in_group 6 "tests/vri/test_fib.vri"
        run_test_in_group 6 "tests/vri/test_fib5.vri"
        run_test_in_group 6 "tests/vri/test_func.vri"
        run_test_in_group 6 "tests/vri/test_func_call.vri"
        run_test_in_group 6 "tests/vri/test_func_simple.vri"
        run_test_in_group 6 "tests/vri/test_hof.vri"
        run_test_in_group 6 "tests/vri/test_if_func.vri"
        run_test_in_group 6 "tests/vri/test_loop_call.vri"
        run_test_in_group 6 "tests/vri/test_multi_func.vri"
        run_test_in_group 6 "tests/vri/test_mutual_recursion.vri"
        run_test_in_group 6 "tests/vri/test_prime.vri"
        run_test_in_group 6 "tests/vri/test_prime2.vri"
        run_test_in_group 6 "tests/vri/test_prime3.vri"
        run_test_in_group 6 "tests/vri/test_prime_simple.vri"
        run_test_in_group 6 "tests/vri/test_recursion.vri"
    fi
    local pass_cnt=${GP_PASS[6]}
    local fail_cnt=${GP_FAIL[6]}
    local total_cnt=$((pass_cnt + fail_cnt))
    echo "  ↳ Kết quả Nhóm 6: $pass_cnt/$total_cnt PASS"
    echo ""
}

run_group_7() {
    echo "──────────────────────────────────────────────────────────────────────────"
    echo "► Nhóm  7: Entity & Packed Entity (Structs, Fields, Methods)"
    echo "──────────────────────────────────────────────────────────────────────────"
    if [ "$MODE" = "min" ]; then
        run_test_in_group 7 "tests/vri/test_3vars.vri"
        run_test_in_group 7 "tests/vri/test_6vars.vri"
        run_test_in_group 7 "tests/vri/test_adv_017_struct_fields.vri"
        run_test_in_group 7 "tests/strict_v2/packed_layout_mixed_width_e2e.vri"
        run_test_in_group 7 "tests/strict_v2/packed_missing_field_type_rejected.vri"
    else
        run_test_in_group 7 "tests/vri/test_3vars.vri"
        run_test_in_group 7 "tests/vri/test_6vars.vri"
        run_test_in_group 7 "tests/vri/test_adv_017_struct_fields.vri"
        run_test_in_group 7 "tests/vri/test_adv_029_algebra.vri"
        run_test_in_group 7 "tests/vri/test_adv_041_nested_entity.vri"
        run_test_in_group 7 "tests/vri/test_adv_042_arr_entity.vri"
        run_test_in_group 7 "tests/vri/test_adv_043_entity_return.vri"
        run_test_in_group 7 "tests/vri/test_adv_044_entity_param.vri"
        run_test_in_group 7 "tests/vri/test_adv_045_big_entity.vri"
        run_test_in_group 7 "tests/vri/test_adv_046_entity_mutate.vri"
        run_test_in_group 7 "tests/vri/test_adv_058_multi_return.vri"
        run_test_in_group 7 "tests/vri/test_adv_099_distance.vri"
        run_test_in_group 7 "tests/vri/test_adv_100_stress.vri"
        run_test_in_group 7 "tests/vri/test_aggregate_return_large_entity.vri"
        run_test_in_group 7 "tests/vri/test_aggregate_return_string_field_preserved.vri"
        run_test_in_group 7 "tests/vri/test_aggregate_return_string_int_combos.vri"
        run_test_in_group 7 "tests/vri/test_comma.vri"
        run_test_in_group 7 "tests/vri/test_comma_nl.vri"
        run_test_in_group 7 "tests/vri/test_complex.vri"
        run_test_in_group 7 "tests/vri/test_complex2.vri"
        run_test_in_group 7 "tests/vri/test_dot_entity.vri"
        run_test_in_group 7 "tests/vri/test_dot_entity2.vri"
        run_test_in_group 7 "tests/vri/test_eif_entity.vri"
        run_test_in_group 7 "tests/vri/test_entity.vri"
        run_test_in_group 7 "tests/vri/test_entity_advanced.vri"
        run_test_in_group 7 "tests/vri/test_entity_astnode5.vri"
        run_test_in_group 7 "tests/vri/test_entity_basic.vri"
        run_test_in_group 7 "tests/vri/test_entity_bug.vri"
        run_test_in_group 7 "tests/vri/test_entity_bug11_nl.vri"
        run_test_in_group 7 "tests/vri/test_entity_bug2.vri"
        run_test_in_group 7 "tests/vri/test_entity_bug3.vri"
        run_test_in_group 7 "tests/vri/test_entity_full.vri"
        run_test_in_group 7 "tests/vri/test_entity_multi.vri"
        run_test_in_group 7 "tests/vri/test_entity_paren.vri"
        run_test_in_group 7 "tests/vri/test_entity_rect.vri"
        run_test_in_group 7 "tests/vri/test_if_dot.vri"
        run_test_in_group 7 "tests/vri/test_method.vri"
        run_test_in_group 7 "tests/vri/test_packed.vri"
        run_test_in_group 7 "tests/strict_v2/packed_layout_mixed_width_e2e.vri"
        run_test_in_group 7 "tests/strict_v2/packed_named_initializer_order_e2e.vri"
        run_test_in_group 7 "tests/strict_v2/packed_unaligned_mutation_e2e.vri"
        run_test_in_group 7 "tests/strict_v2/packed_signed_load_e2e.vri"
        run_test_in_group 7 "tests/strict_v2/packed_nested_layout_e2e.vri"
        run_test_in_group 7 "tests/strict_v2/packed_method_layout_e2e.vri"
        run_test_in_group 7 "tests/strict_v2/packed_sizeof_e2e.vri"
        run_test_in_group 7 "tests/strict_v2/packed_missing_field_type_rejected.vri"
        run_test_in_group 7 "tests/strict_v2/packed_dynamic_field_rejected.vri"
        run_test_in_group 7 "tests/strict_v2/packed_nonpacked_nested_rejected.vri"
        run_test_in_group 7 "tests/strict_v2/packed_recursive_layout_rejected.vri"
        run_test_in_group 7 "tests/strict_v2/packed_shorthand_rejected.vri"
        run_test_in_group 7 "tests/strict_v2/packed_constructor_missing_field_rejected.vri"
        run_test_in_group 7 "tests/strict_v2/packed_constructor_duplicate_field_rejected.vri"
        run_test_in_group 7 "tests/strict_v2/packed_constructor_unknown_field_rejected.vri"
        run_test_in_group 7 "tests/strict_v2/packed_u8_overflow_rejected.vri"
        run_test_in_group 7 "tests/strict_v2/packed_u8_underflow_rejected.vri"
    fi
    local pass_cnt=${GP_PASS[7]}
    local fail_cnt=${GP_FAIL[7]}
    local total_cnt=$((pass_cnt + fail_cnt))
    echo "  ↳ Kết quả Nhóm 7: $pass_cnt/$total_cnt PASS"
    echo ""
}

run_group_8() {
    echo "──────────────────────────────────────────────────────────────────────────"
    echo "► Nhóm  8: Enum (Tagged unions, Variants)"
    echo "──────────────────────────────────────────────────────────────────────────"
    if [ "$MODE" = "min" ]; then
        run_test_in_group 8 "tests/test_adv_047_enum_control.vri"
        run_test_in_group 8 "tests/test_adv_081_multi_enum.vri"
        run_test_in_group 8 "tests/test_entity_enum_array.vri"
        run_test_in_group 8 "tests/strict_v2/test_enum_tagged_union_e2e.vri"
        run_test_in_group 8 "tests/strict_v2/test_option_result_enum_e2e.vri"
        run_test_in_group 8 "tests/strict_v2/enum_double_colon_constructor_rejected.vri"
        run_test_in_group 8 "tests/strict_v2/enum_double_colon_pattern_rejected.vri"
        run_test_in_group 8 "tests/strict_v2/test_enum_qualified_collision.vri"
        run_test_in_group 8 "tests/strict_v2/test_enum_complex_payload_e2e.vri"
        run_test_in_group 8 "tests/strict_v2/test_explicit_tags.vri"
        run_test_in_group 8 "tests/strict_v2/test_no_tags.vri"
        run_test_in_group 8 "tests/strict_v2/enum_constructor_arity_rejected.vri"
        run_test_in_group 8 "tests/strict_v2/enum_wrong_binder_count_rejected.vri"
        run_test_in_group 8 "tests/strict_v2/enum_unknown_variant_rejected.vri"
        run_test_in_group 8 "tests/strict_v2/enum_wrong_enum_qualifier_rejected.vri"
        run_test_in_group 8 "tests/strict_v2/enum_duplicate_arm_rejected.vri"
        run_test_in_group 8 "tests/strict_v2/enum_unreachable_arm_rejected.vri"
        run_test_in_group 8 "tests/strict_v2/enum_non_exhaustive_rejected.vri"
        run_test_in_group 8 "tests/strict_v2/enum_duplicate_binder_rejected.vri"
        run_test_in_group 8 "tests/strict_v2/enum_duplicate_tag_rejected.vri"
        run_test_in_group 8 "tests/strict_v2/enum_invalid_tag_range_rejected.vri"
        run_test_in_group 8 "tests/strict_v2/enum_generic_type_mismatch_rejected.vri"
        run_test_in_group 8 "tests/strict_v2/enum_payload_equality_rejected.vri"
        run_test_in_group 8 "tests/strict_v2/enum_ambiguous_unqualified_rejected.vri"
    else
        run_test_in_group 8 "tests/test_adv_047_enum_control.vri"
        run_test_in_group 8 "tests/test_adv_081_multi_enum.vri"
        run_test_in_group 8 "tests/test_entity_enum_array.vri"
        run_test_in_group 8 "tests/test_enum_paren.vri"
        run_test_in_group 8 "tests/strict_v2/test_enum_tagged_union_e2e.vri"
        run_test_in_group 8 "tests/strict_v2/test_option_result_enum_e2e.vri"
        run_test_in_group 8 "tests/strict_v2/enum_double_colon_constructor_rejected.vri"
        run_test_in_group 8 "tests/strict_v2/enum_double_colon_pattern_rejected.vri"
        run_test_in_group 8 "tests/strict_v2/test_enum_qualified_collision.vri"
        run_test_in_group 8 "tests/strict_v2/test_enum_complex_payload_e2e.vri"
        run_test_in_group 8 "tests/strict_v2/test_explicit_tags.vri"
        run_test_in_group 8 "tests/strict_v2/test_no_tags.vri"
        run_test_in_group 8 "tests/strict_v2/enum_constructor_arity_rejected.vri"
        run_test_in_group 8 "tests/strict_v2/enum_wrong_binder_count_rejected.vri"
        run_test_in_group 8 "tests/strict_v2/enum_unknown_variant_rejected.vri"
        run_test_in_group 8 "tests/strict_v2/enum_wrong_enum_qualifier_rejected.vri"
        run_test_in_group 8 "tests/strict_v2/enum_duplicate_arm_rejected.vri"
        run_test_in_group 8 "tests/strict_v2/enum_unreachable_arm_rejected.vri"
        run_test_in_group 8 "tests/strict_v2/enum_non_exhaustive_rejected.vri"
        run_test_in_group 8 "tests/strict_v2/enum_duplicate_binder_rejected.vri"
        run_test_in_group 8 "tests/strict_v2/enum_duplicate_tag_rejected.vri"
        run_test_in_group 8 "tests/strict_v2/enum_invalid_tag_range_rejected.vri"
        run_test_in_group 8 "tests/strict_v2/enum_generic_type_mismatch_rejected.vri"
        run_test_in_group 8 "tests/strict_v2/enum_payload_equality_rejected.vri"
        run_test_in_group 8 "tests/strict_v2/enum_ambiguous_unqualified_rejected.vri"
        run_test_in_group 8 "tests/vri/test_adv_047_enum_control.vri"
        run_test_in_group 8 "tests/vri/test_adv_081_multi_enum.vri"
        run_test_in_group 8 "tests/vri/test_entity_enum_array.vri"
        run_test_in_group 8 "tests/vri/test_enum_paren.vri"
    fi
    run_enum_mc_target "macos-arm64"
    run_enum_mc_target "linux-x86_64"
    run_enum_mc_target "linux-riscv64"
    local pass_cnt=${GP_PASS[8]}
    local fail_cnt=${GP_FAIL[8]}
    local total_cnt=$((pass_cnt + fail_cnt))
    echo "  ↳ Kết quả Nhóm 8: $pass_cnt/$total_cnt PASS"
    echo ""
}

run_group_9() {
    echo "──────────────────────────────────────────────────────────────────────────"
    echo "► Nhóm  9: Luồng điều khiển (if, eif, else, when, for, skip, break)"
    echo "──────────────────────────────────────────────────────────────────────────"
    if [ "$MODE" = "min" ]; then
        run_test_in_group 9 "tests/test_2var_loop.vri"
        run_test_in_group 9 "tests/test_adv_025_nested_break.vri"
        run_test_in_group 9 "tests/test_adv_075_perf_loop.vri"
    else
        run_test_in_group 9 "tests/test_2var_loop.vri"
        run_test_in_group 9 "tests/test_adv_025_nested_break.vri"
        run_test_in_group 9 "tests/test_adv_075_perf_loop.vri"
        run_test_in_group 9 "tests/vri/test_2var_loop.vri"
        run_test_in_group 9 "tests/vri/test_adv_025_nested_break.vri"
        run_test_in_group 9 "tests/vri/test_adv_075_perf_loop.vri"
        run_test_in_group 9 "tests/vri/test_adv_077_collatz.vri"
        run_test_in_group 9 "tests/vri/test_adv_082_eif_classify.vri"
        run_test_in_group 9 "tests/vri/test_adv_083_for_break.vri"
        run_test_in_group 9 "tests/vri/test_adv_084_for_skip.vri"
        run_test_in_group 9 "tests/vri/test_break.vri"
        run_test_in_group 9 "tests/vri/test_control.vri"
        run_test_in_group 9 "tests/vri/test_eif.vri"
        run_test_in_group 9 "tests/vri/test_eif2.vri"
        run_test_in_group 9 "tests/vri/test_eif_global.vri"
        run_test_in_group 9 "tests/vri/test_for_accum.vri"
        run_test_in_group 9 "tests/vri/test_for_range.vri"
        run_test_in_group 9 "tests/vri/test_if_assign.vri"
        run_test_in_group 9 "tests/vri/test_if_else.vri"
        run_test_in_group 9 "tests/vri/test_if_exit.vri"
        run_test_in_group 9 "tests/vri/test_if_exit2.vri"
        run_test_in_group 9 "tests/vri/test_if_false.vri"
        run_test_in_group 9 "tests/vri/test_if_in_loop.vri"
        run_test_in_group 9 "tests/vri/test_if_in_loop2.vri"
        run_test_in_group 9 "tests/vri/test_if_noelse.vri"
        run_test_in_group 9 "tests/vri/test_if_simple.vri"
        run_test_in_group 9 "tests/vri/test_if_sub.vri"
        run_test_in_group 9 "tests/vri/test_if_var.vri"
        run_test_in_group 9 "tests/vri/test_if_var2.vri"
        run_test_in_group 9 "tests/vri/test_loop_n.vri"
        run_test_in_group 9 "tests/vri/test_nested_while.vri"
        run_test_in_group 9 "tests/vri/test_skip.vri"
        run_test_in_group 9 "tests/vri/test_var_loop.vri"
        run_test_in_group 9 "tests/vri/test_while.vri"
        run_test_in_group 9 "tests/vri/test_while_simple.vri"
    fi
    local pass_cnt=${GP_PASS[9]}
    local fail_cnt=${GP_FAIL[9]}
    local total_cnt=$((pass_cnt + fail_cnt))
    echo "  ↳ Kết quả Nhóm 9: $pass_cnt/$total_cnt PASS"
    echo ""
}

run_group_10() {
    echo "──────────────────────────────────────────────────────────────────────────"
    echo "► Nhóm 10: Toán tử (Arithmetic, Bitwise, Logic, mod)"
    echo "──────────────────────────────────────────────────────────────────────────"
    if [ "$MODE" = "min" ]; then
        run_test_in_group 10 "tests/test_adv_002_overflow.vri"
        run_test_in_group 10 "tests/test_adv_004_bitwise.vri"
        run_test_in_group 10 "tests/test_adv_005_shift.vri"
        run_test_in_group 10 "tests/strict_v2/percent_operator_e2e.vri"
        run_test_in_group 10 "tests/strict_v2/test_percent_combination_e2e.vri"
        run_test_in_group 10 "tests/strict_v2/percent_codegen_smoke_e2e.vri"
        run_test_in_group 10 "tests/strict_v2/percent_binary_rejected.vri"
        run_test_in_group 10 "tests/strict_v2/percent_prefix_rejected.vri"
        run_test_in_group 10 "tests/strict_v2/percent_string_rejected.vri"
        run_test_in_group 10 "tests/strict_v2/percent_bool_rejected.vri"
    else
        run_test_in_group 10 "tests/test_adv_002_overflow.vri"
        run_test_in_group 10 "tests/test_adv_004_bitwise.vri"
        run_test_in_group 10 "tests/test_adv_005_shift.vri"
        run_test_in_group 10 "tests/test_adv_007_bitops_edge.vri"
        run_test_in_group 10 "tests/test_adv_053_power.vri"
        run_test_in_group 10 "tests/test_adv_069_shift_chain.vri"
        run_test_in_group 10 "tests/test_adv_070_bit_arith.vri"
        run_test_in_group 10 "tests/test_adv_097_bit_manip.vri"
        run_test_in_group 10 "tests/test_arithmetic.vri"
        run_test_in_group 10 "tests/test_bit_min.vri"
        run_test_in_group 10 "tests/test_bit_min2.vri"
        run_test_in_group 10 "tests/strict_v2/percent_operator_e2e.vri"
        run_test_in_group 10 "tests/strict_v2/test_percent_combination_e2e.vri"
        run_test_in_group 10 "tests/strict_v2/percent_codegen_smoke_e2e.vri"
        run_test_in_group 10 "tests/strict_v2/percent_binary_rejected.vri"
        run_test_in_group 10 "tests/strict_v2/percent_prefix_rejected.vri"
        run_test_in_group 10 "tests/strict_v2/percent_string_rejected.vri"
        run_test_in_group 10 "tests/strict_v2/percent_bool_rejected.vri"
        run_test_in_group 10 "tests/vri/test_adv_002_overflow.vri"
        run_test_in_group 10 "tests/vri/test_adv_004_bitwise.vri"
        run_test_in_group 10 "tests/vri/test_adv_005_shift.vri"
        run_test_in_group 10 "tests/vri/test_adv_007_bitops_edge.vri"
        run_test_in_group 10 "tests/vri/test_adv_053_power.vri"
        run_test_in_group 10 "tests/vri/test_adv_069_shift_chain.vri"
        run_test_in_group 10 "tests/vri/test_adv_070_bit_arith.vri"
        run_test_in_group 10 "tests/vri/test_adv_097_bit_manip.vri"
        run_test_in_group 10 "tests/vri/test_arithmetic.vri"
        run_test_in_group 10 "tests/vri/test_bit_min.vri"
        run_test_in_group 10 "tests/vri/test_bit_tmp.vri"
        run_test_in_group 10 "tests/vri/test_int64_overflow_wrapping.vri"
        run_test_in_group 10 "tests/vri/test_mod_rt.vri"
        run_test_in_group 10 "tests/vri/test_modulo_kw.vri"
        run_test_in_group 10 "tests/vri/test_modulo_op.vri"
        run_test_in_group 10 "tests/vri/test_popcnt_min.vri"
        run_test_in_group 10 "tests/vri/test_rshift_only.vri"
        run_test_in_group 10 "tests/vri/test_shift3.vri"
        run_test_in_group 10 "tests/vri/test_shift5.vri"
        run_test_in_group 10 "tests/vri/test_shift6.vri"
        run_test_in_group 10 "tests/vri/test_shift_all_left.vri"
        run_test_in_group 10 "tests/vri/test_shift_debug.vri"
        run_test_in_group 10 "tests/vri/test_adv_006_mod_neg.vri"
    fi
    local pass_cnt=${GP_PASS[10]}
    local fail_cnt=${GP_FAIL[10]}
    local total_cnt=$((pass_cnt + fail_cnt))
    echo "  ↳ Kết quả Nhóm 10: $pass_cnt/$total_cnt PASS"
    echo ""
}

run_group_11() {
    echo "──────────────────────────────────────────────────────────────────────────"
    echo "► Nhóm 11: UFCS (Uniform Function Call Syntax)"
    echo "──────────────────────────────────────────────────────────────────────────"
    if [ "$MODE" = "min" ]; then
        run_test_in_group 11 "tests/strict_v2/ufcs_callable_field_wrong_arity_rejected.vri"
        run_test_in_group 11 "tests/strict_v2/ufcs_callable_field_wrong_type_rejected.vri"
        run_test_in_group 11 "tests/strict_v2/ufcs_free_arg_wrong_type_rejected.vri"
        run_test_in_group 11 "tests/strict_v2/ufcs_receiver_forms_e2e.vri"
        run_test_in_group 11 "tests/strict_v2/ufcs_eval_order_e2e.vri"
        run_test_in_group 11 "tests/strict_v2/ufcs_cross_type_chain_e2e.vri"
        run_test_in_group 11 "tests/strict_v2/ufcs_declaration_order_e2e.vri"
        run_test_in_group 11 "tests/bootstrap_codegen/cg_ufcs_strict_resolution.vri"
    else
        run_test_in_group 11 "tests/strict_v2/ufcs_callable_field_wrong_arity_rejected.vri"
        run_test_in_group 11 "tests/strict_v2/ufcs_callable_field_wrong_type_rejected.vri"
        run_test_in_group 11 "tests/strict_v2/ufcs_free_arg_wrong_type_rejected.vri"
        run_test_in_group 11 "tests/strict_v2/ufcs_free_entity_receiver_wrong_type_rejected.vri"
        run_test_in_group 11 "tests/strict_v2/ufcs_free_receiver_wrong_type_rejected.vri"
        run_test_in_group 11 "tests/strict_v2/ufcs_missing_member_rejected.vri"
        run_test_in_group 11 "tests/strict_v2/ufcs_non_callable_field_rejected.vri"
        run_test_in_group 11 "tests/strict_v2/ufcs_opaque_pointer_member_rejected.vri"
        run_test_in_group 11 "tests/strict_v2/ufcs_other_entity_method_rejected.vri"
        run_test_in_group 11 "tests/strict_v2/ufcs_pointer_field_rejected.vri"
        run_test_in_group 11 "tests/strict_v2/ufcs_port_missing_member_rejected.vri"
        run_test_in_group 11 "tests/strict_v2/ufcs_port_wrong_arity_rejected.vri"
        run_test_in_group 11 "tests/strict_v2/ufcs_port_wrong_type_rejected.vri"
        run_test_in_group 11 "tests/strict_v2/ufcs_too_many_args_rejected.vri"
        run_test_in_group 11 "tests/strict_v2/ufcs_wrong_arity_rejected.vri"
        run_test_in_group 11 "tests/strict_v2/ufcs_wrong_type_rejected.vri"
        run_test_in_group 11 "tests/strict_v2/ufcs_receiver_forms_e2e.vri"
        run_test_in_group 11 "tests/strict_v2/ufcs_eval_order_e2e.vri"
        run_test_in_group 11 "tests/strict_v2/ufcs_cross_type_chain_e2e.vri"
        run_test_in_group 11 "tests/strict_v2/ufcs_declaration_order_e2e.vri"
        run_test_in_group 11 "tests/strict_v2/ufcs_method_field_same_name_rejected.vri"
        run_test_in_group 11 "tests/strict_v2/ufcs_private_module_rejected.vri"
        run_test_in_group 11 "tests/strict_v2/ufcs_receiver_mutation_e2e.vri"
        run_test_in_group 11 "tests/strict_v2/ufcs_nested_reg_pressure_e2e.vri"
        run_test_in_group 11 "tests/strict_v2/ufcs_optional_chaining_rejected.vri"
        run_test_in_group 11 "tests/bootstrap_codegen/cg_ufcs_strict_resolution.vri"
        run_test_in_group 11 "tests/vri/test_ufcs.vri"
    fi
    run_ufcs_mc_target "linux-arm64"
    run_ufcs_mc_target "linux-x86_64"
    run_ufcs_mc_target "linux-riscv64"
    local pass_cnt=${GP_PASS[11]}
    local fail_cnt=${GP_FAIL[11]}
    local total_cnt=$((pass_cnt + fail_cnt))
    echo "  ↳ Kết quả Nhóm 11: $pass_cnt/$total_cnt PASS"
    echo ""
}

run_group_12() {
    echo "──────────────────────────────────────────────────────────────────────────"
    echo "► Nhóm 12: Nội suy chuỗi & Thao tác chuỗi"
    echo "──────────────────────────────────────────────────────────────────────────"
    if [ "$MODE" = "min" ]; then
        run_test_in_group 12 "tests/test_adv_024_branch_stress.vri"
        run_test_in_group 12 "tests/test_adv_028_strength_reduce.vri"
        run_test_in_group 12 "tests/test_adv_034_strcat_chain.vri"
    else
        run_test_in_group 12 "tests/test_adv_024_branch_stress.vri"
        run_test_in_group 12 "tests/test_adv_028_strength_reduce.vri"
        run_test_in_group 12 "tests/test_adv_034_strcat_chain.vri"
        run_test_in_group 12 "tests/test_adv_036_strlen.vri"
        run_test_in_group 12 "tests/test_adv_037_itoa.vri"
        run_test_in_group 12 "tests/test_adv_039_streq.vri"
        run_test_in_group 12 "tests/test_adv_040_str_get.vri"
        run_test_in_group 12 "tests/test_debug_str.vri"
        run_test_in_group 12 "tests/test_interp.vri"
        run_test_in_group 12 "tests/test_itoa.vri"
        run_test_in_group 12 "tests/test_rt_strcmp_out_in_loop.vri"
        run_test_in_group 12 "tests/vri/test_adv_024_branch_stress.vri"
        run_test_in_group 12 "tests/vri/test_adv_028_strength_reduce.vri"
        run_test_in_group 12 "tests/vri/test_adv_034_strcat_chain.vri"
        run_test_in_group 12 "tests/vri/test_adv_036_strlen.vri"
        run_test_in_group 12 "tests/vri/test_adv_037_itoa.vri"
        run_test_in_group 12 "tests/vri/test_adv_039_streq.vri"
        run_test_in_group 12 "tests/vri/test_adv_040_str_get.vri"
        run_test_in_group 12 "tests/vri/test_interp.vri"
        run_test_in_group 12 "tests/vri/test_str_concat.vri"
        run_test_in_group 12 "tests/vri/test_str_func.vri"
        run_test_in_group 12 "tests/vri/test_str_loop.vri"
        run_test_in_group 12 "tests/vri/test_str_multi.vri"
        run_test_in_group 12 "tests/vri/test_str_var.vri"
    fi
    local pass_cnt=${GP_PASS[12]}
    local fail_cnt=${GP_FAIL[12]}
    local total_cnt=$((pass_cnt + fail_cnt))
    echo "  ↳ Kết quả Nhóm 12: $pass_cnt/$total_cnt PASS"
    echo ""
}

run_group_13() {
    echo "──────────────────────────────────────────────────────────────────────────"
    echo "► Nhóm 13: Xử lý lỗi (throw, try, ensure, revert)"
    echo "──────────────────────────────────────────────────────────────────────────"
    if [ "$MODE" = "min" ]; then
        run_test_in_group 13 "tests/test_ensure.vri"
        run_test_in_group 13 "tests/test_nll_release.vri"
        run_test_in_group 13 "tests/test_throw.vri"
    else
        run_test_in_group 13 "tests/test_ensure.vri"
        run_test_in_group 13 "tests/test_nll_release.vri"
        run_test_in_group 13 "tests/test_throw.vri"
        run_test_in_group 13 "tests/test_try_isolate_retry.vri"
        run_test_in_group 13 "tests/test_try_revert.vri"
        run_test_in_group 13 "tests/test_try_timeout.vri"
        run_test_in_group 13 "tests/vri/test_ensure.vri"
        run_test_in_group 13 "tests/vri/test_nll_release.vri"
        run_test_in_group 13 "tests/vri/test_throw.vri"
        run_test_in_group 13 "tests/vri/test_try_isolate_retry.vri"
        run_test_in_group 13 "tests/vri/test_try_timeout.vri"
    fi
    local pass_cnt=${GP_PASS[13]}
    local fail_cnt=${GP_FAIL[13]}
    local total_cnt=$((pass_cnt + fail_cnt))
    echo "  ↳ Kết quả Nhóm 13: $pass_cnt/$total_cnt PASS"
    echo ""
}

run_group_14() {
    echo "──────────────────────────────────────────────────────────────────────────"
    echo "► Nhóm 14: Tham số (in, ref, out)"
    echo "──────────────────────────────────────────────────────────────────────────"
    if [ "$MODE" = "min" ]; then
        run_test_in_group 14 "tests/test_4param_global.vri"
        run_test_in_group 14 "tests/test_4param_rec.vri"
        run_test_in_group 14 "tests/test_adv_014_many_params.vri"
    else
        run_test_in_group 14 "tests/test_4param_global.vri"
        run_test_in_group 14 "tests/test_4param_rec.vri"
        run_test_in_group 14 "tests/test_adv_014_many_params.vri"
        run_test_in_group 14 "tests/test_param_n.vri"
        run_test_in_group 14 "tests/test_params_nl.vri"
        run_test_in_group 14 "tests/test_ref.vri"
        run_test_in_group 14 "tests/vri/test_4param_global.vri"
        run_test_in_group 14 "tests/vri/test_4param_rec.vri"
        run_test_in_group 14 "tests/vri/test_adv_014_many_params.vri"
        run_test_in_group 14 "tests/vri/test_param_n.vri"
        run_test_in_group 14 "tests/vri/test_ref.vri"
        run_test_in_group 14 "tests/vri/test_var_2param.vri"
    fi
    local pass_cnt=${GP_PASS[14]}
    local fail_cnt=${GP_FAIL[14]}
    local total_cnt=$((pass_cnt + fail_cnt))
    echo "  ↳ Kết quả Nhóm 14: $pass_cnt/$total_cnt PASS"
    echo ""
}

run_group_15() {
    echo "──────────────────────────────────────────────────────────────────────────"
    echo "► Nhóm 15: FFI & Tương tác Hệ điều hành (@bind, syscall, OS)"
    echo "──────────────────────────────────────────────────────────────────────────"
    if [ "$MODE" = "min" ]; then
        run_test_in_group 15 "tests/strict_v2/test_ffi_macos.vri"
        run_test_in_group 15 "tests/strict_v2/test_ffi_multi.vri"
        run_test_in_group 15 "tests/test_extern_from_os.vri"
    else
        run_test_in_group 15 "tests/strict_v2/test_ffi_macos.vri"
        run_test_in_group 15 "tests/strict_v2/test_ffi_multi.vri"
        run_test_in_group 15 "tests/test_extern_from_os.vri"
        run_test_in_group 15 "tests/test_syscall.vri"
        run_test_in_group 15 "tests/vri/test_bind.vri"
        run_test_in_group 15 "tests/vri/test_syscall.vri"
        run_test_in_group 15 "tests/test_bind.vri"
    fi
    local pass_cnt=${GP_PASS[15]}
    local fail_cnt=${GP_FAIL[15]}
    local total_cnt=$((pass_cnt + fail_cnt))
    echo "  ↳ Kết quả Nhóm 15: $pass_cnt/$total_cnt PASS"
    echo ""
}

run_group_16() {
    echo "──────────────────────────────────────────────────────────────────────────"
    echo "► Nhóm 16: Register & Mold (Bit structures, pack)"
    echo "──────────────────────────────────────────────────────────────────────────"
    if [ "$MODE" = "min" ]; then
        run_test_in_group 16 "tests/test_register.vri"
        run_test_in_group 16 "tests/vri/test_register.vri"
    else
        run_test_in_group 16 "tests/test_register.vri"
        run_test_in_group 16 "tests/vri/test_register.vri"
    fi
    local pass_cnt=${GP_PASS[16]}
    local fail_cnt=${GP_FAIL[16]}
    local total_cnt=$((pass_cnt + fail_cnt))
    echo "  ↳ Kết quả Nhóm 16: $pass_cnt/$total_cnt PASS"
    echo ""
}

run_group_17() {
    echo "──────────────────────────────────────────────────────────────────────────"
    echo "► Nhóm 17: Thực thi lúc biên dịch (precomp, const fold)"
    echo "──────────────────────────────────────────────────────────────────────────"
    if [ "$MODE" = "min" ]; then
        run_test_in_group 17 "tests/test_adv_026_const_fold.vri"
        run_test_in_group 17 "tests/test_str_len_fold.vri"
        run_test_in_group 17 "tests/vri/test_adv_026_const_fold.vri"
    else
        run_test_in_group 17 "tests/test_adv_026_const_fold.vri"
        run_test_in_group 17 "tests/test_str_len_fold.vri"
        run_test_in_group 17 "tests/vri/test_adv_026_const_fold.vri"
        run_test_in_group 17 "tests/test_precomp.vri"
    fi
    local pass_cnt=${GP_PASS[17]}
    local fail_cnt=${GP_FAIL[17]}
    local total_cnt=$((pass_cnt + fail_cnt))
    echo "  ↳ Kết quả Nhóm 17: $pass_cnt/$total_cnt PASS"
    echo ""
}

run_group_18() {
    echo "──────────────────────────────────────────────────────────────────────────"
    echo "► Nhóm 18: Điểm nhập (@entry, main, CLI args)"
    echo "──────────────────────────────────────────────────────────────────────────"
    if [ "$MODE" = "min" ]; then
        run_test_in_group 18 "tests/bootstrap_codegen/cg_getarg.vri"
        run_test_in_group 18 "tests/test_adv_071_exit_code.vri"
        run_test_in_group 18 "tests/test_arg_count.vri"
    else
        run_test_in_group 18 "tests/bootstrap_codegen/cg_getarg.vri"
        run_test_in_group 18 "tests/test_adv_071_exit_code.vri"
        run_test_in_group 18 "tests/test_arg_count.vri"
        run_test_in_group 18 "tests/test_helper_argc.vri"
        run_test_in_group 18 "tests/vri/test_adv_071_exit_code.vri"
        run_test_in_group 18 "tests/test_argc.vri"
    fi
    local pass_cnt=${GP_PASS[18]}
    local fail_cnt=${GP_FAIL[18]}
    local total_cnt=$((pass_cnt + fail_cnt))
    echo "  ↳ Kết quả Nhóm 18: $pass_cnt/$total_cnt PASS"
    echo ""
}

run_group_19() {
    echo "──────────────────────────────────────────────────────────────────────────"
    echo "► Nhóm 19: Mảng (Arrays, Indexing, Slices)"
    echo "──────────────────────────────────────────────────────────────────────────"
    if [ "$MODE" = "min" ]; then
        run_test_in_group 19 "tests/bootstrap_codegen/cg_array_indexing.vri"
        run_test_in_group 19 "tests/bootstrap_codegen/cg_array_len.vri"
        run_test_in_group 19 "tests/bootstrap_codegen/cg_array_literal.vri"
    else
        run_test_in_group 19 "tests/bootstrap_codegen/cg_array_indexing.vri"
        run_test_in_group 19 "tests/bootstrap_codegen/cg_array_len.vri"
        run_test_in_group 19 "tests/bootstrap_codegen/cg_array_literal.vri"
        run_test_in_group 19 "tests/test_adv_049_arr_init.vri"
        run_test_in_group 19 "tests/test_adv_078_reverse.vri"
        run_test_in_group 19 "tests/test_adv_087_isort.vri"
        run_test_in_group 19 "tests/test_arr_after_var.vri"
        run_test_in_group 19 "tests/test_arr_min.vri"
        run_test_in_group 19 "tests/test_arr_reorder.vri"
        run_test_in_group 19 "tests/test_array_basic.vri"
        run_test_in_group 19 "tests/test_array_literal.vri"
        run_test_in_group 19 "tests/test_array_loop.vri"
        run_test_in_group 19 "tests/test_array_set.vri"
        run_test_in_group 19 "tests/test_array_simple.vri"
        run_test_in_group 19 "tests/test_vec_loop.vri"
        run_test_in_group 19 "tests/vri/test_adv_049_arr_init.vri"
        run_test_in_group 19 "tests/vri/test_adv_078_reverse.vri"
        run_test_in_group 19 "tests/vri/test_adv_079_stack_calc.vri"
        run_test_in_group 19 "tests/vri/test_adv_087_isort.vri"
        run_test_in_group 19 "tests/vri/test_array_literal.vri"
        run_test_in_group 19 "tests/vri/test_array_loop.vri"
        run_test_in_group 19 "tests/vri/test_array_set.vri"
        run_test_in_group 19 "tests/test_adv_079_stack_calc.vri"
        run_test_in_group 19 "tests/vri/test_arr_after_var.vri"
        run_test_in_group 19 "tests/vri/test_array_basic.vri"
    fi
    local pass_cnt=${GP_PASS[19]}
    local fail_cnt=${GP_FAIL[19]}
    local total_cnt=$((pass_cnt + fail_cnt))
    echo "  ↳ Kết quả Nhóm 19: $pass_cnt/$total_cnt PASS"
    echo ""
}

run_group_20() {
    echo "──────────────────────────────────────────────────────────────────────────"
    echo "► Nhóm 20: Dict & Map (Key-value collections)"
    echo "──────────────────────────────────────────────────────────────────────────"
    if [ "$MODE" = "min" ]; then
        run_test_in_group 20 "tests/test_adv_072_mmap.vri"
        run_test_in_group 20 "tests/test_adv_080_hash.vri"
        run_test_in_group 20 "tests/test_adv_093_map.vri"
    else
        run_test_in_group 20 "tests/test_adv_072_mmap.vri"
        run_test_in_group 20 "tests/test_adv_080_hash.vri"
        run_test_in_group 20 "tests/test_adv_093_map.vri"
        run_test_in_group 20 "tests/test_dict_int.vri"
        run_test_in_group 20 "tests/vri/test_adv_072_mmap.vri"
        run_test_in_group 20 "tests/vri/test_adv_080_hash.vri"
        run_test_in_group 20 "tests/vri/test_adv_093_map.vri"
        run_test_in_group 20 "tests/vri/test_dict_int.vri"
    fi
    local pass_cnt=${GP_PASS[20]}
    local fail_cnt=${GP_FAIL[20]}
    local total_cnt=$((pass_cnt + fail_cnt))
    echo "  ↳ Kết quả Nhóm 20: $pass_cnt/$total_cnt PASS"
    echo ""
}

run_group_21() {
    echo "──────────────────────────────────────────────────────────────────────────"
    echo "► Nhóm 21: Biểu thức Case & Pattern Matching"
    echo "──────────────────────────────────────────────────────────────────────────"
    if [ "$MODE" = "min" ]; then
        run_test_in_group 21 "tests/bootstrap_codegen/cg_mem_loop_pattern.vri"
        run_test_in_group 21 "tests/test_adv_022_switch_case.vri"
        run_test_in_group 21 "tests/test_case_real.vri"
        run_test_in_group 21 "tests/strict_v2/test_case_grammar_e2e.vri"
        run_test_in_group 21 "tests/strict_v2/test_case_control_flow_e2e.vri"
        run_test_in_group 21 "tests/strict_v2/case_else_colon_rejected.vri"
        run_test_in_group 21 "tests/strict_v2/case_empty_arm_rejected.vri"
        run_test_in_group 21 "tests/strict_v2/case_binder_scope_rejected.vri"
        run_test_in_group 21 "tests/strict_v2/case_literal_type_mismatch_rejected.vri"
    else
        run_test_in_group 21 "tests/bootstrap_codegen/cg_mem_loop_pattern.vri"
        run_test_in_group 21 "tests/test_adv_022_switch_case.vri"
        run_test_in_group 21 "tests/test_case_real.vri"
        run_test_in_group 21 "tests/test_case_spec.vri"
        run_test_in_group 21 "tests/test_virc_patterns.vri"
        run_test_in_group 21 "tests/vri/test_adv_022_switch_case.vri"
        run_test_in_group 21 "tests/vri/test_case_real.vri"
        run_test_in_group 21 "tests/vri/test_case_spec.vri"
        run_test_in_group 21 "tests/vri/test_virc_patterns.vri"
        run_test_in_group 21 "tests/strict_v2/test_case_grammar_e2e.vri"
        run_test_in_group 21 "tests/strict_v2/test_case_control_flow_e2e.vri"
        run_test_in_group 21 "tests/strict_v2/case_else_colon_rejected.vri"
        run_test_in_group 21 "tests/strict_v2/case_missing_arm_colon_rejected.vri"
        run_test_in_group 21 "tests/strict_v2/case_empty_arm_rejected.vri"
        run_test_in_group 21 "tests/strict_v2/case_repeated_keyword_rejected.vri"
        run_test_in_group 21 "tests/strict_v2/case_no_pattern_arm_rejected.vri"
        run_test_in_group 21 "tests/strict_v2/case_empty_else_rejected.vri"
        run_test_in_group 21 "tests/strict_v2/case_header_colon_rejected.vri"
        run_test_in_group 21 "tests/strict_v2/case_binder_scope_rejected.vri"
        run_test_in_group 21 "tests/strict_v2/case_literal_type_mismatch_rejected.vri"
        run_test_in_group 21 "tests/strict_v2/case_bool_type_mismatch_rejected.vri"
        run_test_in_group 21 "tests/strict_v2/case_arbitrary_expr_pattern_rejected.vri"
        run_test_in_group 21 "tests/strict_v2/case_duplicate_else_rejected.vri"
        run_test_in_group 21 "tests/strict_v2/case_arm_after_else_rejected.vri"
        run_test_in_group 21 "tests/strict_v2/case_end_dot_rejected.vri"
        run_test_in_group 21 "tests/strict_v2/case_missing_end_rejected.vri"
    fi
    run_case_mc_target "linux-arm64"
    run_case_mc_target "linux-x86_64"
    run_case_mc_target "linux-riscv64"
    local pass_cnt=${GP_PASS[21]}
    local fail_cnt=${GP_FAIL[21]}
    local total_cnt=$((pass_cnt + fail_cnt))
    echo "  ↳ Kết quả Nhóm 21: $pass_cnt/$total_cnt PASS"
    echo ""
}

run_group_22() {
    echo "──────────────────────────────────────────────────────────────────────────"
    echo "► Nhóm 22: Async & Task (Concurrency)"
    echo "──────────────────────────────────────────────────────────────────────────"
    if [ "$MODE" = "min" ]; then
        run_test_in_group 22 "tests/test_async_call.vri"
        run_test_in_group 22 "tests/test_await.vri"
        run_test_in_group 22 "tests/test_await_pass_main.vri"
    else
        run_test_in_group 22 "tests/test_async_call.vri"
        run_test_in_group 22 "tests/test_await.vri"
        run_test_in_group 22 "tests/test_await_pass_main.vri"
        run_test_in_group 22 "tests/vri/test_async_call.vri"
        run_test_in_group 22 "tests/vri/test_async_min.vri"
        run_test_in_group 22 "tests/vri/test_await.vri"
        run_test_in_group 22 "tests/vri/test_await_pass.vri"
        run_test_in_group 22 "tests/vri/test_await_simple.vri"
        run_test_in_group 22 "tests/vri/test_await_v2.vri"
        run_test_in_group 22 "tests/test_async_min.vri"
        run_test_in_group 22 "tests/test_await_pass.vri"
        run_test_in_group 22 "tests/test_await_simple.vri"
        run_test_in_group 22 "tests/test_await_v2.vri"
    fi
    local pass_cnt=${GP_PASS[22]}
    local fail_cnt=${GP_FAIL[22]}
    local total_cnt=$((pass_cnt + fail_cnt))
    echo "  ↳ Kết quả Nhóm 22: $pass_cnt/$total_cnt PASS"
    echo ""
}

run_group_23() {
    echo "──────────────────────────────────────────────────────────────────────────"
    echo "► Nhóm 23: Port & Worker Channels (send, recv)"
    echo "──────────────────────────────────────────────────────────────────────────"
    if [ "$MODE" = "min" ]; then
        run_test_in_group 23 "tests/bootstrap_codegen/cg_mod_import.vri"
    else
        run_test_in_group 23 "tests/bootstrap_codegen/cg_mod_import.vri"
    fi
    local pass_cnt=${GP_PASS[23]}
    local fail_cnt=${GP_FAIL[23]}
    local total_cnt=$((pass_cnt + fail_cnt))
    echo "  ↳ Kết quả Nhóm 23: $pass_cnt/$total_cnt PASS"
    echo ""
}

run_group_24() {
    echo "──────────────────────────────────────────────────────────────────────────"
    echo "► Nhóm 24: GPU, SIMD & Atomic Primitives"
    echo "──────────────────────────────────────────────────────────────────────────"
    if [ "$MODE" = "min" ]; then
        run_test_in_group 24 "tests/test_atomic_isolate.vri"
        run_test_in_group 24 "tests/test_atomic_var.vri"
    else
        run_test_in_group 24 "tests/test_atomic_isolate.vri"
        run_test_in_group 24 "tests/test_atomic_var.vri"
    fi
    local pass_cnt=${GP_PASS[24]}
    local fail_cnt=${GP_FAIL[24]}
    local total_cnt=$((pass_cnt + fail_cnt))
    echo "  ↳ Kết quả Nhóm 24: $pass_cnt/$total_cnt PASS"
    echo ""
}

run_group_25() {
    echo "──────────────────────────────────────────────────────────────────────────"
    echo "► Nhóm 25: UI & Reactive Primitives"
    echo "──────────────────────────────────────────────────────────────────────────"
    if [ "$MODE" = "min" ]; then
        run_test_in_group 25 "tests/bootstrap_codegen/cg_str_builtins.vri"
        run_test_in_group 25 "tests/test_adv_035_quicksort.vri"
        run_test_in_group 25 "tests/test_reactive.vri"
    else
        run_test_in_group 25 "tests/bootstrap_codegen/cg_str_builtins.vri"
        run_test_in_group 25 "tests/test_adv_035_quicksort.vri"
        run_test_in_group 25 "tests/test_reactive.vri"
        run_test_in_group 25 "tests/vri/test_adv_035_quicksort.vri"
        run_test_in_group 25 "tests/vri/test_adv_055_str_build.vri"
        run_test_in_group 25 "tests/test_adv_055_str_build.vri"
    fi
    local pass_cnt=${GP_PASS[25]}
    local fail_cnt=${GP_FAIL[25]}
    local total_cnt=$((pass_cnt + fail_cnt))
    echo "  ↳ Kết quả Nhóm 25: $pass_cnt/$total_cnt PASS"
    echo ""
}

run_group_26() {
    echo "──────────────────────────────────────────────────────────────────────────"
    echo "► Nhóm 26: AI & Học máy (Tensor, MatMul **, FMA, Infer, Train, Quantize)"
    echo "──────────────────────────────────────────────────────────────────────────"
    if [ "$MODE" = "min" ]; then
        run_test_in_group 26 "tests/strict_v2/test_spec26_ai_huge_proof.vri"
        run_test_in_group 26 "tests/strict_v2/fma_tensor_e2e.vri"
        run_test_in_group 26 "tests/strict_v2/fma_float_rectangular_e2e.vri"
        run_test_in_group 26 "tests/strict_v2/test_float_matmul_e2e.vri"
        run_test_in_group 26 "tests/test_adv_030_fma.vri"
        run_test_in_group 26 "tests/test_adv_033_matmul.vri"
    else
        run_test_in_group 26 "tests/strict_v2/test_spec26_ai_huge_proof.vri"
        run_test_in_group 26 "tests/strict_v2/fma_tensor_e2e.vri"
        run_test_in_group 26 "tests/strict_v2/fma_float_rectangular_e2e.vri"
        run_test_in_group 26 "tests/strict_v2/test_autodiff_e2e.vri"
        run_test_in_group 26 "tests/strict_v2/test_quantize_e2e.vri"
        run_test_in_group 26 "tests/strict_v2/quantize_frontend_positive.vri"
        run_test_in_group 26 "tests/strict_v2/test_float_matmul_e2e.vri"
        run_test_in_group 26 "tests/strict_v2/backward_outside_train_negative.vri"
        run_test_in_group 26 "tests/strict_v2/fma_element_negative.vri"
        run_test_in_group 26 "tests/strict_v2/fma_scalar_negative.vri"
        run_test_in_group 26 "tests/strict_v2/fma_shape_negative.vri"
        run_test_in_group 26 "tests/strict_v2/infer_backward_negative.vri"
        run_test_in_group 26 "tests/strict_v2/infer_train_nested_negative.vri"
        run_test_in_group 26 "tests/strict_v2/quantize_bits_negative.vri"
        run_test_in_group 26 "tests/strict_v2/quantize_dynamic_bits_negative.vri"
        run_test_in_group 26 "tests/strict_v2/quantize_input_negative.vri"
        run_test_in_group 26 "tests/strict_v2/quantize_integer_tensor_negative.vri"
        run_test_in_group 26 "tests/strict_v2/tensor_empty_shape_negative.vri"
        run_test_in_group 26 "tests/strict_v2/tensor_zero_dimension_negative.vri"
        run_test_in_group 26 "tests/strict_v2/train_backward_external_negative.vri"
        run_test_in_group 26 "tests/strict_v2/train_backward_integer_negative.vri"
        run_test_in_group 26 "tests/test_adv_030_fma.vri"
        run_test_in_group 26 "tests/test_adv_033_matmul.vri"
        run_test_in_group 26 "tests/test_arena_api.vri"
        run_test_in_group 26 "tests/test_first_class_matmul_rect.vri"
        run_test_in_group 26 "tests/test_neon_matmul_4x4.vri"
        run_test_in_group 26 "tests/test_print_c.vri"
        run_test_in_group 26 "tests/test_probe_01.vri"
        run_test_in_group 26 "tests/vri/test_adv_030_fma.vri"
        run_test_in_group 26 "tests/vri/test_adv_033_matmul.vri"
        run_test_in_group 26 "tests/vri/test_spec20_compiler_features.vri"
        run_test_in_group 26 "tests/vri/test_tensor_matmul.vri"
        run_test_in_group 26 "tests/vri/test_tensor_ml_ops.vri"
        run_test_in_group 26 "tests/vri/test_infer_zero_tape.vri"
        run_test_in_group 26 "tests/test_first_class_tensor.vri"
    fi
    local pass_cnt=${GP_PASS[26]}
    local fail_cnt=${GP_FAIL[26]}
    local total_cnt=$((pass_cnt + fail_cnt))
    echo "  ↳ Kết quả Nhóm 26: $pass_cnt/$total_cnt PASS"
    echo ""
}

run_group_27() {
    echo "──────────────────────────────────────────────────────────────────────────"
    echo "► Nhóm 27: Intrinsics hệ thống (Memory read/write, low-level)"
    echo "──────────────────────────────────────────────────────────────────────────"
    if [ "$MODE" = "min" ]; then
        run_test_in_group 27 "tests/test_intrinsics.vri"
        run_test_in_group 27 "tests/test_native_read_u8.vri"
        run_test_in_group 27 "tests/test_rw64.vri"
    else
        run_test_in_group 27 "tests/test_intrinsics.vri"
        run_test_in_group 27 "tests/test_native_read_u8.vri"
        run_test_in_group 27 "tests/test_rw64.vri"
        run_test_in_group 27 "tests/test_volatile.vri"
        run_test_in_group 27 "tests/vri/test_intrinsics.vri"
    fi
    local pass_cnt=${GP_PASS[27]}
    local fail_cnt=${GP_FAIL[27]}
    local total_cnt=$((pass_cnt + fail_cnt))
    echo "  ↳ Kết quả Nhóm 27: $pass_cnt/$total_cnt PASS"
    echo ""
}

run_group_28() {
    echo "──────────────────────────────────────────────────────────────────────────"
    echo "► Nhóm 28: Hỗ trợ đa ngôn ngữ (UTF-8, String encoding)"
    echo "──────────────────────────────────────────────────────────────────────────"
    if [ "$MODE" = "min" ]; then
        run_test_in_group 28 "tests/virgex_date.vri"
    else
        run_test_in_group 28 "tests/virgex_date.vri"
    fi
    local pass_cnt=${GP_PASS[28]}
    local fail_cnt=${GP_FAIL[28]}
    local total_cnt=$((pass_cnt + fail_cnt))
    echo "  ↳ Kết quả Nhóm 28: $pass_cnt/$total_cnt PASS"
    echo ""
}

run_group_29() {
    echo "──────────────────────────────────────────────────────────────────────────"
    echo "► Nhóm 29: Từ khoá tham chiếu & Diagnostic Tests"
    echo "──────────────────────────────────────────────────────────────────────────"
    if [ "$MODE" = "min" ]; then
        run_test_in_group 29 "tests/test_kw_valid.vri"
    else
        run_test_in_group 29 "tests/test_kw_valid.vri"
    fi
    local pass_cnt=${GP_PASS[29]}
    local fail_cnt=${GP_FAIL[29]}
    local total_cnt=$((pass_cnt + fail_cnt))
    echo "  ↳ Kết quả Nhóm 29: $pass_cnt/$total_cnt PASS"
    echo ""
}

run_group_30() {
    echo "──────────────────────────────────────────────────────────────────────────"
    echo "► Nhóm 30: Bảng ưu tiên toán tử (Operator Precedence)"
    echo "──────────────────────────────────────────────────────────────────────────"
    if [ "$MODE" = "min" ]; then
        run_test_in_group 30 "tests/test_adv_073_deep_expr.vri"
        run_test_in_group 30 "tests/vri/test_adv_010_precedence.vri"
        run_test_in_group 30 "tests/vri/test_adv_073_deep_expr.vri"
        run_test_in_group 30 "tests/strict_v2/test_percent_combination_e2e.vri"
    else
        run_test_in_group 30 "tests/test_adv_073_deep_expr.vri"
        run_test_in_group 30 "tests/vri/test_adv_010_precedence.vri"
        run_test_in_group 30 "tests/vri/test_adv_073_deep_expr.vri"
        run_test_in_group 30 "tests/strict_v2/test_percent_combination_e2e.vri"
    fi
    local pass_cnt=${GP_PASS[30]}
    local fail_cnt=${GP_FAIL[30]}
    local total_cnt=$((pass_cnt + fail_cnt))
    echo "  ↳ Kết quả Nhóm 30: $pass_cnt/$total_cnt PASS"
    echo ""
}

run_group_31() {
    echo "──────────────────────────────────────────────────────────────────────────"
    echo "► Nhóm 31: Thay đổi so với v1.2 (Strict v2.0 Conformance)"
    echo "──────────────────────────────────────────────────────────────────────────"
    if [ "$MODE" = "min" ]; then
        run_test_in_group 31 "tests/strict_v2/e2e_interp_matrix.vri"
        run_test_in_group 31 "tests/strict_v2/e2e_string_interpolation.vri"
        run_test_in_group 31 "tests/strict_v2/interpolation_dynamic_primitives.vri"
        run_test_in_group 31 "tests/strict_v2/interpolation_edge_values_e2e.vri"
        run_test_in_group 31 "tests/strict_v2/interpolation_negative_integer_e2e.vri"
        run_test_in_group 31 "tests/strict_v2/interpolation_float_rejected.vri"
        run_test_in_group 31 "tests/strict_v2/interpolation_array_shorthand_rejected.vri"
        run_test_in_group 31 "tests/strict_v2/interpolation_malformed_rejected.vri"
    else
        run_test_in_group 31 "tests/strict_v2/e2e_interp_matrix.vri"
        run_test_in_group 31 "tests/strict_v2/e2e_string_interpolation.vri"
        run_test_in_group 31 "tests/strict_v2/interpolation_dynamic_primitives.vri"
        run_test_in_group 31 "tests/strict_v2/interpolation_edge_values_e2e.vri"
        run_test_in_group 31 "tests/strict_v2/interpolation_negative_integer_e2e.vri"
        run_test_in_group 31 "tests/strict_v2/interpolation_float_rejected.vri"
        run_test_in_group 31 "tests/strict_v2/interpolation_array_shorthand_rejected.vri"
        run_test_in_group 31 "tests/strict_v2/interpolation_malformed_rejected.vri"
        run_test_in_group 31 "tests/test_interp_v2.vri"
    fi
    run_interp_wasm_target "tests/strict_v2/interpolation_dynamic_primitives.vri" "n=42; ok=true; nope=false; nothing=none; sum=43" "dynamic_primitives"
    run_interp_wasm_target "tests/strict_v2/interpolation_negative_integer_e2e.vri" "negative=-42" "negative_integer"
    run_interp_mc_target "macos-arm64"
    run_interp_mc_target "linux-x86_64"
    run_interp_mc_target "linux-riscv64"
    local pass_cnt=${GP_PASS[31]}
    local fail_cnt=${GP_FAIL[31]}
    local total_cnt=$((pass_cnt + fail_cnt))
    echo "  ↳ Kết quả Nhóm 31: $pass_cnt/$total_cnt PASS"
    echo ""
}

if [ "$MODE" = "single" ]; then
    "run_group_$TARGET_GROUP"
else
    run_group_1
    run_group_2
    run_group_3
    run_group_4
    run_group_5
    run_group_6
    run_group_7
    run_group_8
    run_group_9
    run_group_10
    run_group_11
    run_group_12
    run_group_13
    run_group_14
    run_group_15
    run_group_16
    run_group_17
    run_group_18
    run_group_19
    run_group_20
    run_group_21
    run_group_22
    run_group_23
    run_group_24
    run_group_25
    run_group_26
    run_group_27
    run_group_28
    run_group_29
    run_group_30
    run_group_31
fi

echo "=========================================================================="
echo "                    BẢNG TỔNG KẾT KẾT QUẢ TEST THEO NHÓM                 "
echo "=========================================================================="
printf "%-4s | %-52s | %-5s | %-5s | %-5s\n" "Mục" "Tên Nhóm Phân Loại Spec v2.0" "PASS" "FAIL" "TỔNG"
echo "-----+------------------------------------------------------+-------+-------+------"
if [ "$MODE" != "single" ] || [ "$TARGET_GROUP" = "1" ]; then
    printf "§%-3d | %-52s | %-5d | %-5d | %-5d\n" 1 "Tổng quan (§1.0 Separator, §1.1 Mở khối, §1.2 Pip..." ${GP_PASS[1]} ${GP_FAIL[1]} $((GP_PASS[1] + GP_FAIL[1]))
fi
if [ "$MODE" != "single" ] || [ "$TARGET_GROUP" = "2" ]; then
    printf "§%-3d | %-52s | %-5d | %-5d | %-5d\n" 2 "Chú thích (Comments)" ${GP_PASS[2]} ${GP_FAIL[2]} $((GP_PASS[2] + GP_FAIL[2]))
fi
if [ "$MODE" != "single" ] || [ "$TARGET_GROUP" = "3" ]; then
    printf "§%-3d | %-52s | %-5d | %-5d | %-5d\n" 3 "Hệ thống Module (include, import, export)" ${GP_PASS[3]} ${GP_FAIL[3]} $((GP_PASS[3] + GP_FAIL[3]))
fi
if [ "$MODE" != "single" ] || [ "$TARGET_GROUP" = "4" ]; then
    printf "§%-3d | %-52s | %-5d | %-5d | %-5d\n" 4 "Kiểu dữ liệu (Primitives, Casts, Nil-safety)" ${GP_PASS[4]} ${GP_FAIL[4]} $((GP_PASS[4] + GP_FAIL[4]))
fi
if [ "$MODE" != "single" ] || [ "$TARGET_GROUP" = "5" ]; then
    printf "§%-3d | %-52s | %-5d | %-5d | %-5d\n" 5 "Biến & Hằng số (var, let, const, Scoping)" ${GP_PASS[5]} ${GP_FAIL[5]} $((GP_PASS[5] + GP_FAIL[5]))
fi
if [ "$MODE" != "single" ] || [ "$TARGET_GROUP" = "6" ]; then
    printf "§%-3d | %-52s | %-5d | %-5d | %-5d\n" 6 "Hàm (Functions, out, Recursion, TCO)" ${GP_PASS[6]} ${GP_FAIL[6]} $((GP_PASS[6] + GP_FAIL[6]))
fi
if [ "$MODE" != "single" ] || [ "$TARGET_GROUP" = "7" ]; then
    printf "§%-3d | %-52s | %-5d | %-5d | %-5d\n" 7 "Entity & Packed Entity (Structs, Fields, Methods)" ${GP_PASS[7]} ${GP_FAIL[7]} $((GP_PASS[7] + GP_FAIL[7]))
fi
if [ "$MODE" != "single" ] || [ "$TARGET_GROUP" = "8" ]; then
    printf "§%-3d | %-52s | %-5d | %-5d | %-5d\n" 8 "Enum (Tagged unions, Variants)" ${GP_PASS[8]} ${GP_FAIL[8]} $((GP_PASS[8] + GP_FAIL[8]))
fi
if [ "$MODE" != "single" ] || [ "$TARGET_GROUP" = "9" ]; then
    printf "§%-3d | %-52s | %-5d | %-5d | %-5d\n" 9 "Luồng điều khiển (if, eif, else, when, for, skip,..." ${GP_PASS[9]} ${GP_FAIL[9]} $((GP_PASS[9] + GP_FAIL[9]))
fi
if [ "$MODE" != "single" ] || [ "$TARGET_GROUP" = "10" ]; then
    printf "§%-3d | %-52s | %-5d | %-5d | %-5d\n" 10 "Toán tử (Arithmetic, Bitwise, Logic, mod)" ${GP_PASS[10]} ${GP_FAIL[10]} $((GP_PASS[10] + GP_FAIL[10]))
fi
if [ "$MODE" != "single" ] || [ "$TARGET_GROUP" = "11" ]; then
    printf "§%-3d | %-52s | %-5d | %-5d | %-5d\n" 11 "UFCS (Uniform Function Call Syntax)" ${GP_PASS[11]} ${GP_FAIL[11]} $((GP_PASS[11] + GP_FAIL[11]))
fi
if [ "$MODE" != "single" ] || [ "$TARGET_GROUP" = "12" ]; then
    printf "§%-3d | %-52s | %-5d | %-5d | %-5d\n" 12 "Nội suy chuỗi & Thao tác chuỗi" ${GP_PASS[12]} ${GP_FAIL[12]} $((GP_PASS[12] + GP_FAIL[12]))
fi
if [ "$MODE" != "single" ] || [ "$TARGET_GROUP" = "13" ]; then
    printf "§%-3d | %-52s | %-5d | %-5d | %-5d\n" 13 "Xử lý lỗi (throw, try, ensure, revert)" ${GP_PASS[13]} ${GP_FAIL[13]} $((GP_PASS[13] + GP_FAIL[13]))
fi
if [ "$MODE" != "single" ] || [ "$TARGET_GROUP" = "14" ]; then
    printf "§%-3d | %-52s | %-5d | %-5d | %-5d\n" 14 "Tham số (in, ref, out)" ${GP_PASS[14]} ${GP_FAIL[14]} $((GP_PASS[14] + GP_FAIL[14]))
fi
if [ "$MODE" != "single" ] || [ "$TARGET_GROUP" = "15" ]; then
    printf "§%-3d | %-52s | %-5d | %-5d | %-5d\n" 15 "FFI & Tương tác Hệ điều hành (@bind, syscall, OS)" ${GP_PASS[15]} ${GP_FAIL[15]} $((GP_PASS[15] + GP_FAIL[15]))
fi
if [ "$MODE" != "single" ] || [ "$TARGET_GROUP" = "16" ]; then
    printf "§%-3d | %-52s | %-5d | %-5d | %-5d\n" 16 "Register & Mold (Bit structures, pack)" ${GP_PASS[16]} ${GP_FAIL[16]} $((GP_PASS[16] + GP_FAIL[16]))
fi
if [ "$MODE" != "single" ] || [ "$TARGET_GROUP" = "17" ]; then
    printf "§%-3d | %-52s | %-5d | %-5d | %-5d\n" 17 "Thực thi lúc biên dịch (precomp, const fold)" ${GP_PASS[17]} ${GP_FAIL[17]} $((GP_PASS[17] + GP_FAIL[17]))
fi
if [ "$MODE" != "single" ] || [ "$TARGET_GROUP" = "18" ]; then
    printf "§%-3d | %-52s | %-5d | %-5d | %-5d\n" 18 "Điểm nhập (@entry, main, CLI args)" ${GP_PASS[18]} ${GP_FAIL[18]} $((GP_PASS[18] + GP_FAIL[18]))
fi
if [ "$MODE" != "single" ] || [ "$TARGET_GROUP" = "19" ]; then
    printf "§%-3d | %-52s | %-5d | %-5d | %-5d\n" 19 "Mảng (Arrays, Indexing, Slices)" ${GP_PASS[19]} ${GP_FAIL[19]} $((GP_PASS[19] + GP_FAIL[19]))
fi
if [ "$MODE" != "single" ] || [ "$TARGET_GROUP" = "20" ]; then
    printf "§%-3d | %-52s | %-5d | %-5d | %-5d\n" 20 "Dict & Map (Key-value collections)" ${GP_PASS[20]} ${GP_FAIL[20]} $((GP_PASS[20] + GP_FAIL[20]))
fi
if [ "$MODE" != "single" ] || [ "$TARGET_GROUP" = "21" ]; then
    printf "§%-3d | %-52s | %-5d | %-5d | %-5d\n" 21 "Biểu thức Case & Pattern Matching" ${GP_PASS[21]} ${GP_FAIL[21]} $((GP_PASS[21] + GP_FAIL[21]))
fi
if [ "$MODE" != "single" ] || [ "$TARGET_GROUP" = "22" ]; then
    printf "§%-3d | %-52s | %-5d | %-5d | %-5d\n" 22 "Async & Task (Concurrency)" ${GP_PASS[22]} ${GP_FAIL[22]} $((GP_PASS[22] + GP_FAIL[22]))
fi
if [ "$MODE" != "single" ] || [ "$TARGET_GROUP" = "23" ]; then
    printf "§%-3d | %-52s | %-5d | %-5d | %-5d\n" 23 "Port & Worker Channels (send, recv)" ${GP_PASS[23]} ${GP_FAIL[23]} $((GP_PASS[23] + GP_FAIL[23]))
fi
if [ "$MODE" != "single" ] || [ "$TARGET_GROUP" = "24" ]; then
    printf "§%-3d | %-52s | %-5d | %-5d | %-5d\n" 24 "GPU, SIMD & Atomic Primitives" ${GP_PASS[24]} ${GP_FAIL[24]} $((GP_PASS[24] + GP_FAIL[24]))
fi
if [ "$MODE" != "single" ] || [ "$TARGET_GROUP" = "25" ]; then
    printf "§%-3d | %-52s | %-5d | %-5d | %-5d\n" 25 "UI & Reactive Primitives" ${GP_PASS[25]} ${GP_FAIL[25]} $((GP_PASS[25] + GP_FAIL[25]))
fi
if [ "$MODE" != "single" ] || [ "$TARGET_GROUP" = "26" ]; then
    printf "§%-3d | %-52s | %-5d | %-5d | %-5d\n" 26 "AI & Học máy (Tensor, MatMul **, FMA, Infer, Trai..." ${GP_PASS[26]} ${GP_FAIL[26]} $((GP_PASS[26] + GP_FAIL[26]))
fi
if [ "$MODE" != "single" ] || [ "$TARGET_GROUP" = "27" ]; then
    printf "§%-3d | %-52s | %-5d | %-5d | %-5d\n" 27 "Intrinsics hệ thống (Memory read/write, low-level)" ${GP_PASS[27]} ${GP_FAIL[27]} $((GP_PASS[27] + GP_FAIL[27]))
fi
if [ "$MODE" != "single" ] || [ "$TARGET_GROUP" = "28" ]; then
    printf "§%-3d | %-52s | %-5d | %-5d | %-5d\n" 28 "Hỗ trợ đa ngôn ngữ (UTF-8, String encoding)" ${GP_PASS[28]} ${GP_FAIL[28]} $((GP_PASS[28] + GP_FAIL[28]))
fi
if [ "$MODE" != "single" ] || [ "$TARGET_GROUP" = "29" ]; then
    printf "§%-3d | %-52s | %-5d | %-5d | %-5d\n" 29 "Từ khoá tham chiếu & Diagnostic Tests" ${GP_PASS[29]} ${GP_FAIL[29]} $((GP_PASS[29] + GP_FAIL[29]))
fi
if [ "$MODE" != "single" ] || [ "$TARGET_GROUP" = "30" ]; then
    printf "§%-3d | %-52s | %-5d | %-5d | %-5d\n" 30 "Bảng ưu tiên toán tử (Operator Precedence)" ${GP_PASS[30]} ${GP_FAIL[30]} $((GP_PASS[30] + GP_FAIL[30]))
fi
if [ "$MODE" != "single" ] || [ "$TARGET_GROUP" = "31" ]; then
    printf "§%-3d | %-52s | %-5d | %-5d | %-5d\n" 31 "Thay đổi so với v1.2 (Strict v2.0 Conformance)" ${GP_PASS[31]} ${GP_FAIL[31]} $((GP_PASS[31] + GP_FAIL[31]))
fi
echo "-----+------------------------------------------------------+-------+-------+------"
printf "TỔNG | %-52s | %-5d | %-5d | %-5d\n" "Tất cả các nhóm kiểm thử" "$TOTAL_PASS" "$TOTAL_FAIL" "$((TOTAL_PASS + TOTAL_FAIL))"
echo "=========================================================================="

if [ "$TOTAL_FAIL" -gt 0 ]; then
    echo "KẾT QUẢ: THẤT BẠI ($TOTAL_FAIL lỗi phát hiện)"
    exit 1
else
    echo "KẾT QUẢ: THÀNH CÔNG (100% PASS)"
    exit 0
fi
