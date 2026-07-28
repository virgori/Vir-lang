/*
 * diagnostic.h — Vir Diagnostic Engine (v2)
 * ============================================
 * Compiler-grade structured diagnostics.
 *
 * Architecture:
 *   - Arena-backed string storage (no heap per-diagnostic)
 *   - Byte-offset spans (UTF-8 safe, LSP compatible)
 *   - Abstract output sinks (terminal / buffer / JSON)
 *   - Labeled spans with ownership / borrow traces
 *   - Multiline-aware snippet rendering
 *   - Parser recovery metadata
 *   - Full ICE snapshot system
 *   - Deterministic, locale-independent rendering
 *   - Schema-versioned JSON for tooling stability
 *
 * Principles:
 *   - Show the problem clearly first
 *   - Show technical detail only when needed
 *   - Calm, structured, professional output
 *   - Bootstrap-safe: no malloc after init
 */

#ifndef VIR_DIAGNOSTIC_H
#define VIR_DIAGNOSTIC_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ═══════════════════════════════════════════════════════
 * §1  Severity Levels
 *
 * Ordered by priority. fatal > error > … > debug.
 * ═══════════════════════════════════════════════════════ */

typedef enum {
  DIAG_FATAL   = 0,   /* Compilation aborts immediately          */
  DIAG_ERROR   = 1,   /* Cannot produce valid output             */
  DIAG_WARNING = 2,   /* Potential issue, compilation continues   */
  DIAG_NOTE    = 3,   /* Attached clarification                  */
  DIAG_HELP    = 4,   /* Actionable guidance                     */
  DIAG_SUGGEST = 5,   /* Improvement hint (style, perf)          */
  DIAG_DEBUG   = 6,   /* Trace info (debug builds only)          */
  DIAG_ICE     = 7,   /* Internal compiler error (bug)           */
  DIAG_SEVERITY_COUNT
} diag_severity_t;

/* ═══════════════════════════════════════════════════════
 * §2  Diagnostic Categories
 *
 * Enables IDE filtering and warning suppression.
 * ═══════════════════════════════════════════════════════ */

typedef enum {
  DCAT_SYNTAX      = 0,   /* Lexer / parser errors                */
  DCAT_SEMANTIC    = 1,   /* Type, scope, resolution              */
  DCAT_OWNERSHIP   = 2,   /* Borrow checker, move semantics       */
  DCAT_LOWERING    = 3,   /* AST → IR translation                 */
  DCAT_OPTIMIZER   = 4,   /* IR optimization passes               */
  DCAT_CODEGEN     = 5,   /* Backend code generation              */
  DCAT_LINKER      = 6,   /* Symbol resolution, linking           */
  DCAT_MODULE      = 7,   /* Import / include resolution          */
  DCAT_PERFORMANCE = 8,   /* Performance hints                    */
  DCAT_PORTABILITY = 9,   /* Cross-platform issues                */
  DCAT_STYLE       = 10,  /* Code style / lint                    */
  DCAT_INTERNAL    = 11,  /* Compiler internals / ICE              */
  DCAT_COUNT
} diag_category_t;

/* ═══════════════════════════════════════════════════════
 * §3  Compiler Phases
 * ═══════════════════════════════════════════════════════ */

typedef enum {
  PHASE_LEXER     = 0,
  PHASE_PARSER    = 1,
  PHASE_SEMA      = 2,
  PHASE_IR_LOWER  = 3,
  PHASE_IR_OPT    = 4,
  PHASE_REGALLOC  = 5,
  PHASE_CODEGEN   = 6,
  PHASE_LINKER    = 7,
  PHASE_RESOLVE   = 8,
  PHASE_BORROW    = 9,
  PHASE_COUNT
} diag_phase_t;

/* ═══════════════════════════════════════════════════════
 * §4  Bootstrap Stage
 * ═══════════════════════════════════════════════════════ */

typedef enum {
  STAGE_0_C_CORE   = 0,
  STAGE_1_VIR      = 1,
} diag_stage_t;

/* ═══════════════════════════════════════════════════════
 * §5  Error Code Catalog
 *
 *   E0xxx  Lexer          W0xxx  Lexer warnings
 *   E1xxx  Parser         W1xxx  Parser warnings
 *   E2xxx  Semantic       W2xxx  Semantic warnings
 *   E3xxx  IR lowering
 *   E4xxx  Optimization
 *   E5xxx  CodeGen
 *   E6xxx  Linker
 *   E7xxx  Module resolver
 *   E8xxx  Borrow checker
 *   E9xxx  ICE
 * ═══════════════════════════════════════════════════════ */

/* Lexer */
#define E0001 1     /* Invalid character                         */
#define E0002 2     /* Unterminated string literal                */
#define E0003 3     /* Invalid numeric literal                    */

/* Parser */
#define E1001 1001  /* Unexpected token                          */
#define E1002 1002  /* Missing block delimiter (end)             */
#define E1003 1003  /* Missing colon after condition             */
#define E1004 1004  /* Invalid expression                        */
#define E1005 1005  /* Unexpected end of file                    */
#define E1006 1006  /* Invalid function signature                */
#define E1007 1007  /* Mismatched parentheses                    */
#define E1008 1008  /* Invalid case pattern                      */
#define E1009 1009  /* Parser progress guard triggered           */
#define E1010 1010  /* Recursion depth exceeded                  */

/* Semantic */
#define E2001 2001  /* Undefined variable                        */
#define E2002 2002  /* Undefined function                        */
#define E2003 2003  /* Type mismatch                             */
#define E2004 2004  /* Duplicate definition                      */
#define E2005 2005  /* Invalid assignment target                 */

/* IR Lowering */
#define E3001 3001  /* Unsupported expression type               */
#define E3002 3002  /* Undefined variable in lowering            */
#define E3003 3003  /* Invalid lowering target                   */

/* Module */
#define E7001 7001  /* Module not found                          */
#define E7002 7002  /* Cyclic import                             */
#define E7003 7003  /* Symbol not exported                       */
#define E7004 7004  /* Keyword collision in module path          */

/* Borrow */
#define E8001 8001  /* Use after move                            */
#define E8002 8002  /* Overlapping mutable borrow                */
#define E8003 8003  /* Borrow outlives owner                     */
#define E8004 8004  /* Arena value escapes its block (§4.6)      */

/* ICE */
#define E9001 9001  /* Lowering invariant violated               */
#define E9002 9002  /* Unexpected AST node                       */
#define E9003 9003  /* Register allocation failure               */

/* ═══════════════════════════════════════════════════════
 * §6  Source Span
 *
 * Byte-offset–based. Safe for UTF-8, incremental
 * parsing, rope buffers, and LSP integration.
 *
 * Visual line/col are computed on demand from offsets.
 * ═══════════════════════════════════════════════════════ */

typedef uint32_t diag_file_id_t;  /* Opaque handle into source registry */

#define DIAG_NO_FILE ((diag_file_id_t)0xFFFFFFFFu)

typedef struct {
  diag_file_id_t file_id;       /* Source file handle                  */

  /* Byte offsets — primary addressing mode                            */
  uint32_t       start_byte;    /* Start offset in source buffer       */
  uint32_t       end_byte;      /* End offset (exclusive)              */

  /* Visual coordinates — cached, 1-based, computed from offsets       */
  uint32_t       line;
  uint32_t       col;
  uint32_t       end_line;
  uint32_t       end_col;
} diag_span_t;

#define DIAG_SPAN_EMPTY ((diag_span_t){0})

static inline uint32_t diag_span_len(diag_span_t s) {
  return s.end_byte > s.start_byte ? s.end_byte - s.start_byte : 0;
}

static inline int diag_span_is_multiline(diag_span_t s) {
  return s.end_line > s.line;
}

/* ═══════════════════════════════════════════════════════
 * §7  String Arena
 *
 * All diagnostic strings live in a contiguous arena.
 * A diag_str_t is an offset+length view into the arena.
 * No heap allocation per diagnostic.
 * ═══════════════════════════════════════════════════════ */

#define DIAG_ARENA_SIZE (64 * 1024)  /* 64 KiB — fits in L1 cache */

typedef struct {
  uint32_t offset;    /* Byte offset into arena                    */
  uint32_t length;    /* Byte count (NOT null-terminated)           */
} diag_str_t;

#define DIAG_STR_EMPTY ((diag_str_t){0, 0})

typedef struct {
  char     data[DIAG_ARENA_SIZE];
  uint32_t used;
} diag_arena_t;

/* ═══════════════════════════════════════════════════════
 * §8  Labeled Span
 *
 * A span with an attached label and role.
 * Used for primary highlights, secondary notes,
 * ownership traces, and borrow origins.
 * ═══════════════════════════════════════════════════════ */

typedef enum {
  LABEL_PRIMARY   = 0,   /* Main error location                   */
  LABEL_SECONDARY = 1,   /* Related location                      */
  LABEL_NOTE      = 2,   /* Explanatory note                      */
  LABEL_HELP      = 3,   /* Suggested fix location                */
  LABEL_ORIGIN    = 4,   /* Where value was created / moved       */
} diag_label_role_t;

#define DIAG_MAX_LABELS 8

typedef struct {
  diag_span_t       span;
  diag_str_t        text;     /* Label text (arena-backed)          */
  diag_label_role_t role;
} diag_label_t;

/* ═══════════════════════════════════════════════════════
 * §9  Fix Suggestion
 * ═══════════════════════════════════════════════════════ */

#define DIAG_MAX_FIXES 4

typedef struct {
  diag_str_t  message;         /* Human-readable description        */
  diag_span_t span;            /* Where the fix applies             */
  diag_str_t  replacement;     /* Replacement text                  */
  int         is_applicable;   /* 1 = machine-applicable            */
} diag_fix_t;

/* ═══════════════════════════════════════════════════════
 * §10  Parser Recovery Metadata
 * ═══════════════════════════════════════════════════════ */

typedef struct {
  uint32_t token_index;      /* Token position at error             */
  uint32_t sync_token_index; /* Where recovery synchronized         */
  uint32_t parser_depth;     /* Recursion depth at error            */
  int      recovered;        /* 1 = parser recovered and continued  */
  diag_str_t sync_token_name;/* Name of synchronization token       */
} diag_recovery_t;

/* ═══════════════════════════════════════════════════════
 * §11  ICE Snapshot
 *
 * Captures compiler state at the point of an internal
 * compiler error for post-mortem debugging.
 * ═══════════════════════════════════════════════════════ */

typedef struct {
  /* C source location */
  const char *c_file;         /* __FILE__                            */
  uint32_t    c_line;         /* __LINE__                            */
  const char *c_func;         /* __func__                            */

  /* Compiler state snapshot */
  diag_str_t  current_module; /* Module being compiled               */
  diag_str_t  compiler_pass;  /* Active pass name                    */
  int32_t     ast_node_type;  /* Current AST node type (-1 = none)   */
  uint32_t    token_index;    /* Current token index                 */
  uint32_t    ir_opcode;      /* Current IR opcode (0 = none)        */
} diag_ice_t;

/* ═══════════════════════════════════════════════════════
 * §12  Diagnostic Entry
 * ═══════════════════════════════════════════════════════ */

typedef struct {
  /* Identity */
  uint32_t         code;
  diag_severity_t  severity;
  diag_phase_t     phase;
  diag_stage_t     stage;
  diag_category_t  category;

  /* Primary span */
  diag_span_t      span;

  /* Messages (arena-backed) */
  diag_str_t       summary;     /* Short human-readable message      */
  diag_str_t       detail;      /* Extended explanation               */
  diag_str_t       analysis;    /* Detailed failure analysis          */

  /* Structured root cause and actions */
  diag_str_t       causes[8];
  uint32_t         cause_count;
  diag_str_t       actions[8];
  uint32_t         action_count;

  /* Multiple spans */
  diag_span_t      related[8];
  diag_str_t       related_labels[8];
  uint32_t         related_count;

  /* Labeled spans */
  diag_label_t     labels[DIAG_MAX_LABELS];
  uint32_t         label_count;

  /* Fix suggestions */
  diag_fix_t       fixes[DIAG_MAX_FIXES];
  uint32_t         fix_count;

  /* Parser recovery info (optional) */
  diag_recovery_t  recovery;
  int              has_recovery;

  /* ICE snapshot (optional) */
  diag_ice_t       ice;
  int              has_ice;
} diag_entry_t;

/* ═══════════════════════════════════════════════════════
 * §13  Source Registry
 *
 * Maps file IDs to source buffers. Supports multiple
 * files, virtual sources, and incremental updates.
 * ═══════════════════════════════════════════════════════ */

#define DIAG_MAX_FILES 128

typedef struct {
  const char *filename;       /* File path (borrowed)                */
  const char *source;         /* Source text (borrowed)              */
  size_t      source_len;
  int         active;         /* 1 = slot in use                     */
} diag_source_t;

/* ═══════════════════════════════════════════════════════
 * §14  Output Sink (Abstract Writer)
 *
 * Decouples diagnostic rendering from I/O target.
 * Supports terminal, buffer, file, or custom output.
 * ═══════════════════════════════════════════════════════ */

typedef struct diag_sink_s diag_sink_t;

/* Write callback: write `len` bytes from `data` to sink.
 * Returns bytes written, or 0 on error. */
typedef size_t (*diag_write_fn)(diag_sink_t *sink, const char *data, size_t len);

struct diag_sink_s {
  diag_write_fn write;
  void         *userdata;     /* Opaque context for the callback     */
};

/* Built-in sink constructors */
diag_sink_t diag_sink_stderr(void);
diag_sink_t diag_sink_buffer(char *buf, size_t capacity);

/* Buffer sink: query bytes written */
size_t diag_sink_buffer_used(const diag_sink_t *sink);

/* ═══════════════════════════════════════════════════════
 * §15  Output Format
 * ═══════════════════════════════════════════════════════ */

typedef enum {
  DIAG_FMT_TERMINAL = 0,   /* ANSI-colored pretty output          */
  DIAG_FMT_PLAIN    = 1,   /* No color, CI/log friendly            */
  DIAG_FMT_JSON     = 2,   /* Machine-readable JSON                */
} diag_format_t;

/* ═══════════════════════════════════════════════════════
 * §16  Diagnostic Context
 *
 * Central state. Pre-allocated, arena-backed.
 * Thread-local in future parallel compilation.
 * ═══════════════════════════════════════════════════════ */

#define DIAG_MAX_ENTRIES 128

typedef struct {
  /* Diagnostic storage */
  diag_entry_t    entries[DIAG_MAX_ENTRIES];
  uint32_t        count;

  /* Counters by severity */
  uint32_t        fatal_count;
  uint32_t        error_count;
  uint32_t        warning_count;
  uint32_t        note_count;

  /* String arena */
  diag_arena_t    arena;

  /* Source registry */
  diag_source_t   files[DIAG_MAX_FILES];
  uint32_t        file_count;

  /* Configuration */
  diag_stage_t    active_stage;
  diag_format_t   format;
  diag_sink_t     sink;
  uint32_t        report_code;

  /* Overflow flag — set when arena or entries are full */
  int             overflow;
} diag_context_t;

/* ═══════════════════════════════════════════════════════
 * §17  API — Lifecycle
 * ═══════════════════════════════════════════════════════ */

void diag_init(diag_context_t *ctx, diag_stage_t stage, diag_format_t fmt);

/* Register a source file. Returns file_id for span construction.
 * Source text must remain valid for the lifetime of the context. */
diag_file_id_t diag_register_source(diag_context_t *ctx,
                                     const char *filename,
                                     const char *text, size_t len);

/* Set the default output sink (default: stderr) */
void diag_set_sink(diag_context_t *ctx, diag_sink_t sink);

/* ═══════════════════════════════════════════════════════
 * §18  API — Span Construction
 * ═══════════════════════════════════════════════════════ */

/* Build a span from byte offsets. Visual line/col are
 * computed lazily from the source buffer. */
diag_span_t diag_span(diag_file_id_t file,
                       uint32_t start_byte, uint32_t end_byte);

/* Build a span from line/col (1-based). Byte offsets
 * are computed from the source buffer. */
diag_span_t diag_span_lc(diag_file_id_t file,
                          uint32_t line, uint32_t col, uint32_t length);

/* Resolve visual coordinates for a span (populates line/col fields).
 * Called automatically during rendering. */
void diag_span_resolve(const diag_context_t *ctx, diag_span_t *span);

/* ═══════════════════════════════════════════════════════
 * §19  API — Arena Strings
 * ═══════════════════════════════════════════════════════ */

/* Intern a string into the arena. Returns DIAG_STR_EMPTY on overflow. */
diag_str_t diag_intern(diag_context_t *ctx, const char *str);
diag_str_t diag_intern_len(diag_context_t *ctx, const char *str, uint32_t len);
diag_str_t diag_intern_fmt(diag_context_t *ctx, const char *fmt, ...)
    __attribute__((format(printf, 2, 3)));

/* Read back an interned string (returns pointer into arena, NOT null-terminated) */
const char *diag_str_ptr(const diag_context_t *ctx, diag_str_t s);

/* ═══════════════════════════════════════════════════════
 * §20  API — Emitting Diagnostics
 * ═══════════════════════════════════════════════════════ */

/* Core emit function. Returns pointer for enrichment, NULL on overflow. */
diag_entry_t *diag_emit(diag_context_t *ctx,
                         diag_severity_t severity,
                         diag_category_t category,
                         diag_phase_t phase,
                         uint32_t code,
                         diag_span_t span,
                         const char *summary);

/* Convenience: emit with line/col (for legacy callsites) */
diag_entry_t *diag_emit_lc(diag_context_t *ctx,
                            diag_severity_t severity,
                            diag_category_t category,
                            diag_phase_t phase,
                            uint32_t code,
                            diag_file_id_t file,
                            uint32_t line, uint32_t col, uint32_t length,
                            const char *summary);

/* Shorthand macros */
#define diag_error(ctx, cat, phase, code, span, msg) \
    diag_emit(ctx, DIAG_ERROR, cat, phase, code, span, msg)

#define diag_warning(ctx, cat, phase, code, span, msg) \
    diag_emit(ctx, DIAG_WARNING, cat, phase, code, span, msg)

#define diag_note(ctx, cat, phase, code, span, msg) \
    diag_emit(ctx, DIAG_NOTE, cat, phase, code, span, msg)

/* ICE macro — captures C source location automatically */
#define diag_ice(ctx, code, msg) do {                                \
    diag_entry_t *_e = diag_emit(ctx, DIAG_ICE, DCAT_INTERNAL,      \
        PHASE_PARSER, code, DIAG_SPAN_EMPTY, msg);                  \
    if (_e) {                                                        \
        _e->has_ice = 1;                                             \
        _e->ice.c_file = __FILE__;                                   \
        _e->ice.c_line = __LINE__;                                   \
        _e->ice.c_func = __func__;                                   \
        _e->ice.ast_node_type = -1;                                  \
    }                                                                \
} while(0)

/* ICE with phase */
#define diag_ice_phase(ctx, phase, code, msg) do {                   \
    diag_entry_t *_e = diag_emit(ctx, DIAG_ICE, DCAT_INTERNAL,      \
        phase, code, DIAG_SPAN_EMPTY, msg);                          \
    if (_e) {                                                        \
        _e->has_ice = 1;                                             \
        _e->ice.c_file = __FILE__;                                   \
        _e->ice.c_line = __LINE__;                                   \
        _e->ice.c_func = __func__;                                   \
        _e->ice.ast_node_type = -1;                                  \
    }                                                                \
} while(0)

/* ═══════════════════════════════════════════════════════
 * §21  API — Enrichment
 * ═══════════════════════════════════════════════════════ */

/* Add a labeled span */
void diag_add_label(diag_context_t *ctx, diag_entry_t *entry,
                    diag_span_t span, diag_label_role_t role,
                    const char *text);

/* Add a fix suggestion */
void diag_add_fix(diag_context_t *ctx, diag_entry_t *entry,
                  const char *message,
                  diag_span_t span, const char *replacement);

/* Add a human-readable suggestion (no replacement) */
void diag_add_suggestion(diag_context_t *ctx, diag_entry_t *entry,
                         const char *text);

/* Set extended detail text */
void diag_set_detail(diag_context_t *ctx, diag_entry_t *entry,
                     const char *detail);

/* Analysis and fixes */
void diag_set_analysis(diag_context_t *ctx, diag_entry_t *entry, const char *analysis);
void diag_add_cause(diag_context_t *ctx, diag_entry_t *entry, const char *cause);
void diag_add_action(diag_context_t *ctx, diag_entry_t *entry, const char *action);
void diag_add_related_span(diag_context_t *ctx, diag_entry_t *entry, diag_span_t span, const char *label);

/* Attach parser recovery metadata */
void diag_set_recovery(diag_entry_t *entry,
                       uint32_t token_index,
                       uint32_t sync_token_index,
                       uint32_t depth,
                       int recovered);

/* Enrich ICE with compiler state */
void diag_ice_set_state(diag_context_t *ctx, diag_entry_t *entry,
                        const char *module, const char *pass,
                        int32_t ast_node_type, uint32_t token_index,
                        uint32_t ir_opcode);

/* ═══════════════════════════════════════════════════════
 * §22  API — Rendering
 * ═══════════════════════════════════════════════════════ */

/* Render a single diagnostic to the configured sink */
void diag_render(diag_context_t *ctx, const diag_entry_t *entry);

/* Render all accumulated diagnostics */
void diag_render_all(diag_context_t *ctx);

/* Render summary line */
void diag_render_summary(diag_context_t *ctx);

/* ═══════════════════════════════════════════════════════
 * §23  API — JSON / LSP Serialization
 *
 * Schema version: 1
 * All JSON output includes a "schema_version" field.
 * ═══════════════════════════════════════════════════════ */

#define DIAG_JSON_SCHEMA_VERSION 1

/* Serialize a single diagnostic as JSON into a sink.
 * Returns bytes written. */
size_t diag_to_json(diag_context_t *ctx,
                    const diag_entry_t *entry,
                    diag_sink_t *sink);

/* Serialize all diagnostics as a JSON array. */
size_t diag_all_to_json(diag_context_t *ctx, diag_sink_t *sink);

/* ═══════════════════════════════════════════════════════
 * §24  API — Query
 * ═══════════════════════════════════════════════════════ */

int      diag_has_errors(const diag_context_t *ctx);
int      diag_has_fatal(const diag_context_t *ctx);
uint32_t diag_count(const diag_context_t *ctx, diag_severity_t severity);

/* ═══════════════════════════════════════════════════════
 * §25  Typo Recovery & Suggestion Engine
 * ═══════════════════════════════════════════════════════ */

/* Levenshtein distance (bounded, stack-friendly) */
int diag_levenshtein(const char *a, const char *b, int max_dist);

/* Best match from candidates. Returns NULL if none within threshold. */
const char *diag_suggest_typo(const char *input,
                               const char *const *candidates,
                               int count, int threshold);

/* Token-expectation–aware suggestion.
 * Given current parser state, suggest what was likely intended. */
typedef struct {
  const char *const *expected_tokens;   /* Expected token names        */
  int                expected_count;
  const char        *got_token;         /* What was actually found     */
  uint32_t           parser_depth;
} diag_expect_ctx_t;

/* Returns a human-readable suggestion string, or NULL.
 * The returned string is static / arena-backed. */
const char *diag_suggest_expected(diag_context_t *ctx,
                                   const diag_expect_ctx_t *ectx);

/* ═══════════════════════════════════════════════════════
 * §26  Source Utilities
 * ═══════════════════════════════════════════════════════ */

/* Extract a source line by line number (1-based).
 * Returns pointer into source buffer, sets *out_len.
 * Returns NULL if line not found. */
const char *diag_get_line(const diag_context_t *ctx,
                           diag_file_id_t file,
                           uint32_t line,
                           uint32_t *out_len);

/* Compute line/col from byte offset.
 * Both are 1-based. Returns 0 on failure. */
int diag_offset_to_lc(const diag_context_t *ctx,
                       diag_file_id_t file,
                       uint32_t byte_offset,
                       uint32_t *out_line, uint32_t *out_col);

/* Compute byte offset from line/col (1-based).
 * Returns UINT32_MAX on failure. */
uint32_t diag_lc_to_offset(const diag_context_t *ctx,
                            diag_file_id_t file,
                            uint32_t line, uint32_t col);

#ifdef __cplusplus
}
#endif

#endif /* VIR_DIAGNOSTIC_H */
