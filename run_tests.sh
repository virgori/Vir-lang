#!/bin/bash
# Quick test runner for virc self-hosting compiler
cd "$(dirname "$0")"
VIRC="./core/build/vir run stdlib/vir/compiler/virc.vri"
PASS=0
FAIL=0
SKIP=0

run_test() {
    local test="$1"
    local expected="$2"
    
    # Compile (retry up to 2 times for VM flakiness)
    local compiled=0
    for attempt in 1 2; do
        output=$(perl -e 'alarm 25; exec @ARGV' -- $VIRC "$test" 2>&1)
        if [ $? -eq 0 ]; then
            compiled=1
            break
        fi
    done
    if [ $compiled -eq 0 ]; then
        echo "FAIL (compile): $test"
        FAIL=$((FAIL+1))
        return
    fi
    
    # Re-sign binary (virc's embedded LC_CODE_SIGNATURE can be stale)
    codesign -s - -f ./a.out 2>/dev/null

    # Run
    actual=$(perl -e 'alarm 5; exec @ARGV' -- ./a.out 2>&1)
    
    if [ "$actual" = "$expected" ]; then
        echo "PASS: $test"
        PASS=$((PASS+1))
    else
        echo "FAIL: $test"
        echo "  expected: $(echo "$expected" | tr '\n' ',')"
        echo "  actual:   $(echo "$actual" | tr '\n' ',')"
        FAIL=$((FAIL+1))
    fi
}

echo "=== virc Test Suite ==="
echo ""

run_test "test_hello.vri" "hello world"
run_test "test_arithmetic.vri" "$(printf '30\n90\n75\n15\n5')"
run_test "test_if_simple.vri" "42"
run_test "test_if_false.vri" "0"
run_test "test_if_else.vri" "1"
run_test "test_reassign.vri" "6"
run_test "test_while.vri" "$(printf '0\n1\n2\n3\n4')"
run_test "test_nested_if.vri" "2"
run_test "test_for_range.vri" "$(printf '0\n1\n2\n3\n4')"
run_test "test_break.vri" "$(printf '0\n1\n2\n3\n4\n99')"
run_test "test_skip.vri" "$(printf '1\n3\n5\n7\n9')"
run_test "test_loop_n.vri" "$(printf '7\n7\n7\n7\n7')"
run_test "test_eif.vri" "2"
run_test "test_for_accum.vri" "$(printf '103\n15')"
run_test "test_func_call.vri" "10"
run_test "test_multi_func.vri" "25"
run_test "test_nested_while.vri" "$(printf '0\n1\n2\n10\n11\n12\n20\n21\n22')"
run_test "test_recursion.vri" "$(printf '120\n3628800')"
run_test "test_fib.vri" "$(printf '0\n1\n5\n55')"
run_test "test_mutual_recursion.vri" "$(printf '1\n1\n0\n0')"
run_test "test_str_var.vri" "hello"
run_test "test_str_concat.vri" "hello world"
run_test "test_str_multi.vri" "$(printf 'Vir kills C!\n12\n4')"
run_test "test_str_func.vri" "$(printf 'Hello, Vir!\n11')"
run_test "test_str_loop.vri" "$(printf 'xxxxxx\n6')"
run_test "test_control.vri" "1"
run_test "test_array_basic.vri" "$(printf '10\n20\n30\n3')"
run_test "test_array_set.vri" "$(printf '100\n999\n300')"
run_test "test_array_loop.vri" "$(printf '10\n0\n9\n81\n285')"
run_test "test_array_literal.vri" "$(printf '10\n30\n50\n5')"
run_test "test_entity_full.vri" "$(printf '10\n20\n99\n20')"
run_test "test_entity_advanced.vri" "$(printf '3\n7\n10\n5\n50\n10')"
run_test "test_entity_rect.vri" "$(printf '10\n5\n0')"
run_test "test_entity_multi.vri" "$(printf '3\n7\n10\n5')"
run_test "test_enum_paren.vri" "$(printf '14\n3')"
run_test "test_arr_after_var.vri" "$(printf '2\n42\n99')"
run_test "test_dot_simple.vri" "110"
run_test "test_dot_entity.vri" "110"
run_test "test_dot_entity2.vri" "110"
run_test "test_entity_enum_array.vri" "$(printf '3\n4\n10\n20\n13\n110\n255\n128\n0\n64\n2\n3\n3\n110')"
run_test "test_global.vri" "$(printf '100\n42\n110\n200\n242')"
run_test "test_global2.vri" "$(printf '30\n45\n59\n2')"

# New tests added this session
run_test "test_eif_func.vri" "$(printf '100\n25\n30')"
run_test "test_if_dot.vri" "$(printf '110\n220\n30')"
run_test "test_virc_all.vri" "$(printf '15\n25\n12\n32\n100\n200\n2\nhello\n5')"

# Entity paren syntax, ensure without colon, methods, UFCS
run_test "test_entity_paren.vri" "$(printf '10\n20\n99')"
run_test "test_ensure.vri" "$(printf '42\n99')"
run_test "test_method.vri" "$(printf '11\n16\n16')"
run_test "test_ufcs.vri" "$(printf '20\n15\n37')"

# Stack spilling test (vreg >= 18)
run_test "test_spill.vri" "210"
run_test "test_hof.vri" "10
14"

# Phase 7: New intrinsic tests
run_test "test_intrinsics.vri" "$(printf '59\n2\n3\n-43\n42')"
run_test "test_syscall.vri" "$(printf 'OK')"

echo ""
echo "=== Advanced Test Suite (100 tests) ==="
echo ""

# Group 1: Opcode Correctness — Edge Cases (tests 001-010)
run_test "test_adv_001_i64_max.vri" "$(printf '9223372036854775806\n1\n-9223372036854775807')"
run_test "test_adv_002_overflow.vri" "-9223372036854775808"
run_test "test_adv_003_divzero.vri" "0"
run_test "test_adv_004_bitwise.vri" "$(printf '8\n14\n6\n0\n255')"
run_test "test_adv_005_shift.vri" "$(printf '42\n1\n0\n8\n2')"
run_test "test_adv_006_mod_neg.vri" "$(printf '2\n-1')"
run_test "test_adv_007_bitops_edge.vri" "$(printf '64\n0\n64\n0\n1\n64')"
run_test "test_adv_008_neg_not.vri" "$(printf '42\n42\n0\n-1')"
run_test "test_adv_009_bool_chain.vri" "$(printf '1\n0\n1\n1')"
run_test "test_adv_010_precedence.vri" "$(printf '14\n3\n23')"

# Group 2: Memory & Pointers (tests 011-020)
run_test "test_adv_011_mem_offsets.vri" "$(printf '100\n200\n300')"
run_test "test_adv_012_byte_rw.vri" "$(printf '65\n66\n67\n68')"
run_test "test_adv_013_deep_recursion.vri" "1000"
run_test "test_adv_014_many_params.vri" "136"
run_test "test_adv_015_large_alloc.vri" "$(printf '12345\n99999')"
run_test "test_adv_016_memset.vri" "$(printf '170\n170\n170\n170')"
run_test "test_adv_017_struct_fields.vri" "$(printf '1\n2\n3\n4')"
run_test "test_adv_018_global_local.vri" "$(printf '100\n42\n100')"
run_test "test_adv_019_heap_frag.vri" "100"
run_test "test_adv_020_memcopy.vri" "$(printf '10\n20\n30\n40')"

# Group 3: Control Flow (tests 021-025)
run_test "test_adv_021_nested5.vri" "32"
run_test "test_adv_022_switch_case.vri" "50"
run_test "test_adv_023_tailcall.vri" "0"
run_test "test_adv_024_branch_stress.vri" "500"
run_test "test_adv_025_nested_break.vri" "6"

# Group 4: Optimization Verification (tests 026-030)
run_test "test_adv_026_const_fold.vri" "$(printf '7\n42\n100')"
run_test "test_adv_027_dead_code.vri" "1"
run_test "test_adv_028_strength_reduce.vri" "$(printf '16\n64\n256\n1024')"
run_test "test_adv_029_algebra.vri" "$(printf '42\n42\n0\n42')"
run_test "test_adv_030_fma.vri" "$(printf '11\n14\n23')"

# Group 5: System & Real-world (tests 031-040)
run_test "test_adv_031_raw_write.vri" "$(printf 'HELLO')"
run_test "test_adv_032_bubblesort.vri" "$(printf '1\n2\n3\n4\n5')"
run_test "test_adv_033_matmul.vri" "$(printf '30\n36\n42\n66\n81\n96\n102\n126\n150')"
run_test "test_adv_034_strcat_chain.vri" "$(printf 'abc\n3')"
run_test "test_adv_035_quicksort.vri" "$(printf '1\n2\n3\n4\n5\n6\n7\n8')"
run_test "test_adv_036_strlen.vri" "$(printf '11\n3\n0')"
run_test "test_adv_037_itoa.vri" "$(printf '12345\n0\n5')"
run_test "test_adv_038_hex.vri" "$(printf '255\n3735928559\n170')"
run_test "test_adv_039_streq.vri" "$(printf '1\n0\n1')"
run_test "test_adv_040_str_get.vri" "$(printf '104\n101\n108')"

# Group 6: Advanced Pointers & Data Structures (tests 041-055)
run_test "test_adv_041_nested_entity.vri" "$(printf '10\n20\n30')"
run_test "test_adv_042_arr_entity.vri" "$(printf '10\n20\n30\n60')"
run_test "test_adv_043_entity_return.vri" "$(printf '5\n10\n15')"
run_test "test_adv_044_entity_param.vri" "$(printf '3\n7\n10')"
run_test "test_adv_045_big_entity.vri" "$(printf '1\n2\n3\n4\n5\n6\n21')"
run_test "test_adv_046_entity_mutate.vri" "$(printf '1\n99\n99')"
run_test "test_adv_047_enum_control.vri" "$(printf 'red\ngreen\nblue')"
run_test "test_adv_048_linked_list.vri" "$(printf '30\n20\n10')"
run_test "test_adv_049_arr_init.vri" "$(printf '0\n1\n4\n9\n16')"
run_test "test_adv_050_aliasing.vri" "$(printf '42\n42\n99\n99')"
run_test "test_adv_051_bsearch.vri" "$(printf '4\n-1')"
run_test "test_adv_052_gcd.vri" "$(printf '6\n1\n12')"
run_test "test_adv_053_power.vri" "$(printf '1\n8\n1024\n1')"
run_test "test_adv_054_sieve.vri" "$(printf '2\n3\n5\n7\n11\n13\n17\n19\n23\n29\n31\n37\n41\n43\n47')"
run_test "test_adv_055_str_build.vri" "$(printf 'aaaaaaaaaa\n10')"

# Group 7: ABI & Calling Convention (tests 056-060)
run_test "test_adv_056_callee_save.vri" "$(printf '100\n200\n100\n200')"
run_test "test_adv_057_func_ptr_arr.vri" "$(printf '10\n30\n50')"
run_test "test_adv_058_multi_return.vri" "$(printf '5\n3')"
run_test "test_adv_059_shadowing.vri" "$(printf '10\n42\n10')"
run_test "test_adv_060_spill30.vri" "465"

# Group 8: Advanced Optimizations (tests 061-070)
run_test "test_adv_061_dead_store.vri" "10"
run_test "test_adv_062_inline.vri" "$(printf '7\n30')"
run_test "test_adv_063_const_prop.vri" "14"
run_test "test_adv_064_unused_arg.vri" "10"
run_test "test_adv_065_redundant_load.vri" "$(printf '42\n42')"
run_test "test_adv_066_unroll.vri" "10"
run_test "test_adv_067_bce.vri" "$(printf '0\n1\n4\n9\n16\n25\n36\n49\n64\n81')"
run_test "test_adv_068_accum_func.vri" "55"
run_test "test_adv_069_shift_chain.vri" "$(printf '1024\n5120')"
run_test "test_adv_070_bit_arith.vri" "$(printf '15\n240\n255')"

# Group 9: OS Interaction & Stress (tests 071-080)
run_test "test_adv_071_exit_code.vri" "done"
run_test "test_adv_072_mmap.vri" "1"
run_test "test_adv_073_deep_expr.vri" "100"
run_test "test_adv_074_minimal.vri" "0"
run_test "test_adv_075_perf_loop.vri" "50005000"
run_test "test_adv_076_fib_iter.vri" "832040"
run_test "test_adv_077_collatz.vri" "111"
run_test "test_adv_078_reverse.vri" "$(printf '5\n4\n3\n2\n1')"
run_test "test_adv_079_stack_calc.vri" "42"
run_test "test_adv_080_hash.vri" "99162322"

# Group 10: Complex Integration (tests 081-100)
run_test "test_adv_081_multi_enum.vri" "$(printf '1\n3\n10\n20')"
run_test "test_adv_082_eif_classify.vri" "$(printf 'small\nmedium\nlarge')"
run_test "test_adv_083_for_break.vri" "$(printf '0\n1\n2')"
run_test "test_adv_084_for_skip.vri" "$(printf '0\n2\n4\n6\n8')"
run_test "test_adv_085_nested_call.vri" "15"
run_test "test_adv_086_global_counter.vri" "$(printf '1\n3\n6')"
run_test "test_adv_087_isort.vri" "$(printf '1\n2\n3\n4\n5\n6')"
run_test "test_adv_088_hanoi.vri" "7"
run_test "test_adv_089_minmax.vri" "$(printf '1\n99')"
run_test "test_adv_090_deep_call.vri" "120"
run_test "test_adv_091_tree.vri" "$(printf '1\n2\n3\n4\n5\n6\n7')"
run_test "test_adv_092_compose.vri" "25"
run_test "test_adv_093_map.vri" "$(printf '1\n4\n9\n16\n25')"
run_test "test_adv_094_reduce.vri" "120"
run_test "test_adv_095_mutual_deep.vri" "1"
run_test "test_adv_096_digit_sum.vri" "15"
run_test "test_adv_097_bit_manip.vri" "$(printf '5\n4\n1\n7')"
run_test "test_adv_098_large_arr.vri" "499500"
run_test "test_adv_099_distance.vri" "25"
run_test "test_adv_100_stress.vri" "$(printf '55\n120\n42\nhello\n5\n3\n7\n285\n10')"

# Phase 8: New Language Features
run_test "test_interp.vri" "$(printf 'Hello World\nVir is great\nEscaped $dollar')"
run_test "test_ufcs.vri" "$(printf '20\n15\n37')"
run_test "test_throw.vri" "$(printf '5\n3')"
run_test "test_ensure.vri" "$(printf '42\n99')"
run_test "test_packed.vri" "$(printf '3\n4\n11')"
run_test "test_this.vri" "$(printf '21\n7\n10')"
run_test "test_bind.vri" "$(printf '7\n30\n99')"

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
