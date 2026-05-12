/*
 * constraints.h – Type System & Constraint Definitions
 * =====================================================
 * Defines the minimal type system that the Backend uses to know
 * data widths, alignment, and valid operations at machine-code level.
 *
 * Also defines the "contract" between Vir source tokens and Q-IR
 * opcodes so that the IR Lowering pass can type-check before emitting.
 */

#ifndef VIR_CONSTRAINTS_H
#define VIR_CONSTRAINTS_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ═══════════════════════════════════════════════════════
 * Data Types
 * ═══════════════════════════════════════════════════════
 * Machine-level type descriptors.  The Backend reads these
 * to decide operand width and register class.
 */

typedef enum {
    VIR_TYPE_VOID   = 0x00,  /* No value                      */
    VIR_TYPE_I8     = 0x01,  /* uint8_t  / bool               */
    VIR_TYPE_I32    = 0x02,  /* int32_t                       */
    VIR_TYPE_I64    = 0x03,  /* int64_t  (default integer)    */
    VIR_TYPE_F32    = 0x04,  /* float                         */
    VIR_TYPE_F64    = 0x05,  /* double   (default float)      */
    VIR_TYPE_PTR    = 0x06,  /* void * / string pointer       */
    VIR_TYPE_COUNT  = 7,
} vir_type_t;

/* Type metadata */
typedef struct {
    vir_type_t  type;
    const char *name;      /* "void", "i8", "i32", "i64", "f32", "f64", "ptr" */
    uint8_t     size;      /* Byte width                     */
    uint8_t     align;     /* Alignment requirement          */
    int         is_int;    /* 1 if integer class             */
    int         is_float;  /* 1 if floating-point class      */
} vir_type_info_t;

/* Get type descriptor */
const vir_type_info_t *vir_type_get(vir_type_t t);

/* Convenient size lookup */
uint8_t vir_type_size(vir_type_t t);

/* ═══════════════════════════════════════════════════════
 * Operation Constraints
 * ═══════════════════════════════════════════════════════
 * Each Q-IR opcode has constraints on operand types
 * and the result type it produces.
 */

typedef struct {
    uint8_t     opcode;          /* q_opcode_t                  */
    uint8_t     operand_count;   /* 0–3                         */
    vir_type_t  dest_type;       /* Result type                 */
    vir_type_t  src_types[3];    /* Operand types (VOID = unused) */
    const char *mnemonic;        /* Human-readable name         */
} op_constraint_t;

/* Get constraint for an opcode (NULL if unknown) */
const op_constraint_t *vir_op_constraint(uint8_t opcode);

/* Validate an instruction against constraints.
 * Returns 0 on success, -1 on type mismatch. */
int vir_constraint_check(uint8_t opcode, vir_type_t dest,
                         vir_type_t src1, vir_type_t src2);

/* ═══════════════════════════════════════════════════════
 * Value Representation
 * ═══════════════════════════════════════════════════════
 * Tagged union for typed runtime values.  Used by the VM
 * and by intrinsic callbacks.
 */

typedef struct {
    vir_type_t type;
    union {
        int64_t  i64;
        int32_t  i32;
        uint8_t  i8;
        double   f64;
        float    f32;
        void    *ptr;
    };
} vir_value_t;

/* Convenience constructors */
static inline vir_value_t vir_val_i64(int64_t v)
    { return (vir_value_t){ .type = VIR_TYPE_I64, .i64 = v }; }
static inline vir_value_t vir_val_i32(int32_t v)
    { return (vir_value_t){ .type = VIR_TYPE_I32, .i32 = v }; }
static inline vir_value_t vir_val_f64(double v)
    { return (vir_value_t){ .type = VIR_TYPE_F64, .f64 = v }; }
static inline vir_value_t vir_val_ptr(void *v)
    { return (vir_value_t){ .type = VIR_TYPE_PTR, .ptr = v }; }
static inline vir_value_t vir_val_void(void)
    { return (vir_value_t){ .type = VIR_TYPE_VOID, .i64 = 0 }; }

#ifdef __cplusplus
}
#endif

#endif /* VIR_CONSTRAINTS_H */
