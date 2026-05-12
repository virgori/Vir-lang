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
#include "vm.h"
#include "codegen.h"
#include "jit_bridge.h"
#include "intrinsics.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

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

    /* 5) Fallback: cwd-relative (either translated or verbatim). */
    if ((src = read_source_silent(relpath, out_len))) return src;
    return read_source(filename, out_len);  /* noisy: prints cannot-open */
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
static ast_node_t *frontend(const char *source, size_t len, int verbose)
{
    /* Tokenize */
    vir_lexer_t lex;
    lexer_init(&lex, source, len);
    if (lexer_tokenize(&lex) != 0) {
        fprintf(stderr, "lexer error: %s\n", lex.error);
        lexer_free(&lex);
        return NULL;
    }
    if (verbose) {
        fprintf(stderr, "[vir] %u tokens\n", lex.token_count);
    }

    /* Parse → AST */
    vir_parser_t parser;
    parser_init(&parser, lex.tokens, lex.token_count);
    ast_node_t *ast = parser_parse_program(&parser);
    lexer_free(&lex);
    if (!ast) {
        fprintf(stderr, "parse error (line %u): %s\n",
                parser.error_line, parser.error);
        return NULL;
    }
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
    ast_node_t *ast = frontend(source, len, 0);
    if (!ast) return 1;

    lower_ctx_t ctx;
    lower_init(&ctx, "main");

    /* Set up include handler */
    include_ctx_t ictx;
    get_dir(filepath, ictx.base_dir, sizeof(ictx.base_dir));
    ctx.include_reader = vir_include_reader;
    ctx.include_user_data = &ictx;

    if (lower_resolve_includes(&ctx, ast) != 0) {
        fprintf(stderr, "include error: %s\n", ctx.last_error);
        ast_free(ast); lower_destroy(&ctx);
        return 1;
    }
    if (lower_program(&ctx, ast) != 0) {
        fprintf(stderr, "lower error: %s\n", ctx.last_error);
        ast_free(ast);
        lower_destroy(&ctx);
        return 1;
    }

    /* Apply TCO pass to all functions */
    for (uint32_t i = 0; i < ctx.module.func_count; i++) {
        lower_tco_pass(&ctx.module.functions[i], i);
    }

    char buf[16384];
    q_module_dump(&ctx.module, buf, sizeof(buf));
    printf("%s", buf);

    ast_free(ast);
    lower_destroy(&ctx);
    return 0;
}

/* ── cmd: run (VM interpreter) ────────────────────── */
static int cmd_run(const char *source, size_t len, int verbose,
                   int prog_argc, const char **prog_argv,
                   const char *filepath)
{
    ast_node_t *ast = frontend(source, len, verbose);
    if (!ast) return 1;

    lower_ctx_t ctx;
    lower_init(&ctx, "main");

    /* Set up include handler */
    include_ctx_t ictx;
    get_dir(filepath, ictx.base_dir, sizeof(ictx.base_dir));
    ctx.include_reader = vir_include_reader;
    ctx.include_user_data = &ictx;

    if (lower_resolve_includes(&ctx, ast) != 0) {
        fprintf(stderr, "include error: %s\n", ctx.last_error);
        ast_free(ast); lower_destroy(&ctx);
        return 1;
    }
    if (lower_program(&ctx, ast) != 0) {
        fprintf(stderr, "lower error: %s\n", ctx.last_error);
        ast_free(ast);
        lower_destroy(&ctx);
        return 1;
    }

    /* TCO pass */
    for (uint32_t i = 0; i < ctx.module.func_count; i++) {
        lower_tco_pass(&ctx.module.functions[i], i);
    }

    if (verbose) {
        fprintf(stderr, "[vir] module '%s': %u functions\n",
                ctx.module.name, ctx.module.func_count);
    }

    /* Execute via VM */
    vm_state_t vm;
    vm_init(&vm);
    vm_set_args(&vm, prog_argc, prog_argv);
    vm_status_t status = vm_exec_module(&vm, &ctx.module);

    if (verbose) {
        fprintf(stderr, "[vir] VM status: %s  (%llu instrs)\n",
                vm_status_str(status), (unsigned long long)vm.instr_executed);
    }

    int64_t result = vm_get_reg(&vm, 0);
    if (status == VM_OK || status == VM_HALT) {
        if (verbose) {
            fprintf(stderr, "[vir] result = %lld\n", (long long)result);
        }
        vm_destroy(&vm);
        ast_free(ast);
        lower_destroy(&ctx);
        return 0;
    }

    fprintf(stderr, "runtime error: %s\n", vm_status_str(status));
    vm_destroy(&vm);
    ast_free(ast);
    lower_destroy(&ctx);
    return 1;
}

/* ── cmd: jit (JIT compile + execute) ─────────────── */
static int cmd_jit(const char *source, size_t len, int verbose,
                   const char *filepath)
{
    ast_node_t *ast = frontend(source, len, verbose);
    if (!ast) return 1;

    lower_ctx_t ctx;
    lower_init(&ctx, "main");

    /* Set up include handler */
    include_ctx_t ictx;
    get_dir(filepath, ictx.base_dir, sizeof(ictx.base_dir));
    ctx.include_reader = vir_include_reader;
    ctx.include_user_data = &ictx;

    if (lower_resolve_includes(&ctx, ast) != 0) {
        fprintf(stderr, "include error: %s\n", ctx.last_error);
        ast_free(ast); lower_destroy(&ctx);
        return 1;
    }
    if (lower_program(&ctx, ast) != 0) {
        fprintf(stderr, "lower error: %s\n", ctx.last_error);
        ast_free(ast);
        lower_destroy(&ctx);
        return 1;
    }

    /* TCO pass */
    for (uint32_t i = 0; i < ctx.module.func_count; i++) {
        lower_tco_pass(&ctx.module.functions[i], i);
    }

    /* Detect target architecture */
#if defined(__aarch64__) || defined(__arm64__)
    target_arch_t arch = ARCH_ARM64;
#elif defined(__x86_64__) || defined(_M_X64)
    target_arch_t arch = ARCH_X86_64;
#else
    fprintf(stderr, "error: unsupported architecture for JIT\n");
    ast_free(ast); lower_destroy(&ctx);
    return 1;
#endif

    /* Initialize JIT bridge */
    jit_bridge_t *jb = jit_bridge_global();
    if (!jb || !jb->initialised) {
        fprintf(stderr, "error: JIT bridge init failed\n");
        ast_free(ast); lower_destroy(&ctx);
        return 1;
    }

    /* Register intrinsics */
    jit_bridge_register_intrinsics(jb);

    /* Resolve print function address */
    void *print_fn = (void *)(uintptr_t)vir_builtin_print_i64;

    /* Generate code for first / main function */
    q_function_t *main_func = NULL;
    for (uint32_t i = 0; i < ctx.module.func_count; i++) {
        if (strcmp(ctx.module.functions[i].name, "__main__") == 0 ||
            strcmp(ctx.module.functions[i].name, "main") == 0 ||
            strcmp(ctx.module.functions[i].name, "chính") == 0 ||
            i == 0) {
            main_func = &ctx.module.functions[i];
            break;
        }
    }
    if (!main_func) {
        fprintf(stderr, "error: no main function found\n");
        ast_free(ast); lower_destroy(&ctx);
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
        ast_free(ast); lower_destroy(&ctx);
        return 1;
    }

    /* Execute */
    jit_entry_fn entry = jit_bridge_get_entry(jb, 0);
    if (!entry) {
        fprintf(stderr, "error: no JIT entry point\n");
        ast_free(ast); lower_destroy(&ctx);
        return 1;
    }

    int64_t result = entry(0, 0);

    if (verbose) {
        fprintf(stderr, "[vir] JIT result = %lld\n", (long long)result);
    }

    ast_free(ast);
    lower_destroy(&ctx);
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
        "Options:\n"
        "  -v              Verbose output\n"
        "  --target=T      Compile target for 'build' (wasm32)\n",
        prog);
}

/* ── main ─────────────────────────────────────────── */
int main(int argc, char **argv)
{
    /* §28 — Register all CJK and Vietnamese keyword aliases at startup */
    vir_sublib_adapter_init();

    if (argc < 2) {
        usage(argv[0]);
        return 1;
    }

    const char *cmd = argv[1];

    if (strcmp(cmd, "help") == 0 || strcmp(cmd, "--help") == 0 ||
        strcmp(cmd, "-h") == 0) {
        usage(argv[0]);
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
        else if (strncmp(argv[i], "--target=", 9) == 0)
            target = argv[i] + 9;
        else if (strcmp(argv[i], "--target") == 0 && i + 1 < argc)
            target = argv[++i];
        else if (!filepath)
            filepath = argv[i];
        else if (prog_argc < 64)
            prog_argv[prog_argc++] = argv[i];
    }

    if (!filepath) {
        fprintf(stderr, "error: no input file\n");
        usage(argv[0]);
        return 1;
    }

    /* Read source file */
    size_t src_len = 0;
    char *source = read_source(filepath, &src_len);
    if (!source) return 1;

    /* §15.3 WASM target — compile source → Q-IR → WASM binary */
    if (strcmp(cmd, "build") == 0 && target &&
        (strcmp(target, "wasm32") == 0 || strcmp(target, "wasm") == 0)) {
        const char *outpath = "out.wasm";

        /* Step 1: Parse + lower to Q-IR */
        ast_node_t *ast = frontend(source, src_len, verbose);
        if (!ast) { free(source); return 1; }

        lower_ctx_t ctx;
        lower_init(&ctx, "main");
        include_ctx_t ictx;
        get_dir(filepath, ictx.base_dir, sizeof(ictx.base_dir));
        ctx.include_reader    = vir_include_reader;
        ctx.include_user_data = &ictx;

        if (lower_resolve_includes(&ctx, ast) != 0 ||
            lower_program(&ctx, ast) != 0) {
            fprintf(stderr, "lower error: %s\n", ctx.last_error);
            ast_free(ast); lower_destroy(&ctx); free(source);
            return 1;
        }
        for (uint32_t i = 0; i < ctx.module.func_count; i++)
            lower_tco_pass(&ctx.module.functions[i], i);

        /* Step 2: Emit WASM binary via codegen */
        uint8_t *wasm_buf = NULL;
        size_t   wasm_len = 0;
        int wasm_rc = codegen_emit_wasm(&ctx.module, &wasm_buf, &wasm_len);

        ast_free(ast);
        lower_destroy(&ctx);

        if (wasm_rc != 0 || !wasm_buf) {
            fprintf(stderr, "wasm codegen error\n");
            free(source);
            return 1;
        }

        /* Step 3: Write output */
        FILE *f = fopen(outpath, "wb");
        if (!f) {
            fprintf(stderr, "error: cannot write %s\n", outpath);
            free(wasm_buf); free(source);
            return 1;
        }
        fwrite(wasm_buf, 1, wasm_len, f);
        fclose(f);
        free(wasm_buf);

        if (verbose)
            fprintf(stderr, "[vir] wrote wasm32 module → %s (%zu bytes)\n",
                    outpath, wasm_len);
        free(source);
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
    return rc;
}
