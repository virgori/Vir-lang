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

#include "constraints.h"
#include "q_ir.h"
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
  AST_BLOCK, /* list of statements */
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
  AST_BREAK,    /* break / thoát vòng */
  AST_CONTINUE, /* continue / tiếp tục */
  AST_IMPORT,   /* import module */
  AST_MODULE,   /* module name */
  AST_EXPORT,   /* export func */
  AST_INCLUDE,  /* include "file" */
  /* ── v1.2 additions ──────────────────────────────── */
  AST_ENTITY_DEF,    /* entity Name: ... end */
  AST_METHOD_DEF,    /* method Entity.name: ... end */
  AST_CLASS_DEF,     /* class Name ... end */
  AST_HAS_DECL,      /* has funcName (forward decl) */
  AST_SHARE,         /* share state1, state2 */
  AST_OUT,           /* out expr (v1.2 return) */
  AST_SKIP,          /* skip (v1.2 continue) */
  AST_EIF,           /* eif (v1.2 else-if) */
  AST_WHEN_LOOP,     /* when cond loop ... end */
  AST_INTERFACE_DEF, /* giao_diện Name ... end */
  AST_IMPLEMENT_STMT, /* thực_hiện Name for Type; */
  AST_CASE,          /* case expr val: action; ... end */
  AST_MAP_LITERAL,   /* map key: val; ... end */
  AST_TRY_ERROR,     /* out expr try fallback error Name end */
  AST_TASK,          /* task name wait func */
  AST_ASYNC_FUNC,    /* async func ... end */
  AST_IN_PARAMS,     /* in(a:int; b:int) */
  AST_MODULE_STATE,  /* var block (module state) */
  AST_PATTERN_MATCH, /* expr :~ pattern */
  AST_SAFE_ACCESS,   /* expr?.field */
  AST_CAST,          /* expr >> Type */
  AST_EXIST_CHECK,   /* expr? */
  AST_NAMED_ARG,     /* param=value in call */
  AST_TYPE_DECL,     /* type i8; (v1.2 type alias)  */
  AST_ATOMIC_LOAD,   /* lock expr / expr!! (read)    */
  AST_ATOMIC_STORE,  /* lock x = v / x!! = v         */
  AST_ATOMIC_RMW,    /* lock x += 1 / x!! += 1       */
  AST_SWIZZLE,       /* v~xyz / v~rgba (§24.2)       */
  /* §4.8 Ownership & Borrow (2.8–2.11) */
  AST_BORROW, /* &expr (shared) / &mut expr   */
  /* §13 Error handling (11.3–11.13) */
  AST_THROW,        /* throw <expr>                 */
  AST_ENSURE_BLOCK, /* ensure <body> (func-level)   */
  AST_REVERT_BLOCK, /* revert <body> (func-level)   */
  AST_TRY_BLOCK,    /* try(opts): body revert ... end
                     * children[0] = body block
                     * children[1] = revert block (may be NULL stub)
                     * name holds isolate-list comma-joined
                     * int_val bit 0 = has_timeout, bit 1 = has_isolate
                     * float_val (reused as int) = timeout seconds
                     */
  AST_RESUME,   /* resume retry | resume revert; int_val: 0=retry,1=revert */
  AST_EMIT,     /* emit LEVEL(args); name = LEVEL; children = args */
  AST_ERX_READ, /* erx (leaf, reads error register) */
  /* §16 Register / Mold (bit-level layouts) */
  AST_REGISTER_DEF, /* register NAME: TYPE ... end
                     * children[i] = field node (AST_IDENTIFIER)
                     *   .name = field name
                     *   .int_val = (width << 8) | lo_bit
                     */
  AST_MOLD_DEF,     /* mold NAME: TYPE f:w, f:w ... end — same shape
                     * as AST_REGISTER_DEF (lowering merges both into
                     * the bit_type table; distinguish only by kind).
                     */
  AST_DEL_STMT,     /* del m[key]   (§20)
                     * name = dict identifier
                     * children[0] = key expression
                     */
  AST_MAP_EXPR,     /* map x [,idx] in iter: body end (§20.2)
                     * name  = element var name
                     * name2 = optional second var (index or value)
                     * children[0] = iterable expr
                     * children[1..] = body statements (AST_OUT to emit)
                     */
  /* §25 UI/Reactive, §26 AI/ML annotations and blocks */
  AST_INFER_BLOCK,   /* infer: body end  — transparent wrapper (§26.3) */
  AST_TRAIN_BLOCK,   /* train: body end  — transparent wrapper (§26.4) */
  AST_ISOLATE_BLOCK, /* isolate: body end — sandbox block (§25.5) */
  AST_MORPH_DEF,     /* morph NAME -> UI: bindings end (§25.2). name=entity,
                      * name2=ui component; children = binding pairs (compile-time
                      * metadata; runtime no-op) */
  AST_BUNDLE_DECL,   /* bundle name: type = embed "path" (§25.3).
                      * name=var name, name2="string"/"u8[]"/etc.
                      * children[0] = AST_LITERAL_STR with raw bytes/text */
  /* §17 Precomp / Comptime */
  AST_PRECOMP, /* precomp { expr } / comptime { expr } — parse-time
                * folded int constant. int_val = folded value.
                * If unfoldable: children[0] = expr (runtime fallback). */
  /* §23 Port inter-worker channels */
  AST_PORT_DECL,    /* port NAME: TYPE [(cap: N)] — int_val = capacity,
                     * name = port name, name2 = element type */
  AST_SEND_STMT,    /* send NAME <- expr — name = port; children[0] = expr */
  AST_RECV_EXPR,    /* recv NAME — name = port (leaf) */
  AST_SELECT_BLOCK, /* select: case recv X from P: body ... end
                     * children = list of case nodes (AST_BLOCK whose
                     * name = bind var, name2 = port name, children = body) */
  /* §24.2 Swizzle write-mask: v~xy = rhs */
  AST_SWIZZLE_STORE, /* name = target var; name2 = channels;
                      * children[0] = rhs expr */
  /* §24.3 Shared buffer declaration */
  AST_DECK_DECL, /* deck NAME: TYPE[SIZE]
                  * name = buffer name; int_val = size */
  /* §22 Async async statements */
  AST_AWAIT_EXPR,  /* await EXPR — children[0] = task_id expr */
  AST_CANCEL_STMT, /* cancel EXPR — children[0] = task_id expr */
  AST_QUIET_STMT,  /* quiet EXPR — fire-and-forget; children[0] = expr */
  /* §14.1 Address-of (ref) — children[0] = target IDENT */
  AST_ADDR_OF,
  /* §4.5 Arena block — name holds bind id; children[0] = body block */
  AST_ARENA_BLOCK,
  AST_PACKED_DEF, /* packed entity (v2 experimental) */
  AST_TUPLE_LITERAL, /* (a, b, c) — tuple expression */
} ast_type_t;

/* Binary / comparison operators */
typedef enum {
  OP_ADD,
  OP_SUB,
  OP_MUL,
  OP_DIV,
  OP_MOD,
  OP_EQ,
  OP_NE,
  OP_GT,
  OP_LT,
  OP_GE,
  OP_LE,
  OP_AND,
  OP_OR,
  OP_XOR,
  OP_SHL,
  OP_SHR,
  /* v1.2 additions */
  OP_POW,     /* ^ power */
  OP_PERCENT, /* % percent (not mod) */
  OP_SAFE_EQ, /* ?= safe equal */
  OP_SAFE_NE, /* ?=/= safe not-equal */
  OP_PATTERN, /* :~ pattern match */
  OP_CAST,    /* >> type cast */
  OP_NOT,     /* ! logical not */
  /* §26.2 AI operators */
  OP_MATMUL, /* ** matrix multiply */
  OP_FMA,    /* >< fused multiply-add */
} ast_op_t;

/* Built-in function IDs (for AST_BUILTIN_CALL) */
typedef enum {
  BUILTIN_LEN = 1,         /* dài(arr|str) → length */
  BUILTIN_PUSH,            /* đẩy(arr, val) → push */
  BUILTIN_ALLOC,           /* cấp(size) → address */
  BUILTIN_FREE_MEM,        /* giải(addr) → free */
  BUILTIN_READ8,           /* đọc_byte(addr, off) */
  BUILTIN_WRITE8,          /* ghi_byte(addr, off, val) */
  BUILTIN_READ64,          /* đọc_số(addr, off) */
  BUILTIN_WRITE64,         /* ghi_số(addr, off, val) */
  BUILTIN_STR_LEN,         /* dài_chuỗi(s) */
  BUILTIN_STR_GET,         /* ký_tự(s, idx) */
  BUILTIN_STR_CAT,         /* nối(s1, s2) */
  BUILTIN_STR_EQ,          /* bằng_chuỗi(s1, s2) */
  BUILTIN_FILE_OPEN,       /* mở_tệp(path, mode) */
  BUILTIN_FILE_READ,       /* đọc_tệp(fd) */
  BUILTIN_FILE_WRITE,      /* ghi_tệp(fd, data) */
  BUILTIN_FILE_CLOSE,      /* đóng_tệp(fd) */
  BUILTIN_FILE_WRITE_BYTE, /* ghi_byte_tệp(fd, byte) */
  BUILTIN_EXIT,            /* thoát(code) */
  BUILTIN_I_TO_STR,        /* số_sang_chuỗi(n) */
  BUILTIN_STR_TO_I,        /* chuỗi_sang_số(s) */
  BUILTIN_ARR_NEW,         /* mảng_mới(cap) */
  BUILTIN_PRINT_STR,       /* viết_chuỗi(s) */
  BUILTIN_GET_ARG,         /* lấy_arg(n) */
  BUILTIN_ARG_COUNT,       /* đếm_arg() */
  /* §16.5 volatile intrinsics (memory-mapped I/O) */
  BUILTIN_VOLATILE_READ,  /* volatile_read(addr) → int64       */
  BUILTIN_VOLATILE_WRITE, /* volatile_write(addr, val) → 0     */
  /* §20 Dict builtins */
  BUILTIN_HASH,   /* hash(v) → 64-bit hash             */
  BUILTIN_KEYS,   /* keys(dict) → array of keys        */
  BUILTIN_VALUES, /* values(dict) → array of values    */
  /* §26.5 quantize — lowers to Q_QUANTIZE(arr, bits) */
  BUILTIN_QUANTIZE, /* quantize(tensor, bits: N)         */
  /* §24 flux / atomic / tensor builtins */
  BUILTIN_FLUX_DOT,     /* flux_dot(a, b) — sum(a[i]*b[i])    */
  BUILTIN_FLUX_LEN,     /* flux_len(v) — isqrt(sum(sq))       */
  BUILTIN_FLUX_NORM,    /* flux_norm(v) — v scaled to unit    */
  BUILTIN_FLUX_SPLAT,   /* flux_splat(val, n) — broadcast     */
  BUILTIN_FLUX_LOAD,    /* flux_load(addr, n) — SIMD load     */
  BUILTIN_FLUX_STORE,   /* flux_store(addr, arr)              */
  BUILTIN_TENSOR_SUM,   /* tensor_sum(t) — reduction          */
  BUILTIN_ATOMIC_CAS,   /* atomic_cas(slot, old, new)         */
  BUILTIN_ATOMIC_FENCE, /* atomic_fence() — seq_cst fence     */
  BUILTIN_FLUX_CTOR,    /* flux(v1, v2, ...) — array literal  */
  /* §19.4 array inspection / compaction */
  BUILTIN_CAP,         /* cap(arr) — underlying capacity      */
  BUILTIN_ARR_COMPACT, /* arr_compact(arr) — strip zero slots */
  /* §4.7 Arena allocator API */
  BUILTIN_ARENA_NEW,   /* arena_new(size) → arena_id          */
  BUILTIN_ARENA_ALLOC, /* arena_alloc(id, size) → address     */
  BUILTIN_ARENA_FREE,  /* arena_free(id) → 0                  */
  /* §22.5 Cooperative yield (`await pass` / `yield()`) */
  BUILTIN_YIELD, /* yield() — cooperative scheduler tick */

  /* §Phase-9 Intrinsic Registry — emit Q_INTRINSIC (table-driven dispatch)
   * These are distinct from opcode-based builtins above: they go through
   * vir_intr_table[id].fn(&ctx) in the VM instead of a dedicated opcode. */
  BUILTIN_SYSCALL,     /* __syscall(num, a1..a6) → raw OS syscall */
  BUILTIN_MEMCPY,      /* __memcpy(dst, src, len) → dst ptr       */
  BUILTIN_CAST_PTR,    /* cast_ptr(p) -> p */
  BUILTIN_MEMSET,      /* __memset(dst, val, len) → dst ptr       */
  BUILTIN_TRAP,        /* __trap() → abort (never returns)        */
  BUILTIN_UNREACHABLE, /* __unreachable() → UB hint / trap        */
  BUILTIN_CLZ,         /* __clz(n) → count leading zeros          */
  BUILTIN_CTZ,         /* __ctz(n) → count trailing zeros         */
  BUILTIN_POPCNT,      /* __popcnt(n) → popcount                  */
  BUILTIN_BSWAP,       /* __bswap(n) → byte swap                  */
  BUILTIN_ATOMIC_LOAD, /* __atomic_load(addr)                     */
  BUILTIN_ATOMIC_STORE,/* __atomic_store(addr, val)               */
  BUILTIN_ATOMIC_ADD,  /* __atomic_add(addr, val)                 */
  BUILTIN_ATOMIC_SUB,  /* __atomic_sub(addr, val)                 */
} builtin_id_t;

/* Forward declaration */
typedef struct ast_node ast_node_t;

#define AST_MAX_CHILDREN 16384
#define AST_NAME_LEN 64

#define AST_FLAG_REF_PARAM 0x0001u

struct ast_node {
  ast_type_t type;
  ast_op_t op;              /* For BINOP / COMPARE          */
  int64_t int_val;          /* For LITERAL_INT              */
  double float_val;         /* For LITERAL_FLOAT            */
  char name[AST_NAME_LEN];  /* FUNC_DEF name, IDENTIFIER, etc. */
  char name2[AST_NAME_LEN]; /* Secondary name (e.g. field name for FIELD_ACCESS)
                             */
  int builtin_id;           /* For BUILTIN_CALL             */
  int is_async;             /* For AST_FUNC_DEF - marks async functions (§22) */
  uint32_t flags;           /* Node-specific flags          */
  ast_node_t *children[AST_MAX_CHILDREN];
  uint32_t child_count;
  uint32_t line; /* Source line number            */
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

#define ENUM_MAX_VARIANTS 4096
#define ENUM_MAX_TYPES 1024

typedef struct {
  char name[AST_NAME_LEN]; /* variant name */
  int64_t value;           /* integer value */
} enum_variant_t;

typedef struct {
  char name[AST_NAME_LEN]; /* enum type name */
  enum_variant_t variants[ENUM_MAX_VARIANTS];
  uint32_t variant_count;
} enum_type_t;

/* ═══════════════════════════════════════════════════════
 * Record (Struct) Table
 * ═══════════════════════════════════════════════════════ */

#define RECORD_MAX_FIELDS 128
#define RECORD_MAX_TYPES 4096

typedef struct {
  char name[AST_NAME_LEN]; /* field name */
  char type_name[AST_NAME_LEN];
  uint32_t offset;         /* offset in units of int64 (0, 1, 2, ...) */
} record_field_t;

typedef struct {
  char name[AST_NAME_LEN]; /* record type name */
  record_field_t fields[RECORD_MAX_FIELDS];
  uint32_t field_count;
} record_type_t;

/* ═══════════════════════════════════════════════════════
 * Bit Type Table — §16 Register / Mold
 * ═══════════════════════════════════════════════════════
 * Register = hardware bit-mapped u32/u64, accessed via
 * volatile_read/volatile_write. Mold = general bit-pack
 * for protocol/pixel data. Both share the same extraction
 * and insertion lowering (shift + mask).
 */

#define BIT_TYPE_MAX_FIELDS 128
#define BIT_TYPE_MAX 256

typedef struct {
  char name[AST_NAME_LEN]; /* field name                */
  uint8_t lo;              /* low bit position (inclusive) */
  uint8_t width;           /* field width in bits (1–64)  */
} bit_field_t;

typedef struct {
  char name[AST_NAME_LEN]; /* type name */
  bit_field_t fields[BIT_TYPE_MAX_FIELDS];
  uint32_t field_count;
  uint8_t kind;       /* 0=register, 1=mold */
  uint8_t base_width; /* underlying int width (8/16/32/64) */
} bit_type_t;

/* ═══════════════════════════════════════════════════════
 * Symbol Table (for the lowering pass)
 * ═══════════════════════════════════════════════════════
 * Maps variable names → virtual register indices.
 */

#define SYM_MAX 16384

typedef struct {
  char name[AST_NAME_LEN];
  uint32_t vreg;
  vir_type_t type;
  char type_name[AST_NAME_LEN]; /* original type name string (e.g. "u8") */
  /* §4.8 Ownership tracking (per-symbol flags) */
  uint8_t is_move_type;        /* array/string/entity – needs drop */
  uint8_t is_moved;            /* value already moved out          */
  uint8_t borrow_shared_count; /* active shared borrows (&)        */
  uint8_t borrow_mut_count;    /* active mutable borrows (&mut)    */
  /* §13.7 atomic-var marker (`atomic var x = ...`):
   * Exempt from try(isolate:) snapshot/restore, exempt from W302
   * dirty-state warning. */
  uint8_t is_atomic;
  /* §16 Register/Mold binding: name of the bit_type_t this symbol
   * holds (empty string = ordinary scalar).
   * Set by `var x: TYPE = ...` when TYPE matches a register/mold. */
  char bit_type_name[AST_NAME_LEN];
  /* §4.8 NLL cross-statement borrow lifetime tracking:
   * If this symbol is a borrower (`var b = &a` or `var b = &mut a`),
   * borrow_of_name = "a" and borrow_kind = 1 (shared) or 2 (mut).
   * Released when the borrower is reassigned to a non-borrow value
   * or the enclosing function exits. */
  uint8_t borrow_kind; /* 0=none, 1=shared, 2=mut          */
  char borrow_of_name[AST_NAME_LEN];
  /* Ownership diagnostic tracking */
  uint32_t moved_at_line;      /* Line where the value was moved */
  uint32_t borrowed_at_line;   /* Line where the value was borrowed */
  /* §20 Dict binding: if the symbol holds a dict handle, set flag +
   * key_is_str (1 = string keys, 0 = int keys).  Distinguishes
   * m[k] from arr[i] at lowering time. */
  uint8_t is_dict;
  uint8_t dict_key_is_str;
  /* §25.1 reactive var: write emits Q_REACTIVE_NOTIFY */
  uint8_t is_reactive;
  /* §23 port: symbol holds a port handle */
  uint8_t is_port;
  /* §26.1 tensor: 2-D shape hint for Q_TENSOR_SHAPE + matmul dispatch */
  uint8_t is_tensor;
  uint32_t tensor_rows;
  uint32_t tensor_cols;
} symbol_entry_t;

typedef struct {
  symbol_entry_t entries[SYM_MAX];
  uint32_t count;
} symbol_table_t;

void sym_init(symbol_table_t *st);
int sym_define(symbol_table_t *st, const char *name, uint32_t vreg,
               vir_type_t type);
int sym_lookup(const symbol_table_t *st, const char *name, uint32_t *vreg);

/* ═══════════════════════════════════════════════════════
 * Live Interval (for register allocation)
 * ═══════════════════════════════════════════════════════ */

typedef struct {
  uint32_t vreg;
  uint32_t start; /* First instruction index that defines  */
  uint32_t end;   /* Last instruction index that uses      */
  int phys_reg;   /* Assigned physical register (-1=spill) */
  int spill_slot; /* Stack offset if spilled             */
} live_interval_t;

#define LOWER_MAX_INTERVALS 131072

/* ═══════════════════════════════════════════════════════
 * Lowering Context
 * ═══════════════════════════════════════════════════════ */

typedef struct {
  q_module_t module;
  q_vreg_alloc_t vreg_alloc;
  symbol_table_t symbols;
  symbol_table_t global_symbols; /* globals visible in all functions */
  uint32_t global_index_counter; /* next global slot index */
  uint32_t label_counter;
  uint32_t patch_counter;

  /* Enum + record type tables (compile-time) */
  enum_type_t enum_types[ENUM_MAX_TYPES];
  uint32_t enum_type_count;
  record_type_t record_types[RECORD_MAX_TYPES];
  uint32_t record_type_count;

  /* Best-effort function return record metadata, used by field-offset
   * resolution for values initialised from helper constructors. */
#define FUNC_RETURN_TYPE_MAX 2048
  struct {
    char name[AST_NAME_LEN];
    char type_name[AST_NAME_LEN];
  } func_return_types[FUNC_RETURN_TYPE_MAX];
  uint32_t func_return_type_count;

  /* §16 Register + Mold bit-type table (compile-time) */
  bit_type_t bit_types[BIT_TYPE_MAX];
  uint32_t bit_type_count;

  /* Loop label stack (for break/continue) */
#define LOOP_STACK_MAX 32
  uint32_t loop_start_labels[LOOP_STACK_MAX]; /* continue targets */
  uint32_t loop_end_labels[LOOP_STACK_MAX];   /* break targets */
  uint32_t loop_depth;

  /* Module alias table (for import X as Y) */
#define MODULE_ALIAS_MAX 64
  struct {
    char original[AST_NAME_LEN]; /* module name */
    char alias[AST_NAME_LEN];    /* alias (or same as original) */
  } module_aliases[MODULE_ALIAS_MAX];
  uint32_t module_alias_count;

  /* Imported symbol table (for from X import sym1, sym2) */
#define IMPORTED_SYM_MAX 128
  struct {
    char module[AST_NAME_LEN];
    char symbol[AST_NAME_LEN];
  } imported_syms[IMPORTED_SYM_MAX];
  uint32_t imported_sym_count;

  /* Include file handler (set by driver to resolve file paths) */
  char *(*include_reader)(const char *filename, size_t *out_len,
                          void *user_data);
  void *include_user_data;
  const char *include_search_paths[16];
  uint32_t include_search_path_count;

  /* Track included files to prevent double-include */
#define INCLUDE_MAX 64
  char included_files[INCLUDE_MAX][256];
  uint32_t included_file_count;

  /* Current function being lowered */
  q_function_t *current_func;

  /* Live intervals for register allocation */
  live_interval_t intervals[LOWER_MAX_INTERVALS];
  uint32_t interval_count;

  /* Error tracking */
  int error_count;
  char last_error[256];

  /* §4.8 NLL: transient borrow claims emitted during the current
   * lower_stmt. A binder (var_decl / assign) may claim the most
   * recent matching entry to create a persistent borrower back-link.
   * Unclaimed entries are released at lower_stmt exit. */
#define STMT_BORROW_MAX 32
  struct {
    char target[AST_NAME_LEN];
    uint8_t kind;    /* 1 = shared, 2 = mut */
    uint8_t claimed; /* 1 = consumed by a binder */
  } stmt_borrows[STMT_BORROW_MAX];
  uint32_t stmt_borrow_count;
  /* §20.2 Map expression context: when lowering the body of a map
   * expression, `out expr` (AST_RETURN) pushes expr into map_arr_vreg
   * instead of emitting Q_RET.  Zero = not in map context. */
  uint32_t map_arr_vreg;
  uint8_t in_map_expr;
} lower_ctx_t;

/* ═══════════════════════════════════════════════════════
 * API
 * ═══════════════════════════════════════════════════════ */

/* Initialise lowering context */
void lower_init(lower_ctx_t *ctx, const char *module_name);

/* Resolve a function name to its module index (-1 if missing). */
int lower_find_func_index(lower_ctx_t *ctx, const char *name);

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
int lower_tco_pass(q_function_t *func, uint32_t func_idx);

/* ── Cleanup ──────────────────────────────────────────── */

/* Get the produced Q-IR module (ownership transfers to caller) */
q_module_t *lower_get_module(lower_ctx_t *ctx);

/* Free context internal data (not the module itself) */
void lower_destroy(lower_ctx_t *ctx);

#ifdef __cplusplus
}
#endif

#endif /* VIR_IR_LOWER_H */
