/*
 * test_native.c – Native Core Unit Tests
 * ═══════════════════════════════════════════
 * Tests SHA-256, HMAC, Q-IR, VM, Codegen, Bridge.
 */

#include "vir.h"
#include "q_ir.h"
#include "vm.h"
#include "codegen.h"
#include "bridge.h"
#include "signer.h"
#include "constraints.h"
#include "intrinsics.h"
#include "jit_bridge.h"
#include "ir_lower.h"
#include "lexer.h"
#include "parser.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>

static int tests_run    = 0;
static int tests_passed = 0;

#define TEST(name)  do { \
    tests_run++; \
    printf("  [%d] %-40s ", tests_run, name); \
} while(0)

#define PASS() do { tests_passed++; printf("✓ PASS\n"); } while(0)
#define FAIL(msg) do { printf("✗ FAIL: %s\n", msg); } while(0)

/* ═══════════════════════════════════════════════════════
 * SHA-256 Tests (NIST test vectors)
 * ═══════════════════════════════════════════════════════ */

static void test_sha256_empty(void)
{
    TEST("sha256(\"\")");
    uint8_t digest[32];
    sha256_hash("", 0, digest);

    /* Expected: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 */
    uint8_t expected[32] = {
        0xe3,0xb0,0xc4,0x42,0x98,0xfc,0x1c,0x14,
        0x9a,0xfb,0xf4,0xc8,0x99,0x6f,0xb9,0x24,
        0x27,0xae,0x41,0xe4,0x64,0x9b,0x93,0x4c,
        0xa4,0x95,0x99,0x1b,0x78,0x52,0xb8,0x55
    };

    if (memcmp(digest, expected, 32) == 0) PASS();
    else FAIL("hash mismatch");
}

static void test_sha256_abc(void)
{
    TEST("sha256(\"abc\")");
    uint8_t digest[32];
    sha256_hash("abc", 3, digest);

    /* Expected: ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad */
    uint8_t expected[32] = {
        0xba,0x78,0x16,0xbf,0x8f,0x01,0xcf,0xea,
        0x41,0x41,0x40,0xde,0x5d,0xae,0x22,0x23,
        0xb0,0x03,0x61,0xa3,0x96,0x17,0x7a,0x9c,
        0xb4,0x10,0xff,0x61,0xf2,0x00,0x15,0xad
    };

    if (memcmp(digest, expected, 32) == 0) PASS();
    else FAIL("hash mismatch");
}

static void test_hmac_sha256(void)
{
    TEST("hmac_sha256(key, data)");
    uint8_t mac[32];
    hmac_sha256((const uint8_t *)"key", 3, "The quick brown fox jumps over the lazy dog", 43, mac);

    /* Known HMAC-SHA256 for this key/data pair */
    /* Expected: f7bc83f430538424b13298e6aa6fb143ef4d59a14946175997479dbc2d1a3cd8 */
    uint8_t expected[32] = {
        0xf7,0xbc,0x83,0xf4,0x30,0x53,0x84,0x24,
        0xb1,0x32,0x98,0xe6,0xaa,0x6f,0xb1,0x43,
        0xef,0x4d,0x59,0xa1,0x49,0x46,0x17,0x59,
        0x97,0x47,0x9d,0xbc,0x2d,0x1a,0x3c,0xd8
    };

    if (memcmp(mac, expected, 32) == 0) PASS();
    else FAIL("hmac mismatch");
}

/* ═══════════════════════════════════════════════════════
 * Signer Tests
 * ═══════════════════════════════════════════════════════ */

static void test_signer_sign_verify(void)
{
    TEST("signer sign + verify");
    signer_t s;
    uint8_t key[HMAC_KEY_SIZE] = {
        0x51,0x75,0x69,0x7A,0x7A,0x2D,0x43,0x6F,
        0x72,0x65,0x2D,0x4B,0x65,0x79,0x00,0x00,
        0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,
        0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00
    };
    signer_init(&s, key);

    uint8_t code[] = { 0x48, 0x01, 0xD8, 0xC3 };  /* ADD RAX,RBX; RET */
    signer_sign(&s, 1, code, sizeof(code));

    int ok = signer_verify(&s, 1, code, sizeof(code));
    if (ok == 0) PASS();
    else FAIL("verification failed");
}

static void test_signer_tamper_detect(void)
{
    TEST("signer tamper detection");
    signer_t s;
    uint8_t key[HMAC_KEY_SIZE] = {
        0x51,0x75,0x69,0x7A,0x7A,0x2D,0x43,0x6F,
        0x72,0x65,0x2D,0x4B,0x65,0x79,0x00,0x00,
        0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,
        0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00
    };
    signer_init(&s, key);

    uint8_t code[] = { 0x48, 0x01, 0xD8, 0xC3 };
    signer_sign(&s, 2, code, sizeof(code));

    /* Tamper with code */
    code[0] = 0xFF;
    int ok = signer_verify(&s, 2, code, sizeof(code));
    if (ok != 0) PASS();
    else FAIL("should detect tamper");
}

/* ═══════════════════════════════════════════════════════
 * Q-IR Tests
 * ═══════════════════════════════════════════════════════ */

static void test_qir_create_module(void)
{
    TEST("Q-IR module creation");
    q_module_t mod;
    q_module_init(&mod, "test_module");

    q_function_t *func = q_module_add_func(&mod, "main");

    q_vreg_alloc_t alloc;
    q_vreg_alloc_init(&alloc);
    uint32_t r0 = q_vreg_alloc_next(&alloc);
    uint32_t r1 = q_vreg_alloc_next(&alloc);
    uint32_t r2 = q_vreg_alloc_next(&alloc);

    q_func_emit(func, q_instr(Q_LOAD, q_vreg(r0), q_imm(42), q_none()));
    q_func_emit(func, q_instr(Q_LOAD, q_vreg(r1), q_imm(58), q_none()));
    q_func_emit(func, q_instr(Q_ADD,  q_vreg(r2), q_vreg(r0), q_vreg(r1)));
    q_func_emit(func, q_instr(Q_RET,  q_none(),   q_vreg(r2), q_none()));

    if (mod.func_count == 1 && func->body_count == 4) PASS();
    else FAIL("wrong instruction count");

    q_module_free(&mod);
}

/* ═══════════════════════════════════════════════════════
 * VM Tests
 * ═══════════════════════════════════════════════════════ */

static void test_vm_arithmetic(void)
{
    TEST("VM arithmetic (42 + 58 = 100)");
    q_function_t func;
    q_func_init(&func, "add_test");

    q_func_emit(&func, q_instr(Q_LOAD, q_vreg(0), q_imm(42), q_none()));
    q_func_emit(&func, q_instr(Q_LOAD, q_vreg(1), q_imm(58), q_none()));
    q_func_emit(&func, q_instr(Q_ADD,  q_vreg(2), q_vreg(0), q_vreg(1)));
    q_func_emit(&func, q_instr(Q_RET,  q_none(),  q_vreg(2), q_none()));

    vm_state_t vm;
    vm_init(&vm);
    vm_status_t status = vm_exec_function(&vm, &func);
    int64_t result = vm_get_reg(&vm, 2);

    if (status >= 0 && result == 100) PASS();
    else FAIL("expected 100");

    q_func_free(&func);
}

static void test_vm_multiply(void)
{
    TEST("VM multiply (7 * 6 = 42)");
    q_function_t func;
    q_func_init(&func, "mul_test");

    q_func_emit(&func, q_instr(Q_LOAD, q_vreg(0), q_imm(7), q_none()));
    q_func_emit(&func, q_instr(Q_LOAD, q_vreg(1), q_imm(6), q_none()));
    q_func_emit(&func, q_instr(Q_MUL,  q_vreg(2), q_vreg(0), q_vreg(1)));
    q_func_emit(&func, q_instr(Q_RET,  q_none(),  q_vreg(2), q_none()));

    vm_state_t vm;
    vm_init(&vm);
    vm_status_t status = vm_exec_function(&vm, &func);
    int64_t result = vm_get_reg(&vm, 2);

    if (status >= 0 && result == 42) PASS();
    else FAIL("expected 42");

    q_func_free(&func);
}

/* ═══════════════════════════════════════════════════════
 * Codegen Tests
 * ═══════════════════════════════════════════════════════ */

static void test_codegen_buffer(void)
{
    TEST("codebuf emit + hexdump");
    codebuf_t cb;
    codebuf_init(&cb, ARCH_X86_64);

    x86_emit_nop(&cb);
    x86_emit_ret(&cb);

    if (cb.len == 2 && cb.data[0] == 0x90 && cb.data[1] == 0xC3) PASS();
    else FAIL("unexpected bytes");

    codebuf_free(&cb);
}

static void test_codegen_x86_add(void)
{
    TEST("x86 ADD RAX, RBX encoding");
    codebuf_t cb;
    codebuf_init(&cb, ARCH_X86_64);

    x86_emit_add_rr(&cb, X86_RAX, X86_RBX);

    /* ADD RAX, RBX = 48 01 D8 */
    if (cb.len == 3 && cb.data[0] == 0x48 && cb.data[1] == 0x01 && cb.data[2] == 0xD8)
        PASS();
    else {
        char hex[64];
        codebuf_hexdump(&cb, hex, sizeof(hex));
        printf("✗ FAIL: got %s\n", hex);
    }

    codebuf_free(&cb);
}

static void test_codegen_arm64_add(void)
{
    TEST("arm64 ADD X0, X1, X2 encoding");
    codebuf_t cb;
    codebuf_init(&cb, ARCH_ARM64);

    arm64_emit_add_rrr(&cb, ARM_X0, ARM_X1, ARM_X2);

    /* ADD X0, X1, X2 = 0x8B020020 */
    uint32_t instr;
    memcpy(&instr, cb.data, 4);
    if (cb.len == 4 && instr == 0x8B020020) PASS();
    else {
        printf("✗ FAIL: got 0x%08X\n", instr);
    }

    codebuf_free(&cb);
}

/* ═══════════════════════════════════════════════════════
 * Bridge Tests
 * ═══════════════════════════════════════════════════════ */

static void test_bridge_detect_os(void)
{
    TEST("bridge OS detection");
    os_type_t os = bridge_detect_os();
#if defined(__APPLE__)
    if (os == OS_MACOS) PASS();
    else FAIL("expected macOS");
#elif defined(__linux__)
    if (os == OS_LINUX) PASS();
    else FAIL("expected Linux");
#else
    PASS();  /* any result is fine */
#endif
}

static void test_bridge_jit_alloc(void)
{
    TEST("bridge JIT alloc/free");
    void *ptr = bridge_jit_alloc(4096);
    if (ptr != NULL) {
        bridge_jit_free(ptr, 4096);
        PASS();
    } else {
        FAIL("alloc returned NULL");
    }
}

static void test_bridge_cpu_probe(void)
{
    TEST("bridge CPU probe");
    cpu_state_t state;
    int rc = bridge_probe_cpu(&state);
    if (rc == 0 && state.total_gp_regs > 0) PASS();
    else FAIL("probe failed");
}

/* ═══════════════════════════════════════════════════════
 * Constraints Tests
 * ═══════════════════════════════════════════════════════ */

static void test_constraints_type_get(void)
{
    TEST("constraints type_get I64");
    const vir_type_info_t *info = vir_type_get(VIR_TYPE_I64);
    if (info && info->size == 8 && info->is_int == 1 && info->is_float == 0)
        PASS();
    else FAIL("bad I64 type info");
}

static void test_constraints_type_size(void)
{
    TEST("constraints type sizes");
    int ok = (vir_type_size(VIR_TYPE_VOID) == 0 &&
              vir_type_size(VIR_TYPE_I8)   == 1 &&
              vir_type_size(VIR_TYPE_I32)  == 4 &&
              vir_type_size(VIR_TYPE_I64)  == 8 &&
              vir_type_size(VIR_TYPE_F32)  == 4 &&
              vir_type_size(VIR_TYPE_F64)  == 8 &&
              vir_type_size(VIR_TYPE_PTR)  == 8);
    if (ok) PASS();
    else FAIL("type size mismatch");
}

static void test_constraints_op_add(void)
{
    TEST("constraints op Q_ADD");
    const op_constraint_t *c = vir_op_constraint(Q_ADD);
    if (c && c->operand_count == 3 && c->dest_type == VIR_TYPE_I64)
        PASS();
    else FAIL("bad ADD constraint");
}

static void test_constraints_check_pass(void)
{
    TEST("constraints check valid ADD");
    int rc = vir_constraint_check(Q_ADD, VIR_TYPE_I64,
                                  VIR_TYPE_I64, VIR_TYPE_I64);
    if (rc == 0) PASS();
    else FAIL("should pass");
}

/* ═══════════════════════════════════════════════════════
 * Intrinsics Tests
 * ═══════════════════════════════════════════════════════ */

static void test_intrinsics_table_init(void)
{
    TEST("intrinsics table init");
    intrinsic_table_t *t = vir_intrinsics();
    if (t && t->initialised)
        PASS();
    else FAIL("table not initialised");
}

static void test_intrinsics_get_print(void)
{
    TEST("intrinsics get PRINT");
    const intrinsic_desc_t *d = vir_intrinsic_get(INTRINSIC_PRINT);
    if (d && d->func_ptr != NULL && d->arg_count == 1)
        PASS();
    else FAIL("bad PRINT descriptor");
}

static void test_intrinsics_addr(void)
{
    TEST("intrinsics addr non-null");
    void *addr = vir_intrinsic_addr(INTRINSIC_CPU_LOAD);
    if (addr != NULL) PASS();
    else FAIL("CPU_LOAD addr is NULL");
}

static void test_intrinsics_opcode_map(void)
{
    TEST("intrinsics opcode→intrinsic");
    int id_print = vir_opcode_to_intrinsic(Q_PRINT);
    int id_input = vir_opcode_to_intrinsic(Q_INPUT);
    int id_add   = vir_opcode_to_intrinsic(Q_ADD);
    if (id_print == INTRINSIC_PRINT && id_input == INTRINSIC_INPUT && id_add == -1)
        PASS();
    else FAIL("opcode mapping wrong");
}

/* ═══════════════════════════════════════════════════════
 * JIT Bridge Tests
 * ═══════════════════════════════════════════════════════ */

static void test_jit_bridge_init_destroy(void)
{
    TEST("jit_bridge init + destroy");
    jit_bridge_t jb;
    int rc = jit_bridge_init(&jb, 4096);
    if (rc == 0 && jb.initialised && jb.region_base != NULL) {
        jit_bridge_destroy(&jb);
        PASS();
    } else {
        FAIL("init failed");
    }
}

static void test_jit_bridge_register_callback(void)
{
    TEST("jit_bridge register callback");
    jit_bridge_t jb;
    jit_bridge_init(&jb, 4096);

    /* Register a dummy callback */
    int slot = jit_bridge_register(&jb, "test_cb",
                                   (void *)vir_builtin_print_i64,
                                   1, VIR_TYPE_I64);
    void *found = jit_bridge_lookup(&jb, "test_cb");
    jit_bridge_destroy(&jb);

    if (slot >= 0 && found == (void *)vir_builtin_print_i64) PASS();
    else FAIL("callback registration failed");
}

static void test_jit_bridge_register_intrinsics(void)
{
    TEST("jit_bridge register intrinsics");
    jit_bridge_t jb;
    jit_bridge_init(&jb, 65536);

    int rc = jit_bridge_register_intrinsics(&jb);
    void *print_addr = jit_bridge_lookup(&jb, "vir_builtin_print_i64");
    jit_bridge_destroy(&jb);

    if (rc > 0 && print_addr != NULL) PASS();
    else FAIL("intrinsics registration failed");
}

static void test_jit_bridge_emit_code(void)
{
    TEST("jit_bridge emit + finalise");
    jit_bridge_t jb;
    jit_bridge_init(&jb, 65536);

    /* A trivial code block: RET (x86: 0xC3) or (arm64: 0xD65F03C0) */
#if defined(VIR_ARCH_X86_64)
    uint8_t code[] = { 0xC3 };
#elif defined(VIR_ARCH_ARM64)
    uint8_t code[] = { 0xC0, 0x03, 0x5F, 0xD6 };
#else
    uint8_t code[] = { 0x00 };
#endif

    int blk = jit_bridge_emit_code(&jb, 1, code, sizeof(code));
    int fin = jit_bridge_finalise(&jb);
    jit_bridge_destroy(&jb);

    if (blk >= 0 && fin == 0) PASS();
    else FAIL("emit/finalise failed");
}

/* ═══════════════════════════════════════════════════════
 * IR Lowering Tests
 * ═══════════════════════════════════════════════════════ */

static void test_ir_lower_ast_create(void)
{
    TEST("ir_lower AST create/free");
    ast_node_t *prog = ast_new(AST_PROGRAM);
    ast_node_t *lit  = ast_new(AST_LITERAL_INT);
    lit->int_val = 42;
    int rc = ast_add_child(prog, lit);
    if (rc == 0 && prog->child_count == 1 && prog->children[0]->int_val == 42) {
        ast_free(prog);
        PASS();
    } else {
        ast_free(prog);
        FAIL("ast create failed");
    }
}

static void test_ir_lower_simple_program(void)
{
    TEST("ir_lower simple program → Q-IR");

    /* Build AST: program { var x = 42; print x; } */
    ast_node_t *prog = ast_new(AST_PROGRAM);

    /* var x = 42 */
    ast_node_t *decl = ast_new(AST_VAR_DECL);
    strncpy(decl->name, "x", AST_NAME_LEN);
    ast_node_t *val = ast_new(AST_LITERAL_INT);
    val->int_val = 42;
    ast_add_child(decl, val);
    ast_add_child(prog, decl);

    /* print x */
    ast_node_t *pr = ast_new(AST_PRINT);
    ast_node_t *id = ast_new(AST_IDENTIFIER);
    strncpy(id->name, "x", AST_NAME_LEN);
    ast_add_child(pr, id);
    ast_add_child(prog, pr);

    /* Lower */
    lower_ctx_t ctx;
    lower_init(&ctx, "test");
    int rc = lower_program(&ctx, prog);
    q_module_t *mod = lower_get_module(&ctx);

    /* Should have 1 function (__main__) with some instructions */
    int ok = (rc == 0 && mod->func_count >= 1 &&
              mod->functions[0].body_count > 0);

    ast_free(prog);
    lower_destroy(&ctx);

    if (ok) PASS();
    else FAIL("lowering failed");
}

static void test_ir_lower_regalloc(void)
{
    TEST("ir_lower linear-scan regalloc");

    /* Build a small function: x=10; y=20; z=x+y; print z; return z */
    ast_node_t *prog = ast_new(AST_PROGRAM);
    ast_node_t *fn   = ast_new(AST_FUNC_DEF);
    strncpy(fn->name, "add_fn", AST_NAME_LEN);

    ast_node_t *body = ast_new(AST_BLOCK);

    ast_node_t *d1 = ast_new(AST_VAR_DECL);
    strncpy(d1->name, "x", AST_NAME_LEN);
    ast_node_t *v1 = ast_new(AST_LITERAL_INT); v1->int_val = 10;
    ast_add_child(d1, v1);
    ast_add_child(body, d1);

    ast_node_t *d2 = ast_new(AST_VAR_DECL);
    strncpy(d2->name, "y", AST_NAME_LEN);
    ast_node_t *v2 = ast_new(AST_LITERAL_INT); v2->int_val = 20;
    ast_add_child(d2, v2);
    ast_add_child(body, d2);

    /* z = x + y */
    ast_node_t *d3 = ast_new(AST_VAR_DECL);
    strncpy(d3->name, "z", AST_NAME_LEN);
    ast_node_t *add = ast_new(AST_BINOP);
    add->op = OP_ADD;
    ast_node_t *ix = ast_new(AST_IDENTIFIER); strncpy(ix->name, "x", AST_NAME_LEN);
    ast_node_t *iy = ast_new(AST_IDENTIFIER); strncpy(iy->name, "y", AST_NAME_LEN);
    ast_add_child(add, ix);
    ast_add_child(add, iy);
    ast_add_child(d3, add);
    ast_add_child(body, d3);

    /* print z */
    ast_node_t *pr = ast_new(AST_PRINT);
    ast_node_t *iz = ast_new(AST_IDENTIFIER); strncpy(iz->name, "z", AST_NAME_LEN);
    ast_add_child(pr, iz);
    ast_add_child(body, pr);

    /* return z */
    ast_node_t *ret = ast_new(AST_RETURN);
    ast_node_t *iz2 = ast_new(AST_IDENTIFIER); strncpy(iz2->name, "z", AST_NAME_LEN);
    ast_add_child(ret, iz2);
    ast_add_child(body, ret);

    ast_add_child(fn, body);
    ast_add_child(prog, fn);

    /* Lower */
    lower_ctx_t ctx;
    lower_init(&ctx, "regalloc_test");
    int rc = lower_program(&ctx, prog);

    /* Run liveness + regalloc on the function */
    q_module_t *mod = lower_get_module(&ctx);
    int alloc_ok = 0;
    if (rc == 0 && mod->func_count >= 1) {
        lower_compute_liveness(&ctx, &mod->functions[0]);
        lower_regalloc_linear_scan(&ctx, 6); /* 6 GP regs */
        /* All intervals should have been assigned (6 regs > vregs used) */
        alloc_ok = 1;
        for (uint32_t i = 0; i < ctx.interval_count; i++) {
            if (ctx.intervals[i].phys_reg < 0) {
                alloc_ok = 0; break;
            }
        }
    }

    ast_free(prog);
    lower_destroy(&ctx);

    if (rc == 0 && alloc_ok) PASS();
    else FAIL("regalloc failed");
}

static void test_ir_lower_sym_table(void)
{
    TEST("ir_lower symbol table");
    symbol_table_t st;
    sym_init(&st);
    sym_define(&st, "alpha", 5, VIR_TYPE_I64);
    sym_define(&st, "beta",  9, VIR_TYPE_PTR);

    uint32_t r;
    int ok1 = (sym_lookup(&st, "alpha", &r) == 0 && r == 5);
    int ok2 = (sym_lookup(&st, "beta",  &r) == 0 && r == 9);
    int ok3 = (sym_lookup(&st, "gamma", &r) != 0);

    if (ok1 && ok2 && ok3) PASS();
    else FAIL("symbol table lookup wrong");
}

/* ═══════════════════════════════════════════════════════
 * Rollback (Redundancy Patching) Tests
 * ═══════════════════════════════════════════════════════ */

static void test_jit_bridge_emit_dual(void)
{
    TEST("jit_bridge emit_dual safe start");
    jit_bridge_t jb;
    jit_bridge_init(&jb, 4096);

    /* ARM64 RET = 0xD65F03C0, use as dummy "safe" and "fast" code */
    uint8_t safe[] = { 0xC0, 0x03, 0x5F, 0xD6 };
    uint8_t fast[] = { 0x00, 0x00, 0x80, 0xD2, 0xC0, 0x03, 0x5F, 0xD6 };

    int idx = jit_bridge_emit_dual(&jb, 500, safe, sizeof(safe),
                                   fast, sizeof(fast));

    int ok = (idx >= 0);
    ok = ok && (jit_bridge_is_fast(&jb, 500) == 0); /* starts safe */
    ok = ok && (jb.blocks[idx].safe_size == sizeof(safe));
    ok = ok && (jb.blocks[idx].fast_size == sizeof(fast));

    jit_bridge_destroy(&jb);
    if (ok) PASS(); else FAIL("emit_dual basic check");
}

static void test_jit_bridge_patch_and_rollback(void)
{
    TEST("jit_bridge patch→fast→rollback");
    jit_bridge_t jb;
    jit_bridge_init(&jb, 4096);

    uint8_t safe[] = { 0xC0, 0x03, 0x5F, 0xD6 };
    uint8_t fast[] = { 0x00, 0x00, 0x80, 0xD2, 0xC0, 0x03, 0x5F, 0xD6 };
    jit_bridge_emit_dual(&jb, 600, safe, sizeof(safe),
                         fast, sizeof(fast));

    /* Patch to fast */
    int rc1 = jit_bridge_patch_to_fast(&jb, 600);
    int is_fast1 = jit_bridge_is_fast(&jb, 600);

    /* Rollback to safe */
    int rc2 = jit_bridge_rollback(&jb, 600);
    int is_fast2 = jit_bridge_is_fast(&jb, 600);

    jit_bridge_destroy(&jb);
    if (rc1 == 0 && is_fast1 == 1 && rc2 == 0 && is_fast2 == 0) PASS();
    else FAIL("patch/rollback cycle");
}

static void test_jit_bridge_auto_rollback(void)
{
    TEST("jit_bridge auto-rollback on faults");
    jit_bridge_t jb;
    jit_bridge_init(&jb, 4096);

    uint8_t safe[] = { 0xC0, 0x03, 0x5F, 0xD6 };
    uint8_t fast[] = { 0x00, 0x00, 0x80, 0xD2, 0xC0, 0x03, 0x5F, 0xD6 };
    jit_bridge_emit_dual(&jb, 700, safe, sizeof(safe),
                         fast, sizeof(fast));
    jit_bridge_patch_to_fast(&jb, 700);

    /* Report faults below threshold – should stay fast */
    int r1 = jit_bridge_report_fault(&jb, 700, 3);
    int r2 = jit_bridge_report_fault(&jb, 700, 3);
    int still_fast = jit_bridge_is_fast(&jb, 700);

    /* Third fault → triggers auto-rollback (max_faults=3) */
    int r3 = jit_bridge_report_fault(&jb, 700, 3);
    int rolled_back = (jit_bridge_is_fast(&jb, 700) == 0);

    jit_bridge_destroy(&jb);
    if (r1 == 0 && r2 == 0 && still_fast == 1 &&
        r3 == 1 && rolled_back) PASS();
    else FAIL("auto-rollback");
}

/* ═══════════════════════════════════════════════════════
 * Tail-Call Optimization Tests
 * ═══════════════════════════════════════════════════════ */

static void test_tco_basic(void)
{
    TEST("tco: CALL+RET → JUMP+NOP");
    q_function_t fn;
    q_func_init(&fn, "tco_test");

    /* Emit: LOAD r0, #42; CALL @10; RET r0 */
    q_func_emit(&fn, q_instr(Q_LOAD, q_vreg(0), q_imm(42), q_none()));
    q_func_emit(&fn, q_instr(Q_CALL, q_none(), q_label(10), q_none()));
    q_func_emit(&fn, q_instr(Q_RET, q_none(), q_vreg(0), q_none()));

    int count = lower_tco_pass(&fn);

    int ok = (count == 1);
    ok = ok && (fn.body[1].opcode == Q_JUMP);
    ok = ok && (fn.body[1].src1.label == 10);   /* target preserved */
    ok = ok && (fn.body[2].opcode == Q_NOP);

    q_func_free(&fn);
    if (ok) PASS(); else FAIL("tco basic");
}

static void test_tco_no_tail(void)
{
    TEST("tco: non-tail CALL not touched");
    q_function_t fn;
    q_func_init(&fn, "notail_test");

    /* CALL @5; ADD r0, r1, r2; RET r0 – call is NOT at tail */
    q_func_emit(&fn, q_instr(Q_CALL, q_none(), q_label(5), q_none()));
    q_func_emit(&fn, q_instr(Q_ADD, q_vreg(0), q_vreg(1), q_vreg(2)));
    q_func_emit(&fn, q_instr(Q_RET, q_none(), q_vreg(0), q_none()));

    int count = lower_tco_pass(&fn);

    int ok = (count == 0);
    ok = ok && (fn.body[0].opcode == Q_CALL);  /* untouched */
    ok = ok && (fn.body[2].opcode == Q_RET);    /* untouched */

    q_func_free(&fn);
    if (ok) PASS(); else FAIL("non-tail call modified");
}

static void test_tco_multiple(void)
{
    TEST("tco: multiple tail calls");
    q_function_t fn;
    q_func_init(&fn, "multi_tco");

    /* Two CALL+RET pairs separated by a label */
    q_func_emit(&fn, q_instr(Q_CALL, q_none(), q_label(1), q_none()));
    q_func_emit(&fn, q_instr(Q_RET, q_none(), q_vreg(0), q_none()));
    q_func_emit(&fn, q_instr(Q_LOAD, q_vreg(1), q_imm(99), q_none()));
    q_func_emit(&fn, q_instr(Q_CALL, q_none(), q_label(2), q_none()));
    q_func_emit(&fn, q_instr(Q_RET, q_none(), q_vreg(1), q_none()));

    int count = lower_tco_pass(&fn);

    int ok = (count == 2);
    ok = ok && (fn.body[0].opcode == Q_JUMP);
    ok = ok && (fn.body[1].opcode == Q_NOP);
    ok = ok && (fn.body[3].opcode == Q_JUMP);
    ok = ok && (fn.body[3].src1.label == 2);
    ok = ok && (fn.body[4].opcode == Q_NOP);

    q_func_free(&fn);
    if (ok) PASS(); else FAIL("multiple tco");
}

/* ═══════════════════════════════════════════════════════
 * Bridge Extended Tests
 * ═══════════════════════════════════════════════════════ */

static void test_bridge_alloc_executable(void)
{
    TEST("bridge alloc_executable + free");
    void *p = bridge_alloc_executable(4096);
    if (p) {
        bridge_jit_free(p, 4096);
        PASS();
    } else {
        FAIL("alloc_executable returned NULL");
    }
}

static void test_bridge_abi_get(void)
{
    TEST("bridge ABI get");
    const abi_info_t *abi = bridge_get_abi(
#if defined(VIR_ARCH_ARM64)
        ARCH_ARM64
#else
        ARCH_X86_64
#endif
    );
    if (abi && abi->max_int_args > 0) PASS();
    else FAIL("ABI lookup failed");
}

/* ═══════════════════════════════════════════════════════
 * Lexer Tests
 * ═══════════════════════════════════════════════════════ */

static void test_lexer_english_keywords(void)
{
    TEST("lexer: English keywords");
    const char *src = "func main() then\n  var x = 42\n  return x\nend\n";
    vir_lexer_t lex;
    lexer_init(&lex, src, strlen(src));
    int rc = lexer_tokenize(&lex);
    if (rc != 0) { FAIL(lex.error); return; }

    /* Expect: FUNC IDENT( LPAREN RPAREN THEN NL VAR IDENT( ASSIGN INT(42) NL RETURN IDENT( NL END NL EOF */
    int ok = lex.token_count >= 10;
    ok = ok && lex.tokens[0].type == TOK_FUNC;
    ok = ok && lex.tokens[1].type == TOK_IDENT;
    ok = ok && strcmp(lex.tokens[1].str.buf, "main") == 0;
    ok = ok && lex.tokens[2].type == TOK_LPAREN;
    ok = ok && lex.tokens[3].type == TOK_RPAREN;
    ok = ok && lex.tokens[4].type == TOK_THEN;
    if (ok) PASS(); else FAIL("token mismatch");
}

static void test_lexer_vietnamese_keywords(void)
{
    TEST("lexer: Vietnamese keywords");
    /* "hàm chính() thì\n  biến x = 42\n  trả về x\nhết\n" */
    const char *src = "h\xc3\xa0m ch\xc3\xadnh() th\xc3\xac\n"
                      "  bi\xe1\xba\xbfn x = 42\n"
                      "  tr\xe1\xba\xa3 v\xe1\xbb\x81 x\n"
                      "h\xe1\xba\xbft\n";
    vir_lexer_t lex;
    lexer_init(&lex, src, strlen(src));
    int rc = lexer_tokenize(&lex);
    if (rc != 0) { FAIL(lex.error); return; }

    int ok = lex.token_count >= 8;
    ok = ok && lex.tokens[0].type == TOK_FUNC;    /* hàm */
    /* thì should appear after RPAREN */
    int found_then = 0;
    for (uint32_t i = 0; i < lex.token_count; i++) {
        if (lex.tokens[i].type == TOK_THEN) { found_then = 1; break; }
    }
    ok = ok && found_then;
    /* hết should appear */
    int found_end = 0;
    for (uint32_t i = 0; i < lex.token_count; i++) {
        if (lex.tokens[i].type == TOK_END) { found_end = 1; break; }
    }
    ok = ok && found_end;
    if (ok) PASS(); else FAIL("Vietnamese keyword mismatch");
}

static void test_lexer_operators(void)
{
    TEST("lexer: operators");
    const char *src = "x + y == 10 != z >= 5";
    vir_lexer_t lex;
    lexer_init(&lex, src, strlen(src));
    int rc = lexer_tokenize(&lex);
    if (rc != 0) { FAIL(lex.error); return; }

    /* IDENT PLUS IDENT EQ INT NE IDENT GE INT EOF */
    int ok = lex.tokens[1].type == TOK_PLUS;
    ok = ok && lex.tokens[3].type == TOK_EQ;
    ok = ok && lex.tokens[5].type == TOK_NE;
    ok = ok && lex.tokens[7].type == TOK_GE;
    if (ok) PASS(); else FAIL("operator mismatch");
}

static void test_lexer_strings_numbers(void)
{
    TEST("lexer: strings and numbers");
    const char *src = "\"hello\" 42 3.14 0xFF";
    vir_lexer_t lex;
    lexer_init(&lex, src, strlen(src));
    int rc = lexer_tokenize(&lex);
    if (rc != 0) { FAIL(lex.error); return; }

    int ok = lex.tokens[0].type == TOK_STRING;
    ok = ok && strcmp(lex.tokens[0].str.buf, "hello") == 0;
    ok = ok && lex.tokens[1].type == TOK_INT;
    ok = ok && lex.tokens[1].int_val == 42;
    ok = ok && lex.tokens[2].type == TOK_FLOAT;
    ok = ok && lex.tokens[3].type == TOK_INT;
    ok = ok && lex.tokens[3].int_val == 255;
    if (ok) PASS(); else FAIL("literal mismatch");
}

/* ═══════════════════════════════════════════════════════
 * Parser Tests
 * ═══════════════════════════════════════════════════════ */

static void test_parser_simple_func(void)
{
    TEST("parser: simple function");
    const char *src = "func add(a, b) then\n  return a + b\nend\n";
    vir_lexer_t lex;
    lexer_init(&lex, src, strlen(src));
    lexer_tokenize(&lex);

    vir_parser_t parser;
    parser_init(&parser, lex.tokens, lex.token_count);
    ast_node_t *ast = parser_parse_program(&parser);

    int ok = ast != NULL;
    ok = ok && ast->type == AST_PROGRAM;
    ok = ok && ast->child_count >= 1;
    ok = ok && ast->children[0]->type == AST_FUNC_DEF;
    ok = ok && strcmp(ast->children[0]->name, "add") == 0;
    if (ok) PASS(); else FAIL(parser.error);
    if (ast) ast_free(ast);
}

static void test_parser_if_else(void)
{
    TEST("parser: if/else");
    const char *src = "func test() then\n  if x > 0 then\n    return 1\n  else\n    return 0\n  end\nend\n";
    vir_lexer_t lex;
    lexer_init(&lex, src, strlen(src));
    lexer_tokenize(&lex);

    vir_parser_t parser;
    parser_init(&parser, lex.tokens, lex.token_count);
    ast_node_t *ast = parser_parse_program(&parser);

    int ok = ast != NULL;
    ok = ok && ast->child_count >= 1;
    if (ok) {
        ast_node_t *fn = ast->children[0];
        /* The last child should be BLOCK containing IF */
        ast_node_t *body = fn->children[fn->child_count - 1];
        ok = ok && body->type == AST_BLOCK;
        ok = ok && body->child_count >= 1;
        ok = ok && body->children[0]->type == AST_IF;
    }
    if (ok) PASS(); else FAIL(parser.error);
    if (ast) ast_free(ast);
}

static void test_parser_expression_precedence(void)
{
    TEST("parser: expression precedence");
    /* 2 + 3 * 4 should parse as 2 + (3 * 4) */
    const char *src = "func f() then\n  var x = 2 + 3 * 4\nend\n";
    vir_lexer_t lex;
    lexer_init(&lex, src, strlen(src));
    lexer_tokenize(&lex);

    vir_parser_t parser;
    parser_init(&parser, lex.tokens, lex.token_count);
    ast_node_t *ast = parser_parse_program(&parser);

    int ok = ast != NULL;
    if (ok) {
        ast_node_t *fn = ast->children[0];
        ast_node_t *body = fn->children[fn->child_count - 1];
        ast_node_t *var = body->children[0];
        ok = ok && var->type == AST_VAR_DECL;
        /* The initializer should be BINOP(ADD, 2, BINOP(MUL, 3, 4)) */
        ast_node_t *add = var->children[0];
        ok = ok && add->type == AST_BINOP;
        ok = ok && add->op == OP_ADD;
        ok = ok && add->children[1]->type == AST_BINOP;
        ok = ok && add->children[1]->op == OP_MUL;
    }
    if (ok) PASS(); else FAIL(parser.error);
    if (ast) ast_free(ast);
}

/* ═══════════════════════════════════════════════════════
 * End-to-End Pipeline Tests
 * ═══════════════════════════════════════════════════════ */

static void test_e2e_vm_simple(void)
{
    TEST("e2e: lex → parse → lower → VM");
    const char *src = "func main() then\n  var x = 10\n  var y = 20\n  return x + y\nend\n";

    /* Lex */
    vir_lexer_t lex;
    lexer_init(&lex, src, strlen(src));
    int rc = lexer_tokenize(&lex);
    if (rc != 0) { FAIL("lex failed"); return; }

    /* Parse */
    vir_parser_t parser;
    parser_init(&parser, lex.tokens, lex.token_count);
    ast_node_t *ast = parser_parse_program(&parser);
    if (!ast) { FAIL(parser.error); return; }

    /* Lower */
    lower_ctx_t ctx;
    lower_init(&ctx, "test_e2e");
    if (lower_program(&ctx, ast) != 0) {
        FAIL(ctx.last_error);
        ast_free(ast); lower_destroy(&ctx);
        return;
    }

    /* TCO pass */
    for (uint32_t i = 0; i < ctx.module.func_count; i++) {
        lower_tco_pass(&ctx.module.functions[i]);
    }

    /* Execute */
    vm_state_t vm;
    vm_init(&vm);
    vm_status_t status = vm_exec_module(&vm, &ctx.module);

    int ok = (status == VM_OK || status == VM_HALT);
    /* Result should be 30 in vreg 0 */
    ok = ok && (vm_get_reg(&vm, 0) == 30);

    if (ok) PASS();
    else {
        char msg[128];
        snprintf(msg, sizeof(msg), "status=%s result=%lld expected=30",
                 vm_status_str(status), (long long)vm_get_reg(&vm, 0));
        FAIL(msg);
    }

    ast_free(ast);
    lower_destroy(&ctx);
}

static void test_e2e_vm_if_else(void)
{
    TEST("e2e: if/else via VM");
    const char *src = "func main() then\n  var x = 5\n  if x > 3 then\n    return 1\n  else\n    return 0\n  end\nend\n";

    vir_lexer_t lex;
    lexer_init(&lex, src, strlen(src));
    lexer_tokenize(&lex);

    vir_parser_t parser;
    parser_init(&parser, lex.tokens, lex.token_count);
    ast_node_t *ast = parser_parse_program(&parser);
    if (!ast) { FAIL(parser.error); return; }

    lower_ctx_t ctx;
    lower_init(&ctx, "test_if");
    lower_program(&ctx, ast);

    for (uint32_t i = 0; i < ctx.module.func_count; i++)
        lower_tco_pass(&ctx.module.functions[i]);

    vm_state_t vm;
    vm_init(&vm);
    vm_status_t status = vm_exec_module(&vm, &ctx.module);

    int ok = (status == VM_OK || status == VM_HALT);
    ok = ok && (vm_get_reg(&vm, 0) == 1);  /* 5 > 3 → return 1 */

    if (ok) PASS();
    else {
        char msg[128];
        snprintf(msg, sizeof(msg), "status=%s result=%lld expected=1",
                 vm_status_str(status), (long long)vm_get_reg(&vm, 0));
        FAIL(msg);
    }

    ast_free(ast);
    lower_destroy(&ctx);
}

static void test_e2e_vm_loop(void)
{
    TEST("e2e: loop via VM");
    const char *src = "func main() then\n  var sum = 0\n  var i = 0\n"
                      "  while i < 5 then\n    sum = sum + i\n    i = i + 1\n  end\n"
                      "  return sum\nend\n";

    vir_lexer_t lex;
    lexer_init(&lex, src, strlen(src));
    lexer_tokenize(&lex);

    vir_parser_t parser;
    parser_init(&parser, lex.tokens, lex.token_count);
    ast_node_t *ast = parser_parse_program(&parser);
    if (!ast) { FAIL(parser.error); return; }

    lower_ctx_t ctx;
    lower_init(&ctx, "test_loop");
    lower_program(&ctx, ast);

    for (uint32_t i = 0; i < ctx.module.func_count; i++)
        lower_tco_pass(&ctx.module.functions[i]);

    vm_state_t vm;
    vm_init(&vm);
    vm_status_t status = vm_exec_module(&vm, &ctx.module);

    int ok = (status == VM_OK || status == VM_HALT);
    /* sum = 0+1+2+3+4 = 10 */
    ok = ok && (vm_get_reg(&vm, 0) == 10);

    if (ok) PASS();
    else {
        char msg[128];
        snprintf(msg, sizeof(msg), "status=%s result=%lld expected=10",
                 vm_status_str(status), (long long)vm_get_reg(&vm, 0));
        FAIL(msg);
    }

    ast_free(ast);
    lower_destroy(&ctx);
}

/* ═══════════════════════════════════════════════════════
 * Codegen Full Tests
 * ═══════════════════════════════════════════════════════ */

static void test_codegen_full_branches(void)
{
    TEST("codegen_emit_full: branch patching");
    /*
     * LOAD v0, 10
     * LOAD v1, 3
     * CMP_GT v2, v0, v1    ; 10 > 3 → 1
     * JUMP_IF v2, :L1
     * LOAD v0, 0          ; shouldn't run
     * JUMP :L2
     * LABEL :L1
     * LOAD v0, 1          ; should run → v0 = 1
     * LABEL :L2
     * RET v0
     */
    q_instruction_t code[10];
    memset(code, 0, sizeof(code));

    code[0] = (q_instruction_t){Q_LOAD, q_vreg(0), q_imm(10), q_none(), 0};
    code[1] = (q_instruction_t){Q_LOAD, q_vreg(1), q_imm(3),  q_none(), 0};
    code[2] = (q_instruction_t){Q_CMP_GT, q_vreg(2), q_vreg(0), q_vreg(1), 0};

    /* JUMP_IF v2, :L1(label=1) */
    code[3].opcode   = Q_JUMP_IF;
    code[3].dest     = q_none();
    code[3].src1     = q_vreg(2);
    code[3].src2     = q_label(1);

    code[4] = (q_instruction_t){Q_LOAD, q_vreg(0), q_imm(0), q_none(), 0};

    /* JUMP :L2(label=2) */
    code[5].opcode   = Q_JUMP;
    code[5].dest     = q_none();
    code[5].src1     = q_label(2);
    code[5].src2     = q_none();

    /* LABEL :L1 */
    code[6].opcode   = Q_LABEL;
    code[6].patch_id = 1;
    code[6].dest = code[6].src1 = code[6].src2 = q_none();

    code[7] = (q_instruction_t){Q_LOAD, q_vreg(0), q_imm(1), q_none(), 0};

    /* LABEL :L2 */
    code[8].opcode   = Q_LABEL;
    code[8].patch_id = 2;
    code[8].dest = code[8].src1 = code[8].src2 = q_none();

    code[9] = (q_instruction_t){Q_RET, q_none(), q_vreg(0), q_none(), 0};

    codebuf_t cb;
    codebuf_init(&cb, 4096);

#if defined(__aarch64__) || defined(__arm64__)
    target_arch_t arch = ARCH_ARM64;
#else
    target_arch_t arch = ARCH_X86_64;
#endif

    int rc = codegen_emit_full(&cb, code, 10, arch, NULL);
    int ok = (rc == 0) && (cb.len > 0);

    if (ok) PASS(); else FAIL("emit_full failed or empty");
    codebuf_free(&cb);
}

/* ═══════════════════════════════════════════════════════
 * Codegen Full2 Tests (Phase 1 – complete opcode coverage)
 * ═══════════════════════════════════════════════════════ */

static void test_codegen_full2_bitwise(void)
{
    TEST("codegen_emit_full2: bitwise AND/OR/XOR");

    codegen_rt_t rt;
    codegen_rt_init(&rt);

    /*
     * LOAD v0, 0xFF00
     * LOAD v1, 0x0F0F
     * AND  v2, v0, v1   → 0x0F00
     * OR   v3, v0, v1   → 0xFF0F
     * XOR  v4, v0, v1   → 0xF00F
     * RET  v2
     */
    q_instruction_t code[6];
    memset(code, 0, sizeof(code));
    code[0] = (q_instruction_t){Q_LOAD, q_vreg(0), q_imm(0xFF00), q_none(), 0};
    code[1] = (q_instruction_t){Q_LOAD, q_vreg(1), q_imm(0x0F0F), q_none(), 0};
    code[2] = (q_instruction_t){Q_AND,  q_vreg(2), q_vreg(0), q_vreg(1), 0};
    code[3] = (q_instruction_t){Q_OR,   q_vreg(3), q_vreg(0), q_vreg(1), 0};
    code[4] = (q_instruction_t){Q_XOR,  q_vreg(4), q_vreg(0), q_vreg(1), 0};
    code[5] = (q_instruction_t){Q_RET,  q_none(), q_vreg(2), q_none(), 0};

    codebuf_t cb;
    codebuf_init(&cb, 4096);

#if defined(__aarch64__) || defined(__arm64__)
    target_arch_t arch = ARCH_ARM64;
#else
    target_arch_t arch = ARCH_X86_64;
#endif

    int rc = codegen_emit_full2(&cb, code, 6, arch, &rt);
    int ok = (rc == 0) && (cb.len > 0);
    if (ok) PASS(); else FAIL("emit_full2 bitwise failed");
    codebuf_free(&cb);
}

static void test_codegen_full2_globals(void)
{
    TEST("codegen_emit_full2: global load/store");

    codegen_rt_t rt;
    codegen_rt_init(&rt);

    /* Allocate globals on the stack */
    int64_t globals[64];
    memset(globals, 0, sizeof(globals));
    rt.globals = globals;
    rt.global_cap = 64;

    /*
     * LOAD v0, 42
     * STORE_GLOBAL [0], v0      — globals[0] = 42
     * LOAD_GLOBAL  v1, [0]      — v1 = globals[0]
     * RET  v1
     */
    q_instruction_t code[4];
    memset(code, 0, sizeof(code));
    code[0] = (q_instruction_t){Q_LOAD, q_vreg(0), q_imm(42), q_none(), 0};
    code[1] = (q_instruction_t){Q_STORE_GLOBAL, q_none(), q_imm(0), q_vreg(0), 0};
    code[2] = (q_instruction_t){Q_LOAD_GLOBAL,  q_vreg(1), q_imm(0), q_none(), 0};
    code[3] = (q_instruction_t){Q_RET, q_none(), q_vreg(1), q_none(), 0};

    codebuf_t cb;
    codebuf_init(&cb, 4096);

#if defined(__aarch64__) || defined(__arm64__)
    target_arch_t arch = ARCH_ARM64;
#else
    target_arch_t arch = ARCH_X86_64;
#endif

    int rc = codegen_emit_full2(&cb, code, 4, arch, &rt);
    int ok = (rc == 0) && (cb.len > 0);
    if (ok) PASS(); else FAIL("emit_full2 globals failed");
    codebuf_free(&cb);
}

static void test_codegen_full2_intrinsic_calls(void)
{
    TEST("codegen_emit_full2: intrinsic arr/str ops");

    codegen_rt_t rt;
    codegen_rt_init(&rt);

    /*
     * LOAD    v0, 16
     * ARR_NEW v1, v0            — arr = new_array(16)
     * LOAD    v2, 99
     * ARR_PUSH _, v1, v2        — push(arr, 99)
     * ARR_LEN v3, v1            — len = arr_len(arr)
     * RET     v3
     */
    q_instruction_t code[6];
    memset(code, 0, sizeof(code));
    code[0] = (q_instruction_t){Q_LOAD,     q_vreg(0), q_imm(16),  q_none(), 0};
    code[1] = (q_instruction_t){Q_ARR_NEW,  q_vreg(1), q_vreg(0),  q_none(), 0};
    code[2] = (q_instruction_t){Q_LOAD,     q_vreg(2), q_imm(99),  q_none(), 0};
    code[3] = (q_instruction_t){Q_ARR_PUSH, q_none(),  q_vreg(1),  q_vreg(2), 0};
    code[4] = (q_instruction_t){Q_ARR_LEN,  q_vreg(3), q_vreg(1),  q_none(), 0};
    code[5] = (q_instruction_t){Q_RET,      q_none(),  q_vreg(3),  q_none(), 0};

    codebuf_t cb;
    codebuf_init(&cb, 8192);

#if defined(__aarch64__) || defined(__arm64__)
    target_arch_t arch = ARCH_ARM64;
#else
    target_arch_t arch = ARCH_X86_64;
#endif

    int rc = codegen_emit_full2(&cb, code, 6, arch, &rt);
    int ok = (rc == 0) && (cb.len > 0);
    if (ok) PASS(); else FAIL("emit_full2 intrinsic calls failed");
    codebuf_free(&cb);
}

static void test_codegen_full2_shift_mod(void)
{
    TEST("codegen_emit_full2: SHL/SHR/MOD");

    codegen_rt_t rt;
    codegen_rt_init(&rt);

    /*
     * LOAD v0, 1
     * LOAD v1, 4
     * SHL  v2, v0, v1    → 1 << 4 = 16
     * LOAD v3, 7
     * MOD  v4, v2, v3    → 16 % 7 = 2
     * SHR  v5, v2, v0    → 16 >> 1 = 8
     * RET  v4
     */
    q_instruction_t code[7];
    memset(code, 0, sizeof(code));
    code[0] = (q_instruction_t){Q_LOAD, q_vreg(0), q_imm(1),  q_none(), 0};
    code[1] = (q_instruction_t){Q_LOAD, q_vreg(1), q_imm(4),  q_none(), 0};
    code[2] = (q_instruction_t){Q_SHL,  q_vreg(2), q_vreg(0), q_vreg(1), 0};
    code[3] = (q_instruction_t){Q_LOAD, q_vreg(3), q_imm(7),  q_none(), 0};
    code[4] = (q_instruction_t){Q_MOD,  q_vreg(4), q_vreg(2), q_vreg(3), 0};
    code[5] = (q_instruction_t){Q_SHR,  q_vreg(5), q_vreg(2), q_vreg(0), 0};
    code[6] = (q_instruction_t){Q_RET,  q_none(),  q_vreg(4), q_none(), 0};

    codebuf_t cb;
    codebuf_init(&cb, 4096);

#if defined(__aarch64__) || defined(__arm64__)
    target_arch_t arch = ARCH_ARM64;
#else
    target_arch_t arch = ARCH_X86_64;
#endif

    int rc = codegen_emit_full2(&cb, code, 7, arch, &rt);
    int ok = (rc == 0) && (cb.len > 0);
    if (ok) PASS(); else FAIL("emit_full2 shift/mod failed");
    codebuf_free(&cb);
}

static void test_intrinsics_phase1(void)
{
    TEST("intrinsics: phase1 string/array builtins");

    /* Test str_cat */
    const char *cat = vir_builtin_str_cat("hello", " world");
    int ok = (cat != NULL && strcmp(cat, "hello world") == 0);
    free((void *)cat);

    /* Test str_eq */
    int eq = (int)vir_builtin_str_eq("abc", "abc");
    int neq = (int)vir_builtin_str_eq("abc", "xyz");
    ok = ok && (eq == 1) && (neq == 0);

    /* Test str_get */
    int ch = (int)vir_builtin_str_get("ABC", 1);
    ok = ok && (ch == 'B');

    /* Test i_to_str */
    const char *s = vir_builtin_i_to_str(42);
    ok = ok && (s != NULL && strcmp(s, "42") == 0);
    free((void *)s);

    /* Test str_to_i */
    int64_t n = vir_builtin_str_to_i("123");
    ok = ok && (n == 123);

    /* Test arr_new/push/get/len */
    int64_t arr = vir_builtin_arr_new(8);
    ok = ok && (arr >= 0);
    vir_builtin_arr_push(arr, 10);
    vir_builtin_arr_push(arr, 20);
    vir_builtin_arr_push(arr, 30);
    ok = ok && (vir_builtin_arr_len(arr) == 3);
    ok = ok && (vir_builtin_arr_get(arr, 0) == 10);
    ok = ok && (vir_builtin_arr_get(arr, 2) == 30);

    /* Test arr_set */
    vir_builtin_arr_set(arr, 1, 99);
    ok = ok && (vir_builtin_arr_get(arr, 1) == 99);

    if (ok) PASS(); else FAIL("phase1 intrinsic tests failed");
}

/* ═══════════════════════════════════════════════════════
 * Blacklist Tests
 * ═══════════════════════════════════════════════════════ */

static void test_blacklist_threshold(void)
{
    TEST("blacklist: threshold enforcement");

    jit_bridge_t jb;
    jit_bridge_init(&jb, 65536);
    jit_bridge_set_blacklist_threshold(&jb, 3);

    /* Emit dual code (safe + fast) */
    uint8_t safe_code[] = {0x90, 0x90, 0xC3};  /* NOP NOP RET */
    uint8_t fast_code[] = {0x90, 0xC3, 0x90};  /* NOP RET NOP */
    jit_bridge_emit_dual(&jb, 100, safe_code, 3, fast_code, 3);

    /* Simulate 3 rollbacks */
    jit_bridge_patch_to_fast(&jb, 100);
    jit_bridge_rollback(&jb, 100);  /* rollback #1 */
    jit_bridge_patch_to_fast(&jb, 100);
    jit_bridge_rollback(&jb, 100);  /* rollback #2 */
    jit_bridge_patch_to_fast(&jb, 100);
    jit_bridge_rollback(&jb, 100);  /* rollback #3 → blacklisted */

    int ok = jit_bridge_is_blacklisted(&jb, 100) == 1;
    /* patch_to_fast should now return -2 */
    ok = ok && jit_bridge_patch_to_fast(&jb, 100) == -2;

    if (ok) PASS(); else FAIL("blacklist not enforced");
    jit_bridge_destroy(&jb);
}

/* ═══════════════════════════════════════════════════════
 * VM Array/String/Memory Opcode Tests
 * ═══════════════════════════════════════════════════════ */

/* Helper: run Vir source through full pipeline, return R0 */
static int64_t run_vir(const char *src, int *out_ok)
{
    vir_lexer_t lex;
    lexer_init(&lex, src, strlen(src));
    if (lexer_tokenize(&lex) != 0) { *out_ok = 0; return -9999; }

    vir_parser_t parser;
    parser_init(&parser, lex.tokens, lex.token_count);
    ast_node_t *ast = parser_parse_program(&parser);
    if (!ast) { *out_ok = 0; return -9999; }

    lower_ctx_t ctx;
    lower_init(&ctx, "test");
    if (lower_program(&ctx, ast) != 0) {
        ast_free(ast); lower_destroy(&ctx);
        *out_ok = 0; return -9999;
    }
    for (uint32_t i = 0; i < ctx.module.func_count; i++)
        lower_tco_pass(&ctx.module.functions[i]);

    vm_state_t vm;
    vm_init(&vm);
    vm_status_t status = vm_exec_module(&vm, &ctx.module);

    int64_t result = vm_get_reg(&vm, 0);
    *out_ok = (status == VM_OK || status == VM_HALT) ? 1 : 0;
    vm_destroy(&vm);
    ast_free(ast);
    lower_destroy(&ctx);
    return result;
}

static void test_vm_array_ops(void)
{
    TEST("vm: array new/push/get/len");
    /* Direct VM opcode test for arrays */
    q_function_t fn;
    memset(&fn, 0, sizeof(fn));
    strcpy(fn.name, "__main__");

    q_instruction_t code[16];
    int n = 0;
    /* ARR_NEW r0, cap=8 */
    code[n++] = (q_instruction_t){Q_ARR_NEW, q_vreg(0), q_imm(8), q_none(), 0, 0};
    /* ARR_PUSH r0, 100 */
    code[n++] = (q_instruction_t){Q_ARR_PUSH, q_none(), q_vreg(0), q_imm(100), 0, 0};
    /* ARR_PUSH r0, 200 */
    code[n++] = (q_instruction_t){Q_ARR_PUSH, q_none(), q_vreg(0), q_imm(200), 0, 0};
    /* ARR_PUSH r0, 300 */
    code[n++] = (q_instruction_t){Q_ARR_PUSH, q_none(), q_vreg(0), q_imm(300), 0, 0};
    /* ARR_GET r1, r0, 1 → should be 200 */
    code[n++] = (q_instruction_t){Q_ARR_GET, q_vreg(1), q_vreg(0), q_imm(1), 0, 0};
    /* ARR_LEN r2, r0 → should be 3 */
    code[n++] = (q_instruction_t){Q_ARR_LEN, q_vreg(2), q_vreg(0), q_none(), 0, 0};
    /* RET r1 (should be 200) */
    code[n++] = (q_instruction_t){Q_RET, q_none(), q_vreg(1), q_none(), 0, 0};

    fn.body = code;
    fn.body_count = (uint32_t)n;

    q_module_t mod;
    memset(&mod, 0, sizeof(mod));
    strcpy(mod.name, "test_arr");
    mod.functions[0] = fn;
    mod.func_count = 1;

    vm_state_t vm;
    vm_init(&vm);
    vm_status_t s = vm_exec_module(&vm, &mod);

    int ok = (s == VM_OK || s == VM_HALT);
    ok = ok && vm_get_reg(&vm, 1) == 200;
    ok = ok && vm_get_reg(&vm, 2) == 3;

    if (ok) PASS();
    else {
        char msg[128];
        snprintf(msg, sizeof(msg), "r1=%lld (exp 200), r2=%lld (exp 3)",
                 (long long)vm_get_reg(&vm, 1), (long long)vm_get_reg(&vm, 2));
        FAIL(msg);
    }
    vm_destroy(&vm);
}

static void test_vm_array_set(void)
{
    TEST("vm: array set + get");
    q_function_t fn;
    memset(&fn, 0, sizeof(fn));
    strcpy(fn.name, "__main__");

    q_instruction_t code[16];
    int n = 0;
    code[n++] = (q_instruction_t){Q_ARR_NEW, q_vreg(0), q_imm(4), q_none(), 0, 0};
    code[n++] = (q_instruction_t){Q_ARR_PUSH, q_none(), q_vreg(0), q_imm(10), 0, 0};
    code[n++] = (q_instruction_t){Q_ARR_PUSH, q_none(), q_vreg(0), q_imm(20), 0, 0};
    /* ARR_SET arr[0] = 99: src1=arr, src2=index, dest=value */
    code[n++] = (q_instruction_t){Q_ARR_SET, q_imm(99), q_vreg(0), q_imm(0), 0, 0};
    /* ARR_GET r1, arr, 0 → should be 99 */
    code[n++] = (q_instruction_t){Q_ARR_GET, q_vreg(1), q_vreg(0), q_imm(0), 0, 0};
    code[n++] = (q_instruction_t){Q_RET, q_none(), q_vreg(1), q_none(), 0, 0};

    fn.body = code;
    fn.body_count = (uint32_t)n;

    q_module_t mod;
    memset(&mod, 0, sizeof(mod));
    strcpy(mod.name, "test_arrset");
    mod.functions[0] = fn;
    mod.func_count = 1;

    vm_state_t vm;
    vm_init(&vm);
    vm_exec_module(&vm, &mod);

    int ok = vm_get_reg(&vm, 1) == 99;
    if (ok) PASS();
    else { char msg[64]; snprintf(msg, sizeof(msg), "got %lld", (long long)vm_get_reg(&vm, 1)); FAIL(msg); }
    vm_destroy(&vm);
}

static void test_vm_string_ops(void)
{
    TEST("vm: string len/get/eq");
    q_function_t fn;
    memset(&fn, 0, sizeof(fn));
    strcpy(fn.name, "__main__");

    q_module_t mod;
    memset(&mod, 0, sizeof(mod));
    strcpy(mod.name, "test_str");

    /* Add strings to module string table */
    uint32_t s_hello = q_module_add_string(&mod, "hello");
    uint32_t s_hello2 = q_module_add_string(&mod, "hello");
    uint32_t s_world = q_module_add_string(&mod, "world");

    q_instruction_t code[16];
    int n = 0;
    /* Load "hello" → r0 */
    code[n++] = (q_instruction_t){Q_LOAD, q_vreg(0), q_str(s_hello), q_none(), 0, 0};
    /* STR_LEN r1, r0 → should be 5 */
    code[n++] = (q_instruction_t){Q_STR_LEN, q_vreg(1), q_vreg(0), q_none(), 0, 0};
    /* STR_GET r2, r0, 1 → 'e' = 101 */
    code[n++] = (q_instruction_t){Q_STR_GET, q_vreg(2), q_vreg(0), q_imm(1), 0, 0};
    /* Load duplicate "hello" → r3 */
    code[n++] = (q_instruction_t){Q_LOAD, q_vreg(3), q_str(s_hello2), q_none(), 0, 0};
    /* STR_EQ r4, r0, r3 → should be 1 */
    code[n++] = (q_instruction_t){Q_STR_EQ, q_vreg(4), q_vreg(0), q_vreg(3), 0, 0};
    /* Load "world" → r5 */
    code[n++] = (q_instruction_t){Q_LOAD, q_vreg(5), q_str(s_world), q_none(), 0, 0};
    /* STR_EQ r6, r0, r5 → should be 0 */
    code[n++] = (q_instruction_t){Q_STR_EQ, q_vreg(6), q_vreg(0), q_vreg(5), 0, 0};
    code[n++] = (q_instruction_t){Q_RET, q_none(), q_vreg(1), q_none(), 0, 0};

    fn.body = code;
    fn.body_count = (uint32_t)n;
    mod.functions[0] = fn;
    mod.func_count = 1;

    vm_state_t vm;
    vm_init(&vm);
    vm_exec_module(&vm, &mod);

    int ok = vm_get_reg(&vm, 1) == 5;       /* strlen("hello") */
    ok = ok && vm_get_reg(&vm, 2) == 101;   /* 'e' */
    ok = ok && vm_get_reg(&vm, 4) == 1;     /* "hello" == "hello" */
    ok = ok && vm_get_reg(&vm, 6) == 0;     /* "hello" != "world" */
    ok = ok && s_hello == s_hello2;          /* dedup check */

    if (ok) PASS();
    else {
        char msg[256];
        snprintf(msg, sizeof(msg), "len=%lld char=%lld eq=%lld neq=%lld dedup=%d",
                 (long long)vm_get_reg(&vm, 1), (long long)vm_get_reg(&vm, 2),
                 (long long)vm_get_reg(&vm, 4), (long long)vm_get_reg(&vm, 6),
                 s_hello == s_hello2);
        FAIL(msg);
    }
    vm_destroy(&vm);
    mod.functions[0].body = NULL;  /* stack-allocated, don't free */
    q_module_free(&mod);
}

static void test_vm_string_cat(void)
{
    TEST("vm: string concat");
    q_function_t fn;
    memset(&fn, 0, sizeof(fn));
    strcpy(fn.name, "__main__");

    q_module_t mod;
    memset(&mod, 0, sizeof(mod));
    strcpy(mod.name, "test_strcat");

    uint32_t s_hello = q_module_add_string(&mod, "hello ");
    uint32_t s_world = q_module_add_string(&mod, "world");

    q_instruction_t code[8];
    int n = 0;
    code[n++] = (q_instruction_t){Q_LOAD, q_vreg(0), q_str(s_hello), q_none(), 0, 0};
    code[n++] = (q_instruction_t){Q_LOAD, q_vreg(1), q_str(s_world), q_none(), 0, 0};
    /* STR_CAT r2, r0, r1 → "hello world" */
    code[n++] = (q_instruction_t){Q_STR_CAT, q_vreg(2), q_vreg(0), q_vreg(1), 0, 0};
    /* STR_LEN r3, r2 → 11 */
    code[n++] = (q_instruction_t){Q_STR_LEN, q_vreg(3), q_vreg(2), q_none(), 0, 0};
    code[n++] = (q_instruction_t){Q_RET, q_none(), q_vreg(3), q_none(), 0, 0};

    fn.body = code;
    fn.body_count = (uint32_t)n;
    mod.functions[0] = fn;
    mod.func_count = 1;

    vm_state_t vm;
    vm_init(&vm);
    vm_exec_module(&vm, &mod);

    int ok = vm_get_reg(&vm, 3) == 11;
    if (ok) PASS();
    else { char msg[64]; snprintf(msg, sizeof(msg), "len=%lld", (long long)vm_get_reg(&vm, 3)); FAIL(msg); }
    vm_destroy(&vm);
    mod.functions[0].body = NULL;
    q_module_free(&mod);
}

static void test_vm_memory_ops(void)
{
    TEST("vm: alloc/store_byte/load_byte");
    q_function_t fn;
    memset(&fn, 0, sizeof(fn));
    strcpy(fn.name, "__main__");

    q_instruction_t code[16];
    int n = 0;
    /* ALLOC r0, 16 bytes */
    code[n++] = (q_instruction_t){Q_ALLOC, q_vreg(0), q_imm(16), q_none(), 0, 0};
    /* STORE_BYTE: *(r0 + 3) = 42 → dest has value, src1=base, src2=offset */
    code[n++] = (q_instruction_t){Q_STORE_BYTE, q_imm(42), q_vreg(0), q_imm(3), 0, 0};
    /* LOAD_BYTE r1, r0, 3 → should be 42 */
    code[n++] = (q_instruction_t){Q_LOAD_BYTE, q_vreg(1), q_vreg(0), q_imm(3), 0, 0};
    /* STORE_BYTE: *(r0 + 0) = 255 */
    code[n++] = (q_instruction_t){Q_STORE_BYTE, q_imm(255), q_vreg(0), q_imm(0), 0, 0};
    /* LOAD_BYTE r2, r0, 0 → should be 255 */
    code[n++] = (q_instruction_t){Q_LOAD_BYTE, q_vreg(2), q_vreg(0), q_imm(0), 0, 0};
    /* FREE r0 */
    code[n++] = (q_instruction_t){Q_FREE, q_none(), q_vreg(0), q_none(), 0, 0};
    code[n++] = (q_instruction_t){Q_RET, q_none(), q_vreg(1), q_none(), 0, 0};

    fn.body = code;
    fn.body_count = (uint32_t)n;

    q_module_t mod;
    memset(&mod, 0, sizeof(mod));
    strcpy(mod.name, "test_mem");
    mod.functions[0] = fn;
    mod.func_count = 1;

    vm_state_t vm;
    vm_init(&vm);
    vm_exec_module(&vm, &mod);

    int ok = vm_get_reg(&vm, 1) == 42 && vm_get_reg(&vm, 2) == 255;
    if (ok) PASS();
    else {
        char msg[128];
        snprintf(msg, sizeof(msg), "[3]=%lld (exp 42), [0]=%lld (exp 255)",
                 (long long)vm_get_reg(&vm, 1), (long long)vm_get_reg(&vm, 2));
        FAIL(msg);
    }
    vm_destroy(&vm);
}

static void test_vm_word_ops(void)
{
    TEST("vm: store_word/load_word");
    q_function_t fn;
    memset(&fn, 0, sizeof(fn));
    strcpy(fn.name, "__main__");

    q_instruction_t code[16];
    int n = 0;
    /* ALLOC r0, 64 bytes */
    code[n++] = (q_instruction_t){Q_ALLOC, q_vreg(0), q_imm(64), q_none(), 0, 0};
    /* STORE_WORD: *(i64*)(r0 + 2*8) = 12345 */
    code[n++] = (q_instruction_t){Q_STORE_WORD, q_imm(12345), q_vreg(0), q_imm(2), 0, 0};
    /* LOAD_WORD r1, r0, 2 → should be 12345 */
    code[n++] = (q_instruction_t){Q_LOAD_WORD, q_vreg(1), q_vreg(0), q_imm(2), 0, 0};
    code[n++] = (q_instruction_t){Q_FREE, q_none(), q_vreg(0), q_none(), 0, 0};
    code[n++] = (q_instruction_t){Q_RET, q_none(), q_vreg(1), q_none(), 0, 0};

    fn.body = code;
    fn.body_count = (uint32_t)n;

    q_module_t mod;
    memset(&mod, 0, sizeof(mod));
    strcpy(mod.name, "test_word");
    mod.functions[0] = fn;
    mod.func_count = 1;

    vm_state_t vm;
    vm_init(&vm);
    vm_exec_module(&vm, &mod);

    int ok = vm_get_reg(&vm, 1) == 12345;
    if (ok) PASS();
    else { char msg[64]; snprintf(msg, sizeof(msg), "got %lld", (long long)vm_get_reg(&vm, 1)); FAIL(msg); }
    vm_destroy(&vm);
}

static void test_vm_i_to_str(void)
{
    TEST("vm: i_to_str + str_to_i roundtrip");
    q_function_t fn;
    memset(&fn, 0, sizeof(fn));
    strcpy(fn.name, "__main__");

    q_instruction_t code[8];
    int n = 0;
    /* I_TO_STR r0, 42 → r0 = "42" */
    code[n++] = (q_instruction_t){Q_I_TO_STR, q_vreg(0), q_imm(42), q_none(), 0, 0};
    /* STR_LEN r1, r0 → 2 */
    code[n++] = (q_instruction_t){Q_STR_LEN, q_vreg(1), q_vreg(0), q_none(), 0, 0};
    /* STR_TO_I r2, r0 → 42 */
    code[n++] = (q_instruction_t){Q_STR_TO_I, q_vreg(2), q_vreg(0), q_none(), 0, 0};
    code[n++] = (q_instruction_t){Q_RET, q_none(), q_vreg(2), q_none(), 0, 0};

    fn.body = code;
    fn.body_count = (uint32_t)n;

    q_module_t mod;
    memset(&mod, 0, sizeof(mod));
    strcpy(mod.name, "test_itos");
    mod.functions[0] = fn;
    mod.func_count = 1;

    vm_state_t vm;
    vm_init(&vm);
    vm_exec_module(&vm, &mod);

    int ok = vm_get_reg(&vm, 1) == 2 && vm_get_reg(&vm, 2) == 42;
    if (ok) PASS();
    else {
        char msg[128];
        snprintf(msg, sizeof(msg), "len=%lld val=%lld",
                 (long long)vm_get_reg(&vm, 1), (long long)vm_get_reg(&vm, 2));
        FAIL(msg);
    }
    vm_destroy(&vm);
}

static void test_e2e_bitwise(void)
{
    TEST("e2e: bitwise operators");
    int ok;
    int64_t r;
    /* 5 & 3 = 1 (& is logical AND, but Q_AND does bitwise → same result),
     * 5 | 3 = 7, 5 xor 3 = 6 (v1.2: xor keyword), 1 << 4 = 16,
     * 32 shr 2 = 8 (v1.2: shr keyword, >> is cast) */
    r = run_vir("func main() then\n  return 5 & 3\nend\n", &ok);
    ok = ok && r == 1;
    r = run_vir("func main() then\n  return 5 | 3\nend\n", &ok);
    ok = ok && r == 7;
    r = run_vir("func main() then\n  return 5 xor 3\nend\n", &ok);
    ok = ok && r == 6;
    r = run_vir("func main() then\n  return 1 << 4\nend\n", &ok);
    ok = ok && r == 16;
    r = run_vir("func main() then\n  return 32 shr 2\nend\n", &ok);
    ok = ok && r == 8;
    if (ok) PASS(); else FAIL("bitwise result mismatch");
}

static void test_e2e_array_literal(void)
{
    TEST("e2e: array literal + index access");
    int ok;
    /* Create array [10, 20, 30], access [1] → 20 */
    int64_t r = run_vir(
        "func main() then\n"
        "  var a = [10, 20, 30]\n"
        "  return a[1]\n"
        "end\n", &ok);
    ok = ok && r == 20;
    if (ok) PASS();
    else { char msg[64]; snprintf(msg, sizeof(msg), "got %lld exp 20", (long long)r); FAIL(msg); }
}

static void test_e2e_array_builtin(void)
{
    TEST("e2e: array len/push builtins");
    int ok;
    int64_t r = run_vir(
        "func main() then\n"
        "  var a = [1, 2]\n"
        "  push(a, 3)\n"
        "  return len(a)\n"
        "end\n", &ok);
    ok = ok && r == 3;
    if (ok) PASS();
    else { char msg[64]; snprintf(msg, sizeof(msg), "got %lld exp 3", (long long)r); FAIL(msg); }
}

static void test_e2e_string_len(void)
{
    TEST("e2e: string len builtin");
    int ok;
    int64_t r = run_vir(
        "func main() then\n"
        "  var s = \"hello\"\n"
        "  return len(s)\n"
        "end\n", &ok);
    ok = ok && r == 5;
    if (ok) PASS();
    else { char msg[64]; snprintf(msg, sizeof(msg), "got %lld exp 5", (long long)r); FAIL(msg); }
}

static void test_e2e_index_assign(void)
{
    TEST("e2e: array index assign");
    int ok;
    int64_t r = run_vir(
        "func main() then\n"
        "  var a = [10, 20, 30]\n"
        "  a[0] = 99\n"
        "  return a[0]\n"
        "end\n", &ok);
    ok = ok && r == 99;
    if (ok) PASS();
    else { char msg[64]; snprintf(msg, sizeof(msg), "got %lld exp 99", (long long)r); FAIL(msg); }
}

/* ═══════════════════════════════════════════════════════
 * E2E Phase 1B: For Loop / Enum / Record
 * ═══════════════════════════════════════════════════════ */

static void test_e2e_for_range(void)
{
    TEST("e2e: for-range loop");
    int ok;
    /* Sum 0..5 → 0+1+2+3+4 = 10 */
    int64_t r = run_vir(
        "func main() then\n"
        "  var sum = 0\n"
        "  for i in 0..5 then\n"
        "    sum = sum + i\n"
        "  end\n"
        "  return sum\n"
        "end\n", &ok);
    ok = ok && r == 10;
    if (ok) PASS();
    else { char msg[64]; snprintf(msg, sizeof(msg), "got %lld exp 10", (long long)r); FAIL(msg); }
}

static void test_e2e_for_range_vi(void)
{
    TEST("e2e: for-range (Vietnamese)");
    int ok;
    /* với mỗi i trong 1..4 → 1+2+3 = 6 */
    int64_t r = run_vir(
        "hàm main() thì\n"
        "  biến tổng = 0\n"
        "  for i in 1..4 then\n"
        "    tổng = tổng + i\n"
        "  end\n"
        "  trả về tổng\n"
        "hết\n", &ok);
    ok = ok && r == 6;
    if (ok) PASS();
    else { char msg[64]; snprintf(msg, sizeof(msg), "got %lld exp 6", (long long)r); FAIL(msg); }
}

static void test_e2e_enum_basic(void)
{
    TEST("e2e: enum definition + access");
    int ok;
    int64_t r = run_vir(
        "enum Color then\n"
        "  RED = 0\n"
        "  GREEN = 1\n"
        "  BLUE = 2\n"
        "end\n"
        "func main() then\n"
        "  var c = Color.GREEN\n"
        "  return c\n"
        "end\n", &ok);
    ok = ok && r == 1;
    if (ok) PASS();
    else { char msg[64]; snprintf(msg, sizeof(msg), "got %lld exp 1", (long long)r); FAIL(msg); }
}

static void test_e2e_enum_auto(void)
{
    TEST("e2e: enum auto-increment");
    int ok;
    /* AUTO: A=0, B=1, C=2 */
    int64_t r = run_vir(
        "enum Op then\n"
        "  ADD\n"
        "  SUB\n"
        "  MUL\n"
        "end\n"
        "func main() then\n"
        "  return Op.MUL\n"
        "end\n", &ok);
    ok = ok && r == 2;
    if (ok) PASS();
    else { char msg[64]; snprintf(msg, sizeof(msg), "got %lld exp 2", (long long)r); FAIL(msg); }
}

static void test_e2e_enum_explicit(void)
{
    TEST("e2e: enum explicit values");
    int ok;
    int64_t r = run_vir(
        "enum Opcode then\n"
        "  NOP = 0\n"
        "  LOAD = 1\n"
        "  ADD = 16\n"
        "  RET = 68\n"
        "end\n"
        "func main() then\n"
        "  return Opcode.ADD + Opcode.RET\n"
        "end\n", &ok);
    ok = ok && r == 84;  /* 16 + 68 */
    if (ok) PASS();
    else { char msg[64]; snprintf(msg, sizeof(msg), "got %lld exp 84", (long long)r); FAIL(msg); }
}

static void test_e2e_record_basic(void)
{
    TEST("e2e: record definition + literal + field access");
    int ok;
    int64_t r = run_vir(
        "record Point then\n"
        "  x: num\n"
        "  y: num\n"
        "end\n"
        "func main() then\n"
        "  var p = Point { x: 10, y: 20 }\n"
        "  return p.x + p.y\n"
        "end\n", &ok);
    ok = ok && r == 30;
    if (ok) PASS();
    else { char msg[64]; snprintf(msg, sizeof(msg), "got %lld exp 30", (long long)r); FAIL(msg); }
}

static void test_e2e_record_assign(void)
{
    TEST("e2e: record field assign");
    int ok;
    int64_t r = run_vir(
        "record Pair then\n"
        "  a: num\n"
        "  b: num\n"
        "end\n"
        "func main() then\n"
        "  var p = Pair { a: 5, b: 10 }\n"
        "  p.a = 99\n"
        "  return p.a\n"
        "end\n", &ok);
    ok = ok && r == 99;
    if (ok) PASS();
    else { char msg[64]; snprintf(msg, sizeof(msg), "got %lld exp 99", (long long)r); FAIL(msg); }
}

static void test_e2e_record_3field(void)
{
    TEST("e2e: record with 3 fields");
    int ok;
    int64_t r = run_vir(
        "record Token then\n"
        "  kind: num\n"
        "  line: num\n"
        "  col: num\n"
        "end\n"
        "func main() then\n"
        "  var t = Token { kind: 42, line: 10, col: 5 }\n"
        "  return t.kind + t.line + t.col\n"
        "end\n", &ok);
    ok = ok && r == 57;  /* 42+10+5 */
    if (ok) PASS();
    else { char msg[64]; snprintf(msg, sizeof(msg), "got %lld exp 57", (long long)r); FAIL(msg); }
}

static void test_e2e_enum_record_combined(void)
{
    TEST("e2e: enum + record combined");
    int ok;
    int64_t r = run_vir(
        "enum TokenType then\n"
        "  INT = 1\n"
        "  PLUS = 2\n"
        "  EOF = 0\n"
        "end\n"
        "record Token then\n"
        "  kind: num\n"
        "  value: num\n"
        "end\n"
        "func main() then\n"
        "  var t = Token { kind: TokenType.PLUS, value: 0 }\n"
        "  return t.kind\n"
        "end\n", &ok);
    ok = ok && r == 2;
    if (ok) PASS();
    else { char msg[64]; snprintf(msg, sizeof(msg), "got %lld exp 2", (long long)r); FAIL(msg); }
}

static void test_e2e_for_array(void)
{
    TEST("e2e: for-range filling array");
    int ok;
    /* Create array, fill with for loop, return sum */
    int64_t r = run_vir(
        "func main() then\n"
        "  var a = arr_new(16)\n"
        "  for i in 0..5 then\n"
        "    push(a, i * 10)\n"
        "  end\n"
        "  return a[0] + a[1] + a[2] + a[3] + a[4]\n"
        "end\n", &ok);
    ok = ok && r == 100;  /* 0+10+20+30+40 */
    if (ok) PASS();
    else { char msg[64]; snprintf(msg, sizeof(msg), "got %lld exp 100", (long long)r); FAIL(msg); }
}

/* ── Phase 4 prep: break / continue / module system ─── */

static void test_e2e_break(void)
{
    TEST("e2e: break exits loop early");
    int ok;
    /* Sum 0..9 but break when i == 5 → sum = 0+1+2+3+4 = 10 */
    int64_t r = run_vir(
        "func main() then\n"
        "  var s = 0\n"
        "  var i = 0\n"
        "  while i < 10 then\n"
        "    if i == 5 then\n"
        "      break\n"
        "    end\n"
        "    s = s + i\n"
        "    i = i + 1\n"
        "  end\n"
        "  return s\n"
        "end\n", &ok);
    ok = ok && r == 10;
    if (ok) PASS();
    else { char msg[64]; snprintf(msg, sizeof(msg), "got %lld exp 10", (long long)r); FAIL(msg); }
}

static void test_e2e_continue(void)
{
    TEST("e2e: continue skips iteration");
    int ok;
    /* Sum 0..5, skip i==2 and i==4 → 0+1+3 = 4 */
    int64_t r = run_vir(
        "func main() then\n"
        "  var s = 0\n"
        "  for i in 0..5 then\n"
        "    if i == 2 then\n"
        "      continue\n"
        "    end\n"
        "    if i == 4 then\n"
        "      continue\n"
        "    end\n"
        "    s = s + i\n"
        "  end\n"
        "  return s\n"
        "end\n", &ok);
    ok = ok && r == 4;
    if (ok) PASS();
    else { char msg[64]; snprintf(msg, sizeof(msg), "got %lld exp 4", (long long)r); FAIL(msg); }
}

static void test_e2e_break_nested(void)
{
    TEST("e2e: break in nested loop");
    int ok;
    /* Outer sums i, inner breaks when j==2 → per iteration inner adds 0+1=1
     * outer 3 iterations → 3 + (0+1+2) = 6 */
    int64_t r = run_vir(
        "func main() then\n"
        "  var s = 0\n"
        "  for i in 0..3 then\n"
        "    s = s + i\n"
        "    for j in 0..5 then\n"
        "      if j == 2 then\n"
        "        break\n"
        "      end\n"
        "      s = s + 1\n"
        "    end\n"
        "  end\n"
        "  return s\n"
        "end\n", &ok);
    ok = ok && r == 9;  /* i: 0+1+2=3, inner: 3*2=6, total=9 */
    if (ok) PASS();
    else { char msg[64]; snprintf(msg, sizeof(msg), "got %lld exp 9", (long long)r); FAIL(msg); }
}

static void test_e2e_import_module(void)
{
    TEST("e2e: import/module/export parse");
    int ok;
    /* Module system stmts are no-ops at runtime; just verify they parse */
    int64_t r = run_vir(
        "module mymod\n"
        "import math\n"
        "func add(a, b) then\n"
        "  return a + b\n"
        "end\n"
        "export add\n"
        "func main() then\n"
        "  return add(10, 20)\n"
        "end\n", &ok);
    ok = ok && r == 30;
    if (ok) PASS();
    else { char msg[64]; snprintf(msg, sizeof(msg), "got %lld exp 30", (long long)r); FAIL(msg); }
}

static void test_e2e_from_import(void)
{
    TEST("e2e: from X import Y");
    int ok;
    int64_t r = run_vir(
        "from utils import helper, calc\n"
        "func main() then\n"
        "  return 42\n"
        "end\n", &ok);
    ok = ok && r == 42;
    if (ok) PASS();
    else { char msg[64]; snprintf(msg, sizeof(msg), "got %lld exp 42", (long long)r); FAIL(msg); }
}

static void test_e2e_import_as(void)
{
    TEST("e2e: import X as Y");
    int ok;
    int64_t r = run_vir(
        "import math as m\n"
        "func main() then\n"
        "  return 99\n"
        "end\n", &ok);
    ok = ok && r == 99;
    if (ok) PASS();
    else { char msg[64]; snprintf(msg, sizeof(msg), "got %lld exp 99", (long long)r); FAIL(msg); }
}

/* ── Include resolution tests ─────────────────────── */

/* Simple include reader that uses /tmp for test files */
static char *test_include_reader(const char *filename, size_t *out_len,
                                  void *user_data)
{
    (void)user_data;
    char path[512];
    snprintf(path, sizeof(path), "/tmp/vir_test_inc/%s", filename);
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

static void write_test_file(const char *name, const char *content)
{
    char path[512];
    snprintf(path, sizeof(path), "/tmp/vir_test_inc/%s", name);
    FILE *f = fopen(path, "w");
    if (f) { fputs(content, f); fclose(f); }
}

static int64_t run_vir_with_includes(const char *src, int *out_ok)
{
    vir_lexer_t *lex = malloc(sizeof(vir_lexer_t));
    if (!lex) { *out_ok = 0; return -9999; }
    lexer_init(lex, src, strlen(src));
    if (lexer_tokenize(lex) != 0) { *out_ok = 0; free(lex); return -9999; }

    vir_parser_t parser;
    parser_init(&parser, lex->tokens, lex->token_count);
    ast_node_t *ast = parser_parse_program(&parser);
    if (!ast) { *out_ok = 0; free(lex); return -9999; }

    lower_ctx_t ctx;
    lower_init(&ctx, "test");
    ctx.include_reader = test_include_reader;
    ctx.include_user_data = NULL;

    if (lower_resolve_includes(&ctx, ast) != 0) {
        ast_free(ast); lower_destroy(&ctx); free(lex);
        *out_ok = 0; return -9999;
    }
    if (lower_program(&ctx, ast) != 0) {
        ast_free(ast); lower_destroy(&ctx); free(lex);
        *out_ok = 0; return -9999;
    }
    for (uint32_t i = 0; i < ctx.module.func_count; i++)
        lower_tco_pass(&ctx.module.functions[i]);

    vm_state_t vm;
    vm_init(&vm);
    vm_status_t status = vm_exec_module(&vm, &ctx.module);

    int64_t result = vm_get_reg(&vm, 0);
    *out_ok = (status == VM_OK || status == VM_HALT) ? 1 : 0;
    vm_destroy(&vm);
    ast_free(ast);
    lower_destroy(&ctx);
    free(lex);
    return result;
}

static void test_e2e_include_basic(void)
{
    TEST("e2e: include loads file");
    /* Create temp dir + library file */
    system("mkdir -p /tmp/vir_test_inc");
    write_test_file("helpers.vri",
        "func double(x) then\n"
        "  return x * 2\n"
        "end\n");

    int ok;
    int64_t r = run_vir_with_includes(
        "include \"helpers.vri\"\n"
        "func main() then\n"
        "  return double(21)\n"
        "end\n", &ok);
    ok = ok && r == 42;
    if (ok) PASS();
    else { char msg[64]; snprintf(msg, sizeof(msg), "got %lld exp 42", (long long)r); FAIL(msg); }
}

static void test_e2e_include_multi(void)
{
    TEST("e2e: include multiple files");
    system("mkdir -p /tmp/vir_test_inc");
    write_test_file("add.vri",
        "func add(a, b) then\n"
        "  return a + b\n"
        "end\n");
    write_test_file("mul.vri",
        "func mul(a, b) then\n"
        "  return a * b\n"
        "end\n");

    int ok;
    int64_t r = run_vir_with_includes(
        "include \"add.vri\"\n"
        "include \"mul.vri\"\n"
        "func main() then\n"
        "  return add(mul(3, 4), 5)\n"
        "end\n", &ok);
    ok = ok && r == 17;  /* 3*4 + 5 = 17 */
    if (ok) PASS();
    else { char msg[64]; snprintf(msg, sizeof(msg), "got %lld exp 17", (long long)r); FAIL(msg); }
}

static void test_e2e_include_double_guard(void)
{
    TEST("e2e: include double-include guard");
    system("mkdir -p /tmp/vir_test_inc");
    write_test_file("lib.vri",
        "func lib_val() then\n"
        "  return 7\n"
        "end\n");

    int ok;
    /* Include same file twice — should not cause duplicate function error */
    int64_t r = run_vir_with_includes(
        "include \"lib.vri\"\n"
        "include \"lib.vri\"\n"
        "func main() then\n"
        "  return lib_val()\n"
        "end\n", &ok);
    ok = ok && r == 7;
    if (ok) PASS();
    else { char msg[64]; snprintf(msg, sizeof(msg), "got %lld exp 7", (long long)r); FAIL(msg); }
}

static void test_e2e_include_with_module(void)
{
    TEST("e2e: include + module/import combined");
    system("mkdir -p /tmp/vir_test_inc");
    write_test_file("mathlib.vri",
        "func square(x) then\n"
        "  return x * x\n"
        "end\n");

    int ok;
    int64_t r = run_vir_with_includes(
        "module myapp\n"
        "import utils as u\n"
        "include \"mathlib.vri\"\n"
        "func main() then\n"
        "  return square(5)\n"
        "end\n", &ok);
    ok = ok && r == 25;
    if (ok) PASS();
    else { char msg[64]; snprintf(msg, sizeof(msg), "got %lld exp 25", (long long)r); FAIL(msg); }
}

static void test_metadata_helper(void)
{
    TEST("ast_is_metadata helper");
    int ok = 1;
    ok = ok && ast_is_metadata(AST_MODULE) == 1;
    ok = ok && ast_is_metadata(AST_IMPORT) == 1;
    ok = ok && ast_is_metadata(AST_EXPORT) == 1;
    ok = ok && ast_is_metadata(AST_INCLUDE) == 1;
    ok = ok && ast_is_metadata(AST_ENUM_DEF) == 1;
    ok = ok && ast_is_metadata(AST_RECORD_DEF) == 1;
    ok = ok && ast_is_metadata(AST_FUNC_DEF) == 0;
    ok = ok && ast_is_metadata(AST_VAR_DECL) == 0;
    ok = ok && ast_is_metadata(AST_IF) == 0;
    ok = ok && ast_is_metadata(AST_BREAK) == 0;
    if (ok) PASS();
    else FAIL("metadata classification wrong");
}

static void test_process_imports(void)
{
    TEST("lower_process_imports populates tables");
    /* Build a small AST: module mymod; import math as m; from io import read, write */
    ast_node_t *prog = ast_new(AST_PROGRAM);

    ast_node_t *mod = ast_new(AST_MODULE);
    strncpy(mod->name, "mymod", AST_NAME_LEN);
    ast_add_child(prog, mod);

    ast_node_t *imp = ast_new(AST_IMPORT);
    strncpy(imp->name, "math", AST_NAME_LEN);
    strncpy(imp->name2, "m", AST_NAME_LEN);
    ast_add_child(prog, imp);

    ast_node_t *from = ast_new(AST_IMPORT);
    strncpy(from->name, "io", AST_NAME_LEN);
    ast_node_t *s1 = ast_new(AST_IDENTIFIER);
    strncpy(s1->name, "read", AST_NAME_LEN);
    ast_node_t *s2 = ast_new(AST_IDENTIFIER);
    strncpy(s2->name, "write", AST_NAME_LEN);
    ast_add_child(from, s1);
    ast_add_child(from, s2);
    ast_add_child(prog, from);

    lower_ctx_t ctx;
    lower_init(&ctx, "test");
    lower_process_imports(&ctx, prog);

    int ok = 1;
    ok = ok && strcmp(ctx.module.name, "mymod") == 0;
    ok = ok && ctx.module_alias_count == 1;
    ok = ok && strcmp(ctx.module_aliases[0].original, "math") == 0;
    ok = ok && strcmp(ctx.module_aliases[0].alias, "m") == 0;
    ok = ok && ctx.imported_sym_count == 2;
    ok = ok && strcmp(ctx.imported_syms[0].module, "io") == 0;
    ok = ok && strcmp(ctx.imported_syms[0].symbol, "read") == 0;
    ok = ok && strcmp(ctx.imported_syms[1].symbol, "write") == 0;

    if (ok) PASS();
    else FAIL("import table mismatch");
    ast_free(prog);
    lower_destroy(&ctx);
}

/* ═══════════════════════════════════════════════════════
 * Main
 * ═══════════════════════════════════════════════════════ */

int main(void)
{
    printf("\n╔═══════════════════════════════════════════╗\n");
    printf("║  Vir Engine – Native Core Tests           ║\n");
    printf("║  Version %d.%d.%d                            ║\n",
           VIR_VERSION_MAJOR, VIR_VERSION_MINOR, VIR_VERSION_PATCH);
    printf("╚═══════════════════════════════════════════╝\n\n");

    printf("── SHA-256 / HMAC ──────────────────────────\n");
    test_sha256_empty();
    test_sha256_abc();
    test_hmac_sha256();

    printf("\n── Code Signer ─────────────────────────────\n");
    test_signer_sign_verify();
    test_signer_tamper_detect();

    printf("\n── Q-IR ────────────────────────────────────\n");
    test_qir_create_module();

    printf("\n── VM ──────────────────────────────────────\n");
    test_vm_arithmetic();
    test_vm_multiply();

    printf("\n── Codegen ─────────────────────────────────\n");
    test_codegen_buffer();
    test_codegen_x86_add();
    test_codegen_arm64_add();

    printf("\n── Bridge ──────────────────────────────────\n");
    test_bridge_detect_os();
    test_bridge_jit_alloc();
    test_bridge_cpu_probe();
    test_bridge_alloc_executable();
    test_bridge_abi_get();

    printf("\n── Constraints ─────────────────────────────\n");
    test_constraints_type_get();
    test_constraints_type_size();
    test_constraints_op_add();
    test_constraints_check_pass();

    printf("\n── Intrinsics ──────────────────────────────\n");
    test_intrinsics_table_init();
    test_intrinsics_get_print();
    test_intrinsics_addr();
    test_intrinsics_opcode_map();

    printf("\n── JIT Bridge ──────────────────────────────\n");
    test_jit_bridge_init_destroy();
    test_jit_bridge_register_callback();
    test_jit_bridge_register_intrinsics();
    test_jit_bridge_emit_code();

    printf("\n── IR Lowering ─────────────────────────────\n");
    test_ir_lower_ast_create();
    test_ir_lower_sym_table();
    test_ir_lower_simple_program();
    test_ir_lower_regalloc();

    printf("\n── Rollback (Redundancy Patching) ──────────\n");
    test_jit_bridge_emit_dual();
    test_jit_bridge_patch_and_rollback();
    test_jit_bridge_auto_rollback();

    printf("\n── Tail-Call Optimization ───────────────────\n");
    test_tco_basic();
    test_tco_no_tail();
    test_tco_multiple();

    printf("\n── Lexer ───────────────────────────────────\n");
    test_lexer_english_keywords();
    test_lexer_vietnamese_keywords();
    test_lexer_operators();
    test_lexer_strings_numbers();

    printf("\n── Parser ──────────────────────────────────\n");
    test_parser_simple_func();
    test_parser_if_else();
    test_parser_expression_precedence();

    printf("\n── End-to-End Pipeline ─────────────────────\n");
    test_e2e_vm_simple();
    test_e2e_vm_if_else();
    test_e2e_vm_loop();

    printf("\n── Codegen Full ────────────────────────────\n");
    test_codegen_full_branches();

    printf("\n── Codegen Full2 (Phase 1) ─────────────────\n");
    test_codegen_full2_bitwise();
    test_codegen_full2_globals();
    test_codegen_full2_intrinsic_calls();
    test_codegen_full2_shift_mod();
    test_intrinsics_phase1();

    printf("\n── Blacklist (PERMANENT_SAFE) ──────────────\n");
    test_blacklist_threshold();

    printf("\n── VM Array/String/Memory Opcodes ──────────\n");
    test_vm_array_ops();
    test_vm_array_set();
    test_vm_string_ops();
    test_vm_string_cat();
    test_vm_memory_ops();
    test_vm_word_ops();
    test_vm_i_to_str();

    printf("\n── E2E New Features ────────────────────────\n");
    test_e2e_bitwise();
    test_e2e_array_literal();
    test_e2e_array_builtin();
    test_e2e_string_len();
    test_e2e_index_assign();

    printf("\n── E2E Phase 1B: For/Enum/Record ───────────\n");
    test_e2e_for_range();
    test_e2e_for_range_vi();
    test_e2e_enum_basic();
    test_e2e_enum_auto();
    test_e2e_enum_explicit();
    test_e2e_record_basic();
    test_e2e_record_assign();
    test_e2e_record_3field();
    test_e2e_enum_record_combined();
    test_e2e_for_array();

    printf("\n── E2E Phase 4 Prep: Break/Continue/Module ─\n");
    test_e2e_break();
    test_e2e_continue();
    test_e2e_break_nested();
    test_e2e_import_module();
    test_e2e_from_import();
    test_e2e_import_as();

    printf("\n── Include Resolution ───────────────────────\n");
    test_e2e_include_basic();
    test_e2e_include_multi();
    test_e2e_include_double_guard();
    test_e2e_include_with_module();

    printf("\n── Module System Internals ──────────────────\n");
    test_metadata_helper();
    test_process_imports();

    printf("\n═══════════════════════════════════════════\n");
    printf("Results: %d / %d passed\n", tests_passed, tests_run);
    printf("═══════════════════════════════════════════\n\n");

    return (tests_passed == tests_run) ? 0 : 1;
}
