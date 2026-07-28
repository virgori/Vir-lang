/*
 * main.c – Vir CLI Driver
 * ========================
 * Pure-C entry point for the Vir programming language.
 *
 * Usage:
 *   vir run   <file.vri>   Interpret via Q-IR VM
 *   vir jit   <file.vri>   JIT compile and execute
 *   vir dump  <file.vri>   Print Q-IR text
 *   vir tokens <file.vri>  Print token stream
 *   vir help               Show usage
 */

#include "vir.h"
#include "lexer.h"
#include "parser.h"
#include "ir_lower.h"
#include "compiler_pipeline.h"
#include "vm.h"
#include "codegen.h"
#include "jit_bridge.h"
#include "intrinsics.h"
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <stdint.h>
#include <time.h>
#include "diagnostic.h"

extern diag_context_t g_parser_diag;
extern int g_diag_initialized;

typedef struct {
    int enabled;
    int timing;
    FILE *file;
    uint64_t start_ms;
    const char *last_phase;
} stage1_trace_t;

static stage1_trace_t g_stage1_trace = {0};

static uint64_t trace_now_ms(void)
{
    struct timespec ts;
#if defined(CLOCK_MONOTONIC)
    clock_gettime(CLOCK_MONOTONIC, &ts);
#else
    clock_gettime(CLOCK_REALTIME, &ts);
#endif
    return (uint64_t)ts.tv_sec * 1000ULL + (uint64_t)ts.tv_nsec / 1000000ULL;
}

static void trace_stage1_init(void)
{
    const char *stage = getenv("VIR_TRACE_STAGE1");
    const char *timing = getenv("VIR_TRACE_TIMING");
    const char *path = getenv("VIR_TRACE_FILE");
    g_stage1_trace.enabled = (stage && stage[0] && strcmp(stage, "0") != 0) ||
                             (timing && timing[0] && strcmp(timing, "0") != 0);
    g_stage1_trace.timing = timing && timing[0] && strcmp(timing, "0") != 0;
    if (!g_stage1_trace.enabled) return;

    g_stage1_trace.start_ms = trace_now_ms();
    g_stage1_trace.last_phase = "trace_init";
    if (path && path[0]) {
        g_stage1_trace.file = fopen(path, "a");
    }
    if (!g_stage1_trace.file) {
        g_stage1_trace.file = stderr;
    }
    setvbuf(g_stage1_trace.file, NULL, _IOLBF, 0);
}

static void trace_stage1_close(void)
{
    if (g_stage1_trace.file && g_stage1_trace.file != stderr) {
        fclose(g_stage1_trace.file);
    }
    g_stage1_trace.file = NULL;
}

static void trace_stage1_event(const char *phase, const char *fmt, ...)
{
    if (!g_stage1_trace.enabled || !g_stage1_trace.file) return;
    uint64_t now = trace_now_ms();
    fprintf(g_stage1_trace.file, "elapsed_ms=%llu phase=%s",
            (unsigned long long)(now - g_stage1_trace.start_ms), phase);
    if (fmt && fmt[0]) {
        fputc(' ', g_stage1_trace.file);
        va_list ap;
        va_start(ap, fmt);
        vfprintf(g_stage1_trace.file, fmt, ap);
        va_end(ap);
    }
    fputc('\n', g_stage1_trace.file);
    fflush(g_stage1_trace.file);
    g_stage1_trace.last_phase = phase;
}

static uint64_t ast_count_nodes(const ast_node_t *node)
{
    if (!node) return 0;
    uint64_t total = 1;
    for (uint32_t i = 0; i < node->child_count; i++) {
        total += ast_count_nodes(node->children[i]);
    }
    return total;
}

static uint64_t ast_count_blocks(const ast_node_t *node)
{
    if (!node) return 0;
    uint64_t total = node->type == AST_BLOCK ? 1 : 0;
    for (uint32_t i = 0; i < node->child_count; i++) {
        total += ast_count_blocks(node->children[i]);
    }
    return total;
}

static uint64_t module_instruction_count(const q_module_t *mod)
{
    if (!mod) return 0;
    uint64_t total = 0;
    for (uint32_t i = 0; i < mod->func_count; i++) {
        total += mod->functions[i].body_count;
    }
    return total;
}

static uint64_t module_label_count(const q_module_t *mod)
{
    if (!mod) return 0;
    uint64_t total = 0;
    for (uint32_t fi = 0; fi < mod->func_count; fi++) {
        const q_function_t *fn = &mod->functions[fi];
        for (uint32_t ii = 0; ii < fn->body_count; ii++) {
            if (fn->body[ii].opcode == Q_LABEL) total++;
        }
    }
    return total;
}

/* ── Read file into malloc'd buffer ────────────────── */
static char *read_source_silent(const char *path, size_t *out_len)
{
    FILE *f = fopen(path, "rb");
    if (!f) return NULL;
    fseek(f, 0, SEEK_END);
    long len = ftell(f);
    fseek(f, 0, SEEK_SET);

    char *buf = malloc((size_t)len + 1);
    if (!buf) { fclose(f); return NULL; }
    fread(buf, 1, (size_t)len, f);
    buf[len] = '\0';
    fclose(f);
    *out_len = (size_t)len;
    return buf;
}

static char *read_source(const char *path, size_t *out_len)
{
    char *buf = read_source_silent(path, out_len);
    if (!buf) fprintf(stderr, "error: cannot open '%s'\n", path);
    return buf;
}

/* ── Include file reader callback ─────────────────── */
typedef struct {
    char base_dir[512];      /* directory of the main source file */
} include_ctx_t;

/* Translate a module path like "vir.rt.syscall" or "vir::rt::syscall"
 * into a relative filesystem path "vir/rt/syscall.vri".  If the input
 * already ends with ".vri" or contains a '/', it is copied verbatim. */
static void module_to_relpath(const char *name, char *out, size_t out_sz)
{
    size_t n = strlen(name);
    int has_sep    = (strchr(name, '/') != NULL);
    int has_suffix = (n >= 4 && strcmp(name + n - 4, ".vri") == 0);
    if (has_sep || has_suffix) {
        snprintf(out, out_sz, "%s", name);
        return;
    }
    size_t w = 0;
    for (size_t i = 0; i < n && w + 1 < out_sz; ) {
        if (name[i] == '.') { out[w++] = '/'; i++; continue; }
        if (name[i] == ':' && i + 1 < n && name[i+1] == ':') {
            out[w++] = '/'; i += 2; continue;
        }
        out[w++] = name[i++];
    }
    if (w + 4 < out_sz) { memcpy(out + w, ".vri", 4); w += 4; }
    out[w] = '\0';
}

static char *vir_include_reader(const char *filename, size_t *out_len,
                                void *user_data)
{
    include_ctx_t *ictx = (include_ctx_t *)user_data;
    char relpath[600];
    char path[1024];
    char *src;

    module_to_relpath(filename, relpath, sizeof(relpath));

    /* 1) <base_dir>/<relpath> */
    snprintf(path, sizeof(path), "%s/%s", ictx->base_dir, relpath);
    if ((src = read_source_silent(path, out_len))) return src;

    /* 2) <base_dir>/../<relpath> — sibling folders via "include types" */
    snprintf(path, sizeof(path), "%s/../%s", ictx->base_dir, relpath);
    if ((src = read_source_silent(path, out_len))) return src;

    /* 3) $VIR_STDLIB/<relpath> (plus common subdirs for bare names
     *    like "types" / "syscall" / "string_rt"). */
    const char *env = getenv("VIR_STDLIB");
    if (env && *env) {
        static const char *subs[] = {
            "",                 /* env/<rel>           */
            "vir",              /* env/vir/<rel>       */
            "vir/core",         /* env/vir/core/<rel>  */
            "vir/rt",           /* env/vir/rt/<rel>    */
            "vir/str",          /* env/vir/str/<rel>   */
            "vir/mem",          /* env/vir/mem/<rel>   */
            "vir/io",           /* env/vir/io/<rel>    */
            "vir/error",        /* env/vir/error/<rel> */
            "vir/compiler",     /* env/vir/compiler/<rel> */
            "vir/collections",
            NULL
        };
        for (int si = 0; subs[si] != NULL; si++) {
            if (subs[si][0] == '\0')
                snprintf(path, sizeof(path), "%s/%s", env, relpath);
            else
                snprintf(path, sizeof(path), "%s/%s/%s", env, subs[si], relpath);
            if ((src = read_source_silent(path, out_len))) return src;
        }
    }

    /* 4) Walk upwards from base_dir trying `<walk>/<relpath>` and
     *    `<walk>/stdlib/<relpath>` at each level. */
    char walk[1024];
    snprintf(walk, sizeof(walk), "%s", ictx->base_dir);
    for (int depth = 0; depth < 10; depth++) {
        snprintf(path, sizeof(path), "%s/%s", walk, relpath);
        if ((src = read_source_silent(path, out_len))) return src;
        snprintf(path, sizeof(path), "%s/stdlib/%s", walk, relpath);
        if ((src = read_source_silent(path, out_len))) return src;
        char *last = strrchr(walk, '/');
        if (!last) break;
        if (last == walk) { walk[1] = '\0'; }  /* "/" root */
        else { *last = '\0'; }
        if (walk[0] == '\0') break;
    }

    /* 5) Repo-root stdlib fallback for relative base_dir runs. */
    static const char *cwd_subs[] = {
        "stdlib/vir",
        "stdlib/vir/core",
        "stdlib/vir/rt",
        "stdlib/vir/str",
        "stdlib/vir/mem",
        "stdlib/vir/io",
        "stdlib/vir/error",
        "stdlib/vir/compiler",
        "stdlib/vir/collections",
        NULL
    };
    for (int si = 0; cwd_subs[si] != NULL; si++) {
        snprintf(path, sizeof(path), "%s/%s", cwd_subs[si], relpath);
        if ((src = read_source_silent(path, out_len))) return src;
    }

    /* 6) Fallback: cwd-relative (either translated or verbatim). */
    if ((src = read_source_silent(relpath, out_len))) {
        return src;
    }
    src = read_source(filename, out_len);
    return src;  /* noisy: prints cannot-open */
}

/* Extract directory from a file path */
static void get_dir(const char *filepath, char *dir, size_t dir_size)
{
    strncpy(dir, filepath, dir_size - 1);
    dir[dir_size - 1] = '\0';
    char *last_sep = strrchr(dir, '/');
    if (last_sep) *last_sep = '\0';
    else strncpy(dir, ".", dir_size);
}

/* ── Frontend: source → AST ───────────────────────── */
static ast_node_t *frontend(const char *filepath, const char *source, size_t len, int verbose)
{
    diag_file_id_t file_id = DIAG_NO_FILE;
    if (g_diag_initialized && filepath) {
        file_id = diag_register_source(&g_parser_diag, filepath, source, len);
    }
    /* Tokenize */
    uint64_t phase_start = trace_now_ms();
    trace_stage1_event("lexer_start", "file=%s bytes=%zu", filepath ? filepath : "", len);
    vir_lexer_t lex;
    lexer_init(&lex, source, len);
    if (lexer_tokenize(&lex) != 0) {
        trace_stage1_event("lexer_error", "elapsed_phase_ms=%llu error=%s",
                           (unsigned long long)(trace_now_ms() - phase_start), lex.error);
        fprintf(stderr, "lexer error: %s\n", lex.error);
        lexer_free(&lex);
        return NULL;
    }
    trace_stage1_event("lexer_end", "elapsed_phase_ms=%llu token_count=%u",
                       (unsigned long long)(trace_now_ms() - phase_start),
                       lex.token_count);
    if (verbose) {
        fprintf(stderr, "[vir] %u tokens\n", lex.token_count);
    }

    /* Parse → AST */
    phase_start = trace_now_ms();
    trace_stage1_event("parser_start", "token_count=%u", lex.token_count);
    vir_parser_t parser;
    parser_init(&parser, lex.tokens, lex.token_count, file_id);
    ast_node_t *ast = parser_parse_program(&parser);
    lexer_free(&lex);
    if (!ast || parser.error[0] != '\0' || (g_diag_initialized && g_parser_diag.count > 0)) {
        trace_stage1_event("parser_error", "elapsed_phase_ms=%llu pos=%u error=%s",
                           (unsigned long long)(trace_now_ms() - phase_start),
                           parser.pos, parser.error);
        if (0) {
            diag_render_all(&g_parser_diag);
        } else {
            fprintf(stderr, "parse error in %s (line %u): %s\n", filepath, 
                    parser.error_line, parser.error);
        }
        if (ast) ast_free(ast);
        return NULL;
    }
    trace_stage1_event("parser_end",
                       "elapsed_phase_ms=%llu ast_node_count=%llu block_count=%llu top_level=%u",
                       (unsigned long long)(trace_now_ms() - phase_start),
                       (unsigned long long)ast_count_nodes(ast),
                       (unsigned long long)ast_count_blocks(ast),
                       ast->child_count);
    if (verbose) {
        fprintf(stderr, "[vir] AST: %u top-level nodes\n",
                ast->child_count);
    }
    return ast;
}

/* ── cmd: tokens ──────────────────────────────────── */
static int cmd_tokens(const char *source, size_t len)
{
    vir_lexer_t lex;
    lexer_init(&lex, source, len);
    if (lexer_tokenize(&lex) != 0) {
        fprintf(stderr, "lexer error: %s\n", lex.error);
        lexer_free(&lex);
        return 1;
    }
    for (uint32_t i = 0; i < lex.token_count; i++) {
        const vir_token_t *t = &lex.tokens[i];
        const char *name = lexer_token_name(t->type);
        switch (t->type) {
        case TOK_INT:
            printf("%4u:%-3u %-16s %lld\n",
                   t->line, t->col, name, (long long)t->int_val);
            break;
        case TOK_FLOAT:
            printf("%4u:%-3u %-16s %g\n",
                   t->line, t->col, name, t->float_val);
            break;
        case TOK_STRING: case TOK_IDENT:
            printf("%4u:%-3u %-16s %s\n",
                   t->line, t->col, name, t->str.buf);
            break;
        default:
            printf("%4u:%-3u %s\n", t->line, t->col, name);
            break;
        }
    }
    lexer_free(&lex);
    return 0;
}

/* ── cmd: dump (Q-IR text) ────────────────────────── */
static int cmd_dump(const char *source, size_t len, const char *filepath)
{
    ast_node_t *ast = frontend(filepath, source, len, 0);
    if (!ast) return 1;

    lower_ctx_t *ctx = malloc(sizeof(lower_ctx_t));
    if (!ctx) {
        ast_free(ast);
        return 1;
    }
    lower_init(ctx, "main");

    /* Set up include handler */
    include_ctx_t ictx;
    get_dir(filepath, ictx.base_dir, sizeof(ictx.base_dir));
    ctx->include_reader = vir_include_reader;
    ctx->include_user_data = &ictx;

    if (lower_resolve_includes(ctx, ast) != 0) {
        if (0) {
            diag_render_all(&g_parser_diag);
        } else {
            fprintf(stderr, "include error: %s\n", ctx->last_error);
        }
        ast_free(ast); lower_destroy(ctx); free(ctx);
        return 1;
    }
    if (getenv("VIR_DEBUG_COMPILER")) {
        fprintf(stderr, "[DEBUG] program->child_count = %u\n", ast->child_count);
    }
    for (uint32_t i = 0; i < ast->child_count; i++) {
        if (ast->children[i] && ast->children[i]->name[0] != '\0') {
        }
    }

    if (lower_program(ctx, ast) != 0) {
        if (0) {
            diag_render_all(&g_parser_diag);
        } else {
            fprintf(stderr, "lower error: %s\n", ctx->last_error);
        }
        ast_free(ast);
        lower_destroy(ctx); free(ctx);
        return 1;
    }

    /* Apply TCO pass to all functions */
    for (uint32_t i = 0; i < ctx->module.func_count; i++) {
        lower_tco_pass(&ctx->module.functions[i], i);
    }
    if (pipeline_borrow_check(ctx) != 0) {
        fprintf(stderr, "borrow error: %s\n", ctx->last_error);
        ast_free(ast);
        lower_destroy(ctx); free(ctx);
        return 1;
    }

    size_t dump_cap = 8 * 1024 * 1024;
    char *buf = malloc(dump_cap);
    if (!buf) {
        ast_free(ast);
        lower_destroy(ctx);
        free(ctx);
        return 1;
    }
    q_module_dump(&ctx->module, buf, dump_cap);
    printf("%s", buf);
    free(buf);

    ast_free(ast);
    lower_destroy(ctx);
    free(ctx);
    return 0;
}

/* ── cmd: run (VM interpreter) ────────────────────── */
static int cmd_run(const char *source, size_t len, int verbose,
                   int prog_argc, const char **prog_argv,
                   const char *filepath)
{
    ast_node_t *ast = frontend(filepath, source, len, verbose);
    if (!ast) return 1;

    lower_ctx_t *ctx = malloc(sizeof(lower_ctx_t));
    if (!ctx) {
        ast_free(ast);
        return 1;
    }
    lower_init(ctx, "main");

    /* Set up include handler */
    include_ctx_t ictx;
    get_dir(filepath, ictx.base_dir, sizeof(ictx.base_dir));
    ctx->include_reader = vir_include_reader;
    ctx->include_user_data = &ictx;

    uint64_t phase_start = trace_now_ms();
    trace_stage1_event("include_start", "top_level=%u", ast->child_count);
    int inc_res = lower_resolve_includes(ctx, ast);
    if (inc_res != 0) {
        trace_stage1_event("include_error", "elapsed_phase_ms=%llu error=%s",
                           (unsigned long long)(trace_now_ms() - phase_start),
                           ctx->last_error);
        if (0) {
            diag_render_all(&g_parser_diag);
        } else {
            fprintf(stderr, "include error: %s\n", ctx->last_error);
        }
        ast_free(ast); lower_destroy(ctx); free(ctx);
        return 1;
    }
    trace_stage1_event("include_end",
                       "elapsed_phase_ms=%llu ast_node_count=%llu block_count=%llu top_level=%u",
                       (unsigned long long)(trace_now_ms() - phase_start),
                       (unsigned long long)ast_count_nodes(ast),
                       (unsigned long long)ast_count_blocks(ast),
                       ast->child_count);

    phase_start = trace_now_ms();
    trace_stage1_event("semantic_start", "top_level=%u", ast->child_count);
    if (getenv("VIR_DEBUG_COMPILER")) {
        fprintf(stderr, "[DEBUG] program->child_count = %u\n", ast->child_count);
    }
    for (uint32_t i = 0; i < ast->child_count; i++) {
        if (ast->children[i] && ast->children[i]->name[0] != '\0') {
        }
    }

    int prog_res = lower_program(ctx, ast);
    if (prog_res != 0) {
        trace_stage1_event("semantic_error", "elapsed_phase_ms=%llu error=%s",
                           (unsigned long long)(trace_now_ms() - phase_start),
                           ctx->last_error);
        if (0) {
            diag_render_all(&g_parser_diag);
        } else {
            fprintf(stderr, "lower error: %s\n", ctx->last_error);
        }
        ast_free(ast);
        lower_destroy(ctx); free(ctx);
        return 1;
    }
    trace_stage1_event("semantic_end",
                       "elapsed_phase_ms=%llu function_count=%u block_count=%llu label_count=%llu emitted_instruction_count=%llu",
                       (unsigned long long)(trace_now_ms() - phase_start),
                       ctx->module.func_count,
                       (unsigned long long)ast_count_blocks(ast),
                       (unsigned long long)module_label_count(&ctx->module),
                       (unsigned long long)module_instruction_count(&ctx->module));

    /* TCO pass */
    phase_start = trace_now_ms();
    trace_stage1_event("optimizer_start", "function_count=%u", ctx->module.func_count);
    for (uint32_t i = 0; i < ctx->module.func_count; i++) {
        lower_tco_pass(&ctx->module.functions[i], i);
    }
    trace_stage1_event("optimizer_end",
                       "elapsed_phase_ms=%llu emitted_instruction_count=%llu label_count=%llu",
                       (unsigned long long)(trace_now_ms() - phase_start),
                       (unsigned long long)module_instruction_count(&ctx->module),
                       (unsigned long long)module_label_count(&ctx->module));

    phase_start = trace_now_ms();
    trace_stage1_event("borrow_start", "function_count=%u", ctx->module.func_count);
    if (pipeline_borrow_check(ctx) != 0) {
        trace_stage1_event("borrow_error", "elapsed_phase_ms=%llu error=%s",
                           (unsigned long long)(trace_now_ms() - phase_start),
                           ctx->last_error);
        fprintf(stderr, "borrow error: %s\n", ctx->last_error);
        ast_free(ast);
        lower_destroy(ctx); free(ctx);
        return 1;
    }
    trace_stage1_event("borrow_end", "elapsed_phase_ms=%llu",
                       (unsigned long long)(trace_now_ms() - phase_start));

    if (verbose) {
        fprintf(stderr, "[vir] module '%s': %u functions\n",
                ctx->module.name, ctx->module.func_count);
    }

    /* Execute via VM. vm_state_t is large; keep it off the CLI stack. */
    vm_state_t *vm = calloc(1, sizeof(*vm));
    if (!vm) {
        ast_free(ast);
        lower_destroy(ctx);
        free(ctx);
        return 1;
    }
    phase_start = trace_now_ms();
    trace_stage1_event("vm_init_start", "prog_argc=%d", prog_argc);
    vm_init(vm);
    vm_set_args(vm, prog_argc, prog_argv);
    trace_stage1_event("vm_init_end", "elapsed_phase_ms=%llu",
                       (unsigned long long)(trace_now_ms() - phase_start));

    phase_start = trace_now_ms();
    trace_stage1_event("runtime_execution_start",
                       "function_count=%u emitted_instruction_count=%llu label_count=%llu",
                       ctx->module.func_count,
                       (unsigned long long)module_instruction_count(&ctx->module),
                       (unsigned long long)module_label_count(&ctx->module));
    vm_status_t status = vm_exec_module(vm, &ctx->module);
    trace_stage1_event("runtime_execution_end",
                       "elapsed_phase_ms=%llu status=%s vm_steps=%llu",
                       (unsigned long long)(trace_now_ms() - phase_start),
                       vm_status_str(status),
                       (unsigned long long)vm->instr_executed);

    if (verbose || status != VM_OK) {
        fprintf(stderr, "[vir] VM status: %s  (%llu instrs)\n",
                vm_status_str(status), (unsigned long long)vm->instr_executed);
    }

    int64_t result = vm_get_reg(vm, 0);
    if (status == VM_OK || status == VM_HALT) {
        if (verbose) {
            fprintf(stderr, "[vir] result = %lld\n", (long long)result);
        }
        vm_destroy(vm);
        free(vm);
        ast_free(ast);
        lower_destroy(ctx);
        free(ctx);
        return 0;
    }

    fprintf(stderr, "runtime error: %s\n", vm_status_str(status));
    vm_destroy(vm);
    free(vm);
    ast_free(ast);
    lower_destroy(ctx);
    free(ctx);
    return 1;
}

/* ── cmd: jit (JIT compile + execute) ─────────────── */
static int cmd_jit(const char *source, size_t len, int verbose,
                   const char *filepath)
{
    ast_node_t *ast = frontend(filepath, source, len, verbose);
    if (!ast) return 1;

    lower_ctx_t *ctx = malloc(sizeof(lower_ctx_t));
    if (!ctx) {
        ast_free(ast);
        return 1;
    }
    lower_init(ctx, "main");

    /* Set up include handler */
    include_ctx_t ictx;
    get_dir(filepath, ictx.base_dir, sizeof(ictx.base_dir));
    ctx->include_reader = vir_include_reader;
    ctx->include_user_data = &ictx;

    if (lower_resolve_includes(ctx, ast) != 0) {
        if (0) {
            diag_render_all(&g_parser_diag);
        } else {
            fprintf(stderr, "include error: %s\n", ctx->last_error);
        }
        ast_free(ast); lower_destroy(ctx); free(ctx);
        return 1;
    }
    if (getenv("VIR_DEBUG_COMPILER")) {
        fprintf(stderr, "[DEBUG] program->child_count = %u\n", ast->child_count);
    }
    for (uint32_t i = 0; i < ast->child_count; i++) {
        if (ast->children[i] && ast->children[i]->name[0] != '\0') {
        }
    }

    if (lower_program(ctx, ast) != 0) {
        if (0) {
            diag_render_all(&g_parser_diag);
        } else {
            fprintf(stderr, "lower error: %s\n", ctx->last_error);
        }
        ast_free(ast);
        lower_destroy(ctx); free(ctx);
        return 1;
    }

    /* TCO pass */
    for (uint32_t i = 0; i < ctx->module.func_count; i++) {
        lower_tco_pass(&ctx->module.functions[i], i);
    }
    if (pipeline_borrow_check(ctx) != 0) {
        fprintf(stderr, "borrow error: %s\n", ctx->last_error);
        ast_free(ast);
        lower_destroy(ctx); free(ctx);
        return 1;
    }

    /* Detect target architecture */
#if defined(__aarch64__) || defined(__arm64__)
    target_arch_t arch = ARCH_ARM64;
#elif defined(__x86_64__) || defined(_M_X64)
    target_arch_t arch = ARCH_X86_64;
#else
    fprintf(stderr, "error: unsupported architecture for JIT\n");
    ast_free(ast); lower_destroy(ctx); free(ctx);
    return 1;
#endif

    /* Initialize JIT bridge */
    jit_bridge_t *jb = jit_bridge_global();
    if (!jb || !jb->initialised) {
        fprintf(stderr, "error: JIT bridge init failed\n");
        ast_free(ast); lower_destroy(ctx); free(ctx);
        return 1;
    }

    /* Register intrinsics */
    jit_bridge_register_intrinsics(jb);

    /* Resolve print function address */
    void *print_fn = (void *)(uintptr_t)vir_builtin_print_i64;

    /* Generate code for first / main function */
    q_function_t *main_func = NULL;
    for (uint32_t i = 0; i < ctx->module.func_count; i++) {
        if (strcmp(ctx->module.functions[i].name, "__main__") == 0 ||
            strcmp(ctx->module.functions[i].name, "main") == 0 ||
            strcmp(ctx->module.functions[i].name, "chính") == 0 ||
            i == 0) {
            main_func = &ctx->module.functions[i];
            break;
        }
    }
    if (!main_func) {
        fprintf(stderr, "error: no main function found\n");
        ast_free(ast); lower_destroy(ctx); free(ctx);
        return 1;
    }

    if (verbose) {
        fprintf(stderr, "[vir] JIT: compiling '%s' (%u instrs, %s)\n",
                main_func->name, main_func->body_count,
                arch == ARCH_ARM64 ? "ARM64" : "x86_64");
    }

    /* Generate machine code */
    codebuf_t cb;
    codebuf_init(&cb, 4096);
    codegen_emit_full(&cb, main_func->body, main_func->body_count,
                      arch, print_fn);

    if (verbose) {
        fprintf(stderr, "[vir] JIT: %zu bytes of machine code\n", cb.len);
    }

    /* Emit into JIT region */
    jit_bridge_begin_patch(jb);
    int blk = jit_bridge_emit_code(jb, 0, cb.data, cb.len);
    jit_bridge_finalise(jb);
    codebuf_free(&cb);

    if (blk < 0) {
        fprintf(stderr, "error: JIT emit failed\n");
        ast_free(ast); lower_destroy(ctx); free(ctx);
        return 1;
    }

    /* Execute */
    jit_entry_fn entry = jit_bridge_get_entry(jb, 0);
    if (!entry) {
        fprintf(stderr, "error: no JIT entry point\n");
        ast_free(ast); lower_destroy(ctx); free(ctx);
        return 1;
    }

    int64_t result = entry(0, 0);

    if (verbose) {
        fprintf(stderr, "[vir] JIT result = %lld\n", (long long)result);
    }

    ast_free(ast);
    lower_destroy(ctx);
    free(ctx);
    return 0;
}

/* ── Usage ────────────────────────────────────────── */
static void usage(const char *prog)
{
    fprintf(stderr,
        "Vir – Ngôn ngữ lập trình Việt Nam\n"
        "Usage: %s <command> [options] <file.vri>\n\n"
        "Commands:\n"
        "  run    <file>   Interpret via Q-IR VM\n"
        "  jit    <file>   JIT compile and execute\n"
        "  dump   <file>   Print Q-IR text\n"
        "  tokens <file>   Print token stream\n"
        "  build  <file>   Emit object for --target (wasm32)\n"
        "  help            Show this message\n\n"
        "  -v              Verbose output\n"
        "  --debug         Enable internal compiler debug logs\n"
        "  --target=T      Compile target for 'build' (wasm32)\n"
        "  --json          Output diagnostics in JSON format\n"
        "  --report=E0000  Show full Execution Report for a specific error\n",
        prog);
}

/* ── main ─────────────────────────────────────────── */

int main(int argc, char **argv)
{
    trace_stage1_init();
    trace_stage1_event("process_start", "argc=%d", argc);

    /* Initialize Diagnostics */
    diag_init(&g_parser_diag, STAGE_0_C_CORE, DIAG_FMT_TERMINAL);
    g_diag_initialized = 1;

    /* §28 — Register all CJK and Vietnamese keyword aliases at startup */
    // vir_sublib_adapter_init();

    if (argc < 2) {
        usage(argv[0]);
        trace_stage1_event("process_end", "rc=1 reason=no_command");
        trace_stage1_close();
        return 1;
    }

    const char *cmd = argv[1];

    if (strcmp(cmd, "help") == 0 || strcmp(cmd, "--help") == 0 ||
        strcmp(cmd, "-h") == 0) {
        usage(argv[0]);
        trace_stage1_event("process_end", "rc=0 reason=help");
        trace_stage1_close();
        return 0;
    }

    /* Parse options */
    int verbose = 0;
    const char *filepath = NULL;
    const char *target = NULL;          /* §15.3 — optional compile target */
    int prog_argc = 0;
    const char *prog_argv[64] = {0};
    for (int i = 2; i < argc; i++) {
        if (strcmp(argv[i], "-v") == 0)
            verbose = 1;
        else if (strcmp(argv[i], "--debug") == 0) {
            setenv("VIR_DEBUG_COMPILER", "1", 1);
        }
        else if (strcmp(argv[i], "--json") == 0)
            g_parser_diag.format = DIAG_FMT_JSON;
        else if (strncmp(argv[i], "--target=", 9) == 0)
            target = argv[i] + 9;
        else if (strcmp(argv[i], "--target") == 0 && i + 1 < argc)
            target = argv[++i];
        else if (strncmp(argv[i], "--report=", 9) == 0) {
            const char *val = argv[i] + 9;
            if (val[0] == 'E' || val[0] == 'W') val++;
            g_parser_diag.report_code = (uint32_t)atoi(val);
        }
        else if (strcmp(argv[i], "--report") == 0 && i + 1 < argc) {
            const char *val = argv[++i];
            if (val[0] == 'E' || val[0] == 'W') val++;
            g_parser_diag.report_code = (uint32_t)atoi(val);
        }
        else if (strcmp(argv[i], "--") == 0) {
            for (i++; i < argc && prog_argc < 64; i++)
                prog_argv[prog_argc++] = argv[i];
            break;
        }
        else if (!filepath) {
            filepath = argv[i];
            /* Don't add filepath itself to prog_argv — extra args start after it */
        }
        else if (prog_argc < 64)
            prog_argv[prog_argc++] = argv[i];
    }

    if (!filepath) {
        fprintf(stderr, "error: no input file\n");
        usage(argv[0]);
        trace_stage1_event("process_end", "rc=1 reason=no_input");
        trace_stage1_close();
        return 1;
    }

    /* Read source file */
    size_t src_len = 0;
    uint64_t phase_start = trace_now_ms();
    trace_stage1_event("read_start", "file=%s", filepath);
    char *source = read_source(filepath, &src_len);
    if (!source) {
        trace_stage1_event("read_error", "elapsed_phase_ms=%llu file=%s",
                           (unsigned long long)(trace_now_ms() - phase_start),
                           filepath);
        trace_stage1_event("process_end", "rc=1 reason=read_error");
        trace_stage1_close();
        return 1;
    }
    trace_stage1_event("read_end", "elapsed_phase_ms=%llu bytes=%zu",
                       (unsigned long long)(trace_now_ms() - phase_start), src_len);

    /* §15.3 WASM target — compile source → Q-IR → WASM binary */
    if (strcmp(cmd, "build") == 0 && target &&
        (strcmp(target, "wasm32") == 0 || strcmp(target, "wasm") == 0)) {
        const char *outpath = "out.wasm";

        /* Step 1: Parse + lower to Q-IR */
        ast_node_t *ast = frontend(filepath, source, src_len, verbose);
        if (!ast) {
            free(source);
            trace_stage1_event("process_end", "rc=1 reason=wasm_frontend_error");
            trace_stage1_close();
            return 1;
        }

        lower_ctx_t *ctx = malloc(sizeof(lower_ctx_t));
        if (!ctx) {
            ast_free(ast); free(source);
            trace_stage1_event("process_end", "rc=1 reason=wasm_alloc_error");
            trace_stage1_close();
            return 1;
        }
        lower_init(ctx, "main");
        include_ctx_t ictx;
        get_dir(filepath, ictx.base_dir, sizeof(ictx.base_dir));
        ctx->include_reader    = vir_include_reader;
        ctx->include_user_data = &ictx;

        if (lower_resolve_includes(ctx, ast) != 0 ||
            lower_program(ctx, ast) != 0) {
            if (0) {
                diag_render_all(&g_parser_diag);
            } else {
                fprintf(stderr, "lower error: %s\n", ctx->last_error);
            }
            ast_free(ast); lower_destroy(ctx); free(ctx); free(source);
            trace_stage1_event("process_end", "rc=1 reason=wasm_lower_error");
            trace_stage1_close();
            return 1;
        }
        for (uint32_t i = 0; i < ctx->module.func_count; i++)
            lower_tco_pass(&ctx->module.functions[i], i);
        if (pipeline_borrow_check(ctx) != 0) {
            fprintf(stderr, "borrow error: %s\n", ctx->last_error);
            ast_free(ast); lower_destroy(ctx); free(ctx); free(source);
            trace_stage1_event("process_end", "rc=1 reason=wasm_borrow_error");
            trace_stage1_close();
            return 1;
        }

        /* Step 2: Emit WASM binary via codegen */
        uint8_t *wasm_buf = NULL;
        size_t   wasm_len = 0;
        int wasm_rc = codegen_emit_wasm(&ctx->module, &wasm_buf, &wasm_len);

        ast_free(ast);
        lower_destroy(ctx);
        free(ctx);

        if (wasm_rc != 0 || !wasm_buf) {
            fprintf(stderr, "wasm codegen error\n");
            free(source);
            trace_stage1_event("process_end", "rc=1 reason=wasm_codegen_error");
            trace_stage1_close();
            return 1;
        }

        /* Step 3: Write output */
        FILE *f = fopen(outpath, "wb");
        if (!f) {
            fprintf(stderr, "error: cannot write %s\n", outpath);
            free(wasm_buf); free(source);
            trace_stage1_event("process_end", "rc=1 reason=wasm_write_error");
            trace_stage1_close();
            return 1;
        }
        fwrite(wasm_buf, 1, wasm_len, f);
        fclose(f);
        free(wasm_buf);

        if (verbose)
            fprintf(stderr, "[vir] wrote wasm32 module → %s (%zu bytes)\n",
                    outpath, wasm_len);
        free(source);
        trace_stage1_event("process_end", "rc=0 reason=wasm_build");
        trace_stage1_close();
        return 0;
    }

    int rc = 1;
    if (strcmp(cmd, "tokens") == 0)
        rc = cmd_tokens(source, src_len);
    else if (strcmp(cmd, "dump") == 0)
        rc = cmd_dump(source, src_len, filepath);
    else if (strcmp(cmd, "run") == 0)
        rc = cmd_run(source, src_len, verbose, prog_argc, prog_argv, filepath);
    else if (strcmp(cmd, "jit") == 0)
        rc = cmd_jit(source, src_len, verbose, filepath);
    else {
        fprintf(stderr, "error: unknown command '%s'\n", cmd);
        usage(argv[0]);
    }

    free(source);
    trace_stage1_event("process_end", "rc=%d last_phase=%s", rc,
                       g_stage1_trace.last_phase ? g_stage1_trace.last_phase : "");
    trace_stage1_close();
    return rc;
}
