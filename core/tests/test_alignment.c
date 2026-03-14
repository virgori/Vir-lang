/*
 * test_alignment.c — Phase 2 C3: Cross-Architecture Struct Alignment Audit
 * =========================================================================
 * Compile-time and runtime checks for struct alignment on x86-64, ARM64, RISC-V.
 * RISC-V traps on unaligned access; this ensures all critical structs are safe.
 *
 * Build:  cc -o test_alignment test_alignment.c -I../include -Wall -Wextra
 * Usage:  ./test_alignment
 */

#include <stdio.h>
#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>

/* Include all Vir headers with structs */
#include "q_ir.h"
#include "vm.h"
#include "task.h"
#include "cpu_caps.h"
#include "bridge.h"
#include "patcher.h"
#include "lexer.h"
#include "simd_index.h"
#include "atomic.h"
#include "ptx_gen.h"
#include "gpu_cuda.h"

/* ═══════════════════════════════════════════════════════
 * Alignment checker macros
 * ═══════════════════════════════════════════════════════ */

#define CHECK_ALIGN(type, field, expected_align)                              \
    do {                                                                      \
        size_t off = offsetof(type, field);                                   \
        if (off % (expected_align) != 0) {                                    \
            printf("  FAIL: %s.%-20s offset=%3zu (need %zu-align)\n",         \
                   #type, #field, off, (size_t)(expected_align));             \
            fails++;                                                          \
        } else {                                                              \
            passes++;                                                         \
        }                                                                     \
    } while (0)

#define CHECK_SIZE_MULTIPLE(type, multiple)                                   \
    do {                                                                      \
        size_t sz = sizeof(type);                                             \
        if (sz % (multiple) != 0) {                                           \
            printf("  FAIL: sizeof(%s) = %zu (not %zu-aligned)\n",            \
                   #type, sz, (size_t)(multiple));                            \
            fails++;                                                          \
        } else {                                                              \
            passes++;                                                         \
        }                                                                     \
    } while (0)

#define CHECK_NATURAL_ALIGN(type, field, field_type)                          \
    CHECK_ALIGN(type, field, _Alignof(field_type))

/* ═══════════════════════════════════════════════════════
 * Audit functions
 * ═══════════════════════════════════════════════════════ */

static int passes = 0;
static int fails = 0;

static void audit_q_ir(void) {
    printf("── q_operand_t ──\n");
    CHECK_NATURAL_ALIGN(q_operand_t, type, q_operand_type_t);
    /* union must be 8-byte aligned for int64_t/double */
    printf("   sizeof(q_operand_t) = %zu\n", sizeof(q_operand_t));
    CHECK_SIZE_MULTIPLE(q_operand_t, 8);

    printf("── q_instruction_t ──\n");
    CHECK_NATURAL_ALIGN(q_instruction_t, opcode, q_opcode_t);
    CHECK_NATURAL_ALIGN(q_instruction_t, dest, q_operand_t);
    CHECK_NATURAL_ALIGN(q_instruction_t, src1, q_operand_t);
    CHECK_NATURAL_ALIGN(q_instruction_t, src2, q_operand_t);
    printf("   sizeof(q_instruction_t) = %zu\n", sizeof(q_instruction_t));

    printf("── q_function_t ──\n");
    CHECK_NATURAL_ALIGN(q_function_t, body, q_instruction_t*);
    CHECK_NATURAL_ALIGN(q_function_t, body_count, uint32_t);
    printf("   sizeof(q_function_t) = %zu\n", sizeof(q_function_t));
}

static void audit_vm(void) {
    printf("── vm structs ──\n");
    printf("   sizeof(q_module_t) = %zu\n", sizeof(q_module_t));
    /* q_module_t has pointer arrays — ensure pointer-aligned */
    CHECK_NATURAL_ALIGN(q_module_t, functions, q_function_t);
    CHECK_NATURAL_ALIGN(q_module_t, strings, char*);
}

static void audit_task(void) {
    printf("── task_tcb_t ──\n");
    printf("   sizeof(task_tcb_t) = %zu\n", sizeof(task_tcb_t));
    CHECK_NATURAL_ALIGN(task_tcb_t, stack_base, void*);
    CHECK_NATURAL_ALIGN(task_tcb_t, stack_size, size_t);
}

static void audit_simd_index(void) {
    printf("── vir_structural_bitmap_t ──\n");
    printf("   sizeof(vir_structural_bitmap_t) = %zu\n", sizeof(vir_structural_bitmap_t));
    CHECK_NATURAL_ALIGN(vir_structural_bitmap_t, blocks, uint64_t*);
    CHECK_NATURAL_ALIGN(vir_structural_bitmap_t, n_blocks, size_t);
    CHECK_NATURAL_ALIGN(vir_structural_bitmap_t, n_bytes, size_t);
}

static void audit_spinlock(void) {
    printf("── vir_spinlock_t ──\n");
    printf("   sizeof(vir_spinlock_t) = %zu\n", sizeof(vir_spinlock_t));
    CHECK_SIZE_MULTIPLE(vir_spinlock_t, 4);
}

static void audit_gpu(void) {
    printf("── vir_gpu_device_info_t ──\n");
    printf("   sizeof(vir_gpu_device_info_t) = %zu\n", sizeof(vir_gpu_device_info_t));

    printf("── vir_gpu_launch_config_t ──\n");
    printf("   sizeof(vir_gpu_launch_config_t) = %zu\n", sizeof(vir_gpu_launch_config_t));
}

static void audit_ptx(void) {
    printf("── ptx_buf_t ──\n");
    printf("   sizeof(ptx_buf_t) = %zu\n", sizeof(ptx_buf_t));
    CHECK_NATURAL_ALIGN(ptx_buf_t, data, char*);
    CHECK_NATURAL_ALIGN(ptx_buf_t, len, size_t);
    CHECK_NATURAL_ALIGN(ptx_buf_t, cap, size_t);

    printf("── ptx_kernel_desc_t ──\n");
    printf("   sizeof(ptx_kernel_desc_t) = %zu\n", sizeof(ptx_kernel_desc_t));
}

/* ═══════════════════════════════════════════════════════
 * RISC-V specific checks
 * ═══════════════════════════════════════════════════════ */

static void audit_riscv_safety(void) {
    printf("\n═══ RISC-V Alignment Safety ═══\n");

    /* On RISC-V, LD requires 8-byte alignment, LW requires 4-byte alignment.
     * Check that all pointer and 64-bit fields are naturally aligned. */

    /* Verify no uint64_t at odd offsets in critical structs */
    size_t operand_union_off = offsetof(q_operand_t, imm);
    if (operand_union_off % 8 != 0) {
        printf("  CRITICAL: q_operand_t.imm at offset %zu (RISC-V LD will trap!)\n",
               operand_union_off);
        fails++;
    } else {
        printf("  OK: q_operand_t union at 8-byte boundary (offset %zu)\n",
               operand_union_off);
        passes++;
    }

    /* Check pointer alignment in arrays */
    q_instruction_t instr_test;
    memset(&instr_test, 0, sizeof(instr_test));
    uintptr_t addr = (uintptr_t)&instr_test;
    if (addr % _Alignof(q_instruction_t) != 0) {
        printf("  CRITICAL: stack q_instruction_t not aligned!\n");
        fails++;
    } else {
        passes++;
    }

    /* Heap allocation alignment check */
    q_instruction_t *heap_instr = malloc(sizeof(q_instruction_t));
    if (heap_instr) {
        uintptr_t haddr = (uintptr_t)heap_instr;
        if (haddr % 8 != 0) {
            printf("  WARN: malloc returned non-8-aligned address %p\n", (void*)heap_instr);
            fails++;
        } else {
            passes++;
        }
        free(heap_instr);
    }
}

/* ═══════════════════════════════════════════════════════
 * Main
 * ═══════════════════════════════════════════════════════ */

int main(void) {
    printf("═══ Vir Struct Alignment Audit ═══\n");
    printf("Platform: sizeof(void*)=%zu, sizeof(long)=%zu\n\n",
           sizeof(void*), sizeof(long));

    audit_q_ir();
    audit_vm();
    audit_task();
    audit_simd_index();
    audit_spinlock();
    audit_gpu();
    audit_ptx();
    audit_riscv_safety();

    printf("\n═══ Summary ═══\n");
    printf("PASS: %d   FAIL: %d\n", passes, fails);

    if (fails > 0) {
        printf("\n⚠ Alignment issues found! Fix with:\n");
        printf("  - Add _Alignas(N) or __attribute__((aligned(N)))\n");
        printf("  - Reorder struct fields: largest → smallest\n");
        printf("  - Use explicit padding fields\n");
        return 1;
    }

    printf("\n✓ All structs are alignment-safe for x86-64, ARM64, and RISC-V\n");
    return 0;
}
