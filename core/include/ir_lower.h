/*
 * ir_lower.h – AST → Q-IR Lowering + Register Allocation
 * ========================================================
 * Converts a high-level AST (as produced by the Parser) into
 * a well-formed Q-IR module with proper register allocation.
 *
 * The lowering pass performs:
 *   1. Recursive AST traversal → Q-IR instruction emission
 *   2. Linear-scan register allocation over virtual registers
 *   3. Spill-slot assignment when physical registers are exhausted
 *   4. Intrinsic call injection for PRINT / INPUT / CHECK_CPU
 *
 * All in C – no Python dependency.
 */

#ifndef VIR_IR_LOWER_H
#define VIR_IR_LOWER_H

#include "q_ir.h"
#include "constraints.h"
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ═══════════════════════════════════════════════════════
 * AST Node Types (mirrors the Python parser)
 * ═══════════════════════════════════════════════════════
 * Compact C representation of the parse tree.
 */

typedef enum {
    AST_PROGRAM,
    AST_FUNC_DEF,
    AST_VAR_DECL,
    AST_CONST_DECL,
    AST_IF,
    AST_LOOP,
    AST_WHILE,
    AST_RETURN,
    AST_PRINT,
    AST_INPUT,
    AST_BINOP,
    AST_COMPARE,
    AST_LITERAL_INT,
    AST_LITERAL_FLOAT,
    AST_LITERAL_STR,
    AST_IDENTIFIER,
    AST_CALL,
    AST_CHECK_CPU,
    AST_PATCH_POINT,
    AST_ASSIGN,
    AST_BLOCK,          /* list of statements */
    /* Phase 1-3 extensions */
    AST_ARRAY_LITERAL,  /* [expr, ...] */
    AST_INDEX_ACCESS,   /* arr[idx] */
    AST_INDEX_ASSIGN,   /* arr[idx] = val */
    AST_FOR_RANGE,      /* for i in 0..N */
    AST_BUILTIN_CALL,   /* built-in function call */
    AST_ENUM_DEF,       /* enum / liệt_kê definition */
    AST_ENUM_ACCESS,    /* Enum.VARIANT */
    AST_RECORD_DEF,     /* record / bản_ghi definition */
    AST_RECORD_LITERAL, /* RecordName { field: val, ... } */
    AST_FIELD_ACCESS,   /* expr.field */
    AST_FIELD_ASSIGN,   /* expr.field = val */
    /* Phase 4 prep */
    AST_BREAK,          /* break / thoát vòng */
    AST_CONTINUE,       /* continue / tiếp tục */
    AST_IMPORT,         /* import module */
    AST_MODULE,         /* module name */
    AST_EXPORT,         /* export func */
    AST_INCLUDE,        /* include "file" */
    /* ── v1.2 additions ──────────────────────────────── */
    AST_ENTITY_DEF,     /* entity Name: ... end */
    AST_METHOD_DEF,     /* method Entity.name: ... end */
    AST_CLASS_DEF,      /* class Name ... end */
    AST_HAS_DECL,       /* has funcName (forward decl) */
    AST_SHARE,          /* share state1, state2 */
    AST_OUT,            /* out expr (v1.2 return) */
    AST_SKIP,           /* skip (v1.2 continue) */
    AST_EIF,            /* eif (v1.2 else-if) */
    AST_WHEN_LOOP,      /* when cond loop ... end */
    AST_CASE,           /* case expr val: action; ... end */
    AST_MAP_LITERAL,    /* map key: val; ... end */
    AST_TRY_ERROR,      /* out expr try fallback error Name end */
    AST_TASK,           /* task name wait func */
    AST_ASYNC_FUNC,     /* async func ... end */
    AST_IN_PARAMS,      /* in(a:int; b:int) */
    AST_MODULE_STATE,   /* var block (module state) */
    AST_PATTERN_MATCH,  /* expr :~ pattern */
    AST_SAFE_ACCESS,    /* expr?.field */
    AST_CAST,           /* expr >> Type */
    AST_EXIST_CHECK,    /* expr? */
    AST_NAMED_ARG,      /* param=value in call */
    AST_TYPE_DECL,      /* type i8; (v1.2 type alias)  */
    AST_ATOMIC_LOAD,    /* lock expr / expr!! (read)    */
    AST_ATOMIC_STORE,   /* lock x = v / x!! = v         */
    AST_ATOMIC_RMW,     /* lock x += 1 / x!! += 1       */
    AST_SWIZZLE,        /* v~xyz / v~rgba (§24.2)       */
} ast_type_t;

/* Binary / comparison operators */
typedef enum {
    OP_ADD, OP_SUB, OP_MUL, OP_DIV, OP_MOD,
    OP_EQ, OP_NE, OP_GT, OP_LT, OP_GE, OP_LE,
    OP_AND, OP_OR, OP_XOR, OP_SHL, OP_SHR,
    /* v1.2 additions */
    OP_POW,             /* ^ power */
    OP_PERCENT,         /* % percent (not mod) */
    OP_SAFE_EQ,         /* ?= safe equal */
    OP_SAFE_NE,         /* ?=/= safe not-equal */
    OP_PATTERN,         /* :~ pattern match */
    OP_CAST,            /* >> type cast */
    OP_NOT,             /* ! logical not */
    /* §26.2 AI operators */
    OP_MATMUL,          /* ** matrix multiply */
    OP_FMA,             /* >< fused multiply-add */
} ast_op_t;

/* Built-in function IDs (for AST_BUILTIN_CALL) */
typedef enum {
    BUILTIN_LEN = 1,       /* dài(arr|str) → length */
    BUILTIN_PUSH,          /* đẩy(arr, val) → push */
    BUILTIN_ALLOC,         /* cấp(size) → address */
    BUILTIN_FREE_MEM,      /* giải(addr) → free */
    BUILTIN_READ8,         /* đọc_byte(addr, off) */
    BUILTIN_WRITE8,        /* ghi_byte(addr, off, val) */
    BUILTIN_READ64,        /* đọc_số(addr, off) */
    BUILTIN_WRITE64,       /* ghi_số(addr, off, val) */
    BUILTIN_STR_LEN,       /* dài_chuỗi(s) */
    BUILTIN_STR_GET,       /* ký_tự(s, idx) */
    BUILTIN_STR_CAT,       /* nối(s1, s2) */
    BUILTIN_STR_EQ,        /* bằng_chuỗi(s1, s2) */
    BUILTIN_FILE_OPEN,     /* mở_tệp(path, mode) */
    BUILTIN_FILE_READ,     /* đọc_tệp(fd) */
    BUILTIN_FILE_WRITE,    /* ghi_tệp(fd, data) */
    BUILTIN_FILE_CLOSE,    /* đóng_tệp(fd) */
    BUILTIN_FILE_WRITE_BYTE,/* ghi_byte_tệp(fd, byte) */
    BUILTIN_EXIT,          /* thoát(code) */
    BUILTIN_I_TO_STR,      /* số_sang_chuỗi(n) */
    BUILTIN_STR_TO_I,      /* chuỗi_sang_số(s) */
    BUILTIN_ARR_NEW,       /* mảng_mới(cap) */
    BUILTIN_PRINT_STR,     /* viết_chuỗi(s) */
    BUILTIN_GET_ARG,       /* lấy_arg(n) */
    BUILTIN_ARG_COUNT,     /* đếm_arg() */
} builtin_id_t;

/* Forward declaration */
typedef struct ast_node ast_node_t;

#define AST_MAX_CHILDREN 1024
#define AST_NAME_LEN     64

struct ast_node {
    ast_type_t  type;
    ast_op_t    op;              /* For BINOP / COMPARE          */
    int64_t     int_val;         /* For LITERAL_INT              */
    double      float_val;       /* For LITERAL_FLOAT            */
    char        name[AST_NAME_LEN]; /* FUNC_DEF name, IDENTIFIER, etc. */
    char        name2[AST_NAME_LEN]; /* Secondary name (e.g. field name for FIELD_ACCESS) */
    int         builtin_id;      /* For BUILTIN_CALL             */
    ast_node_t *children[AST_MAX_CHILDREN];
    uint32_t    child_count;
    uint32_t    line;            /* Source line number            */
};

/* Allocate a new AST node (caller must free with ast_free) */
ast_node_t *ast_new(ast_type_t type);

/* Add a child node */
int ast_add_child(ast_node_t *parent, ast_node_t *child);

/* Free an AST and all children recursively */
void ast_free(ast_node_t *node);

/* ═══════════════════════════════════════════════════════
 * Enum Table (for compile-time integer constants)
 * ═══════════════════════════════════════════════════════ */

#define ENUM_MAX_VARIANTS 64
#define ENUM_MAX_TYPES    32

typedef struct {
    char    name[AST_NAME_LEN];       /* variant name */
    int64_t value;                     /* integer value */
} enum_variant_t;

typedef struct {
    char            name[AST_NAME_LEN]; /* enum type name */
    enum_variant_t  variants[ENUM_MAX_VARIANTS];
    uint32_t        variant_count;
} enum_type_t;

/* ═══════════════════════════════════════════════════════
 * Record (Struct) Table
 * ═══════════════════════════════════════════════════════ */

#define RECORD_MAX_FIELDS 32
#define RECORD_MAX_TYPES  32

typedef struct {
    char     name[AST_NAME_LEN]; /* field name */
    uint32_t offset;              /* offset in units of int64 (0, 1, 2, ...) */
} record_field_t;

typedef struct {
    char            name[AST_NAME_LEN]; /* record type name */
    record_field_t  fields[RECORD_MAX_FIELDS];
    uint32_t        field_count;
} record_type_t;

/* ═══════════════════════════════════════════════════════
 * Symbol Table (for the lowering pass)
 * ═══════════════════════════════════════════════════════
 * Maps variable names → virtual register indices.
 */

#define SYM_MAX 512

typedef struct {
    char     name[AST_NAME_LEN];
    uint32_t vreg;
    vir_type_t type;
} symbol_entry_t;

typedef struct {
    symbol_entry_t entries[SYM_MAX];
    uint32_t       count;
} symbol_table_t;

void sym_init(symbol_table_t *st);
int  sym_define(symbol_table_t *st, const char *name,
                uint32_t vreg, vir_type_t type);
int  sym_lookup(const symbol_table_t *st, const char *name,
                uint32_t *vreg);

/* ═══════════════════════════════════════════════════════
 * Live Interval (for register allocation)
 * ═══════════════════════════════════════════════════════ */

typedef struct {
    uint32_t vreg;
    uint32_t start;    /* First instruction index that defines  */
    uint32_t end;      /* Last instruction index that uses      */
    int      phys_reg; /* Assigned physical register (-1=spill) */
    int      spill_slot; /* Stack offset if spilled             */
} live_interval_t;

#define LOWER_MAX_INTERVALS 4096

/* ═══════════════════════════════════════════════════════
 * Lowering Context
 * ═══════════════════════════════════════════════════════ */

typedef struct {
    q_module_t       module;
    q_vreg_alloc_t   vreg_alloc;
    symbol_table_t   symbols;
    symbol_table_t   global_symbols;  /* globals visible in all functions */
    uint32_t         global_index_counter;  /* next global slot index */
    uint32_t         label_counter;
    uint32_t         patch_counter;

    /* Enum + record type tables (compile-time) */
    enum_type_t      enum_types[ENUM_MAX_TYPES];
    uint32_t         enum_type_count;
    record_type_t    record_types[RECORD_MAX_TYPES];
    uint32_t         record_type_count;

    /* Loop label stack (for break/continue) */
#define LOOP_STACK_MAX 32
    uint32_t         loop_start_labels[LOOP_STACK_MAX]; /* continue targets */
    uint32_t         loop_end_labels[LOOP_STACK_MAX];   /* break targets */
    uint32_t         loop_depth;

    /* Module alias table (for import X as Y) */
#define MODULE_ALIAS_MAX 64
    struct {
        char original[AST_NAME_LEN];  /* module name */
        char alias[AST_NAME_LEN];     /* alias (or same as original) */
    } module_aliases[MODULE_ALIAS_MAX];
    uint32_t         module_alias_count;

    /* Imported symbol table (for from X import sym1, sym2) */
#define IMPORTED_SYM_MAX 128
    struct {
        char module[AST_NAME_LEN];
        char symbol[AST_NAME_LEN];
    } imported_syms[IMPORTED_SYM_MAX];
    uint32_t         imported_sym_count;

    /* Include file handler (set by driver to resolve file paths) */
    char            *(*include_reader)(const char *filename, size_t *out_len,
                                       void *user_data);
    void            *include_user_data;
    const char      *include_search_paths[16];
    uint32_t         include_search_path_count;

    /* Track included files to prevent double-include */
#define INCLUDE_MAX 64
    char             included_files[INCLUDE_MAX][256];
    uint32_t         included_file_count;

    /* Current function being lowered */
    q_function_t    *current_func;

    /* Live intervals for register allocation */
    live_interval_t  intervals[LOWER_MAX_INTERVALS];
    uint32_t         interval_count;

    /* Error tracking */
    int              error_count;
    char             last_error[256];
} lower_ctx_t;

/* ═══════════════════════════════════════════════════════
 * API
 * ═══════════════════════════════════════════════════════ */

/* Initialise lowering context */
void lower_init(lower_ctx_t *ctx, const char *module_name);

/* Lower an AST program → Q-IR module.
 * Returns 0 on success. */
int lower_program(lower_ctx_t *ctx, const ast_node_t *program);

/* Lower a single function definition */
int lower_func_def(lower_ctx_t *ctx, const ast_node_t *func_def);

/* Resolve include directives: load files & splice into AST.
 * Must be called before lower_program if includes are used.
 * Returns 0 on success. */
int lower_resolve_includes(lower_ctx_t *ctx, ast_node_t *program);

/* Process import/module/export metadata from the AST.
 * Populates module_aliases and imported_syms tables.
 * Called automatically by lower_program. */
int lower_process_imports(lower_ctx_t *ctx, const ast_node_t *program);

/* Check if AST node type is structural metadata (no runtime effect) */
int ast_is_metadata(ast_type_t type);

/* Lower an expression, returning the virtual register holding
 * the result (-1 on error). */
int lower_expr(lower_ctx_t *ctx, const ast_node_t *expr);

/* Lower a statement (emit instructions into current_func) */
int lower_stmt(lower_ctx_t *ctx, const ast_node_t *stmt);

/* ── Register Allocation ──────────────────────────────── */

/* Compute live intervals from a function's Q-IR body */
int lower_compute_liveness(lower_ctx_t *ctx, const q_function_t *func);

/* Linear-scan register allocation.
 * `num_phys_regs`: available physical registers (from ABI).
 * Populates `intervals[].phys_reg` or `.spill_slot`.
 * Returns 0 on success. */
int lower_regalloc_linear_scan(lower_ctx_t *ctx, uint32_t num_phys_regs);

/* Get the physical register assigned to a virtual register.
 * Returns -1 if spilled. */
int lower_get_phys_reg(const lower_ctx_t *ctx, uint32_t vreg);

/* ── Spill Code Insertion ──────────────────────────────── */

/* Insert STORE/LOAD instructions around spilled virtual registers.
 * Must be called after lower_regalloc_linear_scan().
 * Uses a dedicated temp register (spill_temp_reg) for loads.
 * Returns number of spill operations inserted, or -1 on error. */
int lower_insert_spill_code(lower_ctx_t *ctx, q_function_t *func,
                            uint32_t spill_temp_reg);

/* ── Tail-Call Optimization ────────────────────────────────── */

/* Post-lowering pass: scan function body for CALL followed
 * immediately by RET and replace with JUMP (tail call).
 * Returns the number of tail calls optimised. */
int lower_tco_pass(q_function_t *func);

/* ── Cleanup ──────────────────────────────────────────── */

/* Get the produced Q-IR module (ownership transfers to caller) */
q_module_t *lower_get_module(lower_ctx_t *ctx);

/* Free context internal data (not the module itself) */
void lower_destroy(lower_ctx_t *ctx);

#ifdef __cplusplus
}
#endif

#endif /* VIR_IR_LOWER_H */
