/*
 * q_ir.h – Q-IR Instruction Set & Virtual Registers
 * ===================================================
 * Spec §2 – Tầng Máy trừu tượng (The Virtual Machine – Q-IR)
 *
 * SSA-form intermediate representation.
 * Unlimited virtual registers R0, R1, …, Rn
 */

#ifndef VIR_Q_IR_H
#define VIR_Q_IR_H

#include <stdint.h>
#include <stddef.h>
#include "vir_platform.h"

#ifdef __cplusplus
extern "C" {
#endif

/* ═══════════════════════════════════════════════════════
 * §2.1 Opcodes
 * ═══════════════════════════════════════════════════════ */
typedef enum {
    /* Data movement */
    Q_NOP           = 0x00,
    Q_LOAD          = 0x01,   /* Q_LOAD  dest, src|imm       */
    Q_STORE         = 0x02,   /* Q_STORE addr, src            */
    Q_MOVE          = 0x03,   /* Q_MOVE  dest, src            */

    /* Arithmetic */
    Q_ADD           = 0x10,   /* Q_ADD   dest, src1, src2     */
    Q_SUB           = 0x11,
    Q_MUL           = 0x12,
    Q_DIV           = 0x13,
    Q_MOD           = 0x14,

    /* Comparison (result: 0 or 1) */
    Q_CMP_EQ        = 0x20,
    Q_CMP_GT        = 0x21,
    Q_CMP_LT        = 0x22,
    Q_CMP_GE        = 0x23,
    Q_CMP_LE        = 0x24,

    /* Bitwise */
    Q_AND           = 0x30,
    Q_OR            = 0x31,
    Q_XOR           = 0x32,
    Q_SHL           = 0x33,
    Q_SHR           = 0x34,

    /* Control flow */
    Q_JUMP          = 0x40,   /* Unconditional jump           */
    Q_JUMP_IF       = 0x41,   /* Jump if cond != 0            */
    Q_JUMP_IF_NOT   = 0x42,   /* Jump if cond == 0            */
    Q_CALL          = 0x43,   /* Function call                */
    Q_RET           = 0x44,   /* Return                       */

    /* I/O */
    Q_PRINT         = 0x50,
    Q_INPUT         = 0x51,

    /* Memory management */
    Q_ALLOC         = 0x60,   /* dest = alloc(src1 bytes)      */
    Q_FREE          = 0x61,   /* free(src1)                    */
    Q_LOAD_BYTE     = 0x62,   /* dest = *(u8*)(src1 + src2)    */
    Q_STORE_BYTE    = 0x63,   /* *(u8*)(src1+src2) = dest      */
    Q_LOAD_WORD     = 0x64,   /* dest = *(i64*)(src1+src2*8)   */
    Q_STORE_WORD    = 0x65,   /* *(i64*)(src1+src2*8) = dest   */

    /* String operations */
    Q_STR_LEN       = 0x70,   /* dest = strlen(src1)           */
    Q_STR_GET       = 0x71,   /* dest = str[src2] (byte)       */
    Q_STR_CAT       = 0x72,   /* dest = concat(src1, src2)     */
    Q_STR_EQ        = 0x73,   /* dest = strcmp(src1,src2)==0    */

    /* File I/O */
    Q_FILE_OPEN     = 0x80,   /* dest = fopen(src1, src2)      */
    Q_FILE_READ     = 0x81,   /* dest = read_all(src1)         */
    Q_FILE_WRITE    = 0x82,   /* write(src1_fd, src2_data)     */
    Q_FILE_CLOSE    = 0x83,   /* fclose(src1)                  */
    Q_FILE_WRITE_BYTE = 0x84, /* write_byte(src1_fd, src2)     */

    /* Array operations */
    Q_ARR_NEW       = 0x90,   /* dest = new_array(src1=cap)    */
    Q_ARR_LEN       = 0x91,   /* dest = array_len(src1)        */
    Q_ARR_GET       = 0x92,   /* dest = arr[src2]              */
    Q_ARR_SET       = 0x93,   /* arr[src1][src2] = dest        */
    Q_ARR_PUSH      = 0x94,   /* arr_push(src1, src2)          */

    /* System */
    Q_EXIT          = 0xA0,   /* exit(src1)                    */
    Q_I_TO_STR      = 0xA1,   /* dest = itoa(src1)             */
    Q_STR_TO_I      = 0xA2,   /* dest = atoi(src1)             */
    Q_PRINT_STR     = 0xA3,   /* print string src1 to stdout   */
    Q_GET_ARG       = 0xA4,   /* dest = argv[src1]             */
    Q_ARG_COUNT     = 0xA5,   /* dest = argc                   */
    Q_CALL_FUNC     = 0xA6,   /* call function by index        */
    Q_LOAD_GLOBAL   = 0xA7,   /* dest = globals[src1]          */
    Q_STORE_GLOBAL  = 0xA8,   /* globals[src1] = src2          */

    /* §24.4 Atomic global accesses (seq_cst).
     * Backed by vir_atomic_{load,store,add}_i64 primitives. */
    Q_ATOMIC_LOAD_GLOBAL  = 0xA9, /* dest = atomic_load(globals[src1])  */
    Q_ATOMIC_STORE_GLOBAL = 0xAA, /* atomic_store(globals[src1], src2)  */
    Q_ATOMIC_ADD_GLOBAL   = 0xAB, /* dest = atomic_fetch_add(globals[src1], src2) */
    Q_ATOMIC_SUB_GLOBAL   = 0xAC, /* dest = atomic_fetch_sub(globals[src1], src2) */

    /* §26.2 / §24.2 Tensor + swizzle (runtime dispatch on array handle).
     * If operands are array handles → element-wise over arrays.
     * Otherwise → scalar fallback (Q_MUL). */
    Q_TENSOR_MUL    = 0xAD,   /* dest = src1 ** src2  (a*b elementwise) */
    Q_TENSOR_FMA    = 0xAE,   /* dest = src1 >< src2  (a*b elementwise) */
    Q_SWIZZLE       = 0xAF,   /* dest = swizzle(src1, channels=src2)    */

    /* SIMD / Vector operations (128-bit NEON / AVX) */
    Q_VLOAD         = 0xB0,   /* dest = vec_load(src1)         */
    Q_VSTORE        = 0xB1,   /* vec_store(dest, src1)         */
    Q_VADD          = 0xB2,   /* dest = vec_add(src1, src2)    */
    Q_VSUB          = 0xB3,   /* dest = vec_sub(src1, src2)    */
    Q_VMUL          = 0xB4,   /* dest = vec_mul(src1, src2)    */
    Q_VFMA          = 0xB5,   /* dest += vec_mul(src1, src2)   */
    Q_VDIV          = 0xB6,   /* dest = vec_div(src1, src2)    */
    Q_VMIN          = 0xB7,   /* dest = vec_min(src1, src2)    */
    Q_VMAX          = 0xB8,   /* dest = vec_max(src1, src2)    */
    Q_VREDUCE       = 0xB9,   /* dest = horizontal_sum(src1)   */
    Q_VSPLAT        = 0xBA,   /* dest = broadcast(src1)        */
    Q_VPERM         = 0xBB,   /* dest = permute(src1, src2)    */

    /* Self-patching  (Spec §2.1 – Q_PATCH_POINT) */
    Q_PATCH_POINT   = 0xF0,   /* "Lỗ hổng" cho Backend vá mã */

    /* Task / Green Thread (A2) */
    Q_TASK_SPAWN    = 0xF1,   /* dest = task_spawn(src1=fn_idx) */
    Q_TASK_YIELD    = 0xF2,   /* yield_now()                    */
    Q_TASK_WAIT     = 0xF3,   /* task_wait(src1=task_id)        */

    /* §11.4 Callable field: call function whose index is held in src1 (vreg).
     * Args are already in R0..R(argc-1) just like Q_CALL_FUNC. */
    Q_CALL_INDIRECT = 0xF4,   /* call_indirect(src1=vreg_holding_fidx) */

    /* Pseudo */
    Q_LABEL         = 0xFE,
    Q_HALT          = 0xFF
} q_opcode_t;

/* ═══════════════════════════════════════════════════════
 * §2.2 Operand Types
 * ═══════════════════════════════════════════════════════ */
typedef enum {
    OPERAND_NONE    = 0,
    OPERAND_VREG    = 1,  /* Virtual register Rn           */
    OPERAND_IMM     = 2,  /* Immediate value               */
    OPERAND_LABEL   = 3,  /* Label (jump target)           */
    OPERAND_ADDR    = 4,  /* Memory address                */
    OPERAND_STR     = 5,  /* String table index            */
    OPERAND_FUNC_IDX= 6   /* Function table index          */
} q_operand_type_t;

typedef struct {
    q_operand_type_t type;
    union {
        uint32_t    vreg;   /* Virtual register index       */
        int64_t     imm;    /* Immediate (integer)          */
        double      fimm;   /* Immediate (float)            */
        uint32_t    label;  /* Label ID                     */
        uint64_t    addr;   /* Memory address               */
        uint32_t    str_idx;/* String table index           */
        uint32_t    func_idx;/* Function index              */
    };
} q_operand_t;

/* ═══════════════════════════════════════════════════════
 * Instruction
 * ═══════════════════════════════════════════════════════ */
typedef struct {
    q_opcode_t   opcode;
    q_operand_t  dest;
    q_operand_t  src1;
    q_operand_t  src2;
    uint32_t     patch_id;  /* Nonzero for Q_PATCH_POINT    */
    uint32_t     line;      /* Source line (debug info)      */
} q_instruction_t;

/* ═══════════════════════════════════════════════════════
 * Function & Module
 * ═══════════════════════════════════════════════════════ */
#define Q_MAX_FUNC_NAME  64
#define Q_MAX_PARAMS     16

typedef struct {
    char             name[Q_MAX_FUNC_NAME];
    uint32_t         param_count;
    uint32_t         param_vregs[Q_MAX_PARAMS];
    q_instruction_t *body;
    uint32_t         body_count;
    uint32_t         body_capacity;
} q_function_t;

#define Q_MAX_FUNCTIONS  256
#define Q_MAX_STRINGS    8192

typedef struct {
    char             name[Q_MAX_FUNC_NAME];
    q_function_t     functions[Q_MAX_FUNCTIONS];
    uint32_t         func_count;
    /* String constant table */
    char            *strings[Q_MAX_STRINGS];
    uint32_t         string_count;
} q_module_t;

/* ═══════════════════════════════════════════════════════
 * §2.2 Virtual Register Allocator
 * ═══════════════════════════════════════════════════════ */
#define VREG_MAX  65536

typedef struct {
    uint32_t next_index;
} q_vreg_alloc_t;

/* ── API ─────────────────────────────────────────────── */

/* Operand constructors */
q_operand_t q_vreg(uint32_t index);
q_operand_t q_imm(int64_t value);
q_operand_t q_fimm(double value);
q_operand_t q_label(uint32_t id);
q_operand_t q_none(void);
q_operand_t q_str(uint32_t str_idx);
q_operand_t q_func_idx(uint32_t func_idx);

/* Instruction constructor */
q_instruction_t q_instr(q_opcode_t op, q_operand_t dest,
                        q_operand_t src1, q_operand_t src2);

/* Function */
int  q_func_init(q_function_t *func, const char *name);
int  q_func_emit(q_function_t *func, q_instruction_t instr);
void q_func_free(q_function_t *func);

/* Module */
int  q_module_init(q_module_t *mod, const char *name);
q_function_t* q_module_add_func(q_module_t *mod, const char *name);
void q_module_free(q_module_t *mod);
void q_module_dump(const q_module_t *mod, char *buf, size_t buf_size);
uint32_t q_module_add_string(q_module_t *mod, const char *str);

/* Register allocator */
void     q_vreg_alloc_init(q_vreg_alloc_t *alloc);
uint32_t q_vreg_alloc_next(q_vreg_alloc_t *alloc);
void     q_vreg_alloc_reset(q_vreg_alloc_t *alloc);

/* Opcode name */
const char* q_opcode_name(q_opcode_t op);

#ifdef __cplusplus
}
#endif

#endif /* VIR_Q_IR_H */
