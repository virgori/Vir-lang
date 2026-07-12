#include "hir_lower.h"
#include <stdlib.h>
#include <string.h>

typedef struct {
    lower_ctx_t *lctx;
} hir_lower_ctx_t;

static uint32_t resolve_var(hir_lower_ctx_t *ctx, const char *name) {
    if (!name || !name[0])
        return 0;
    uint32_t vreg = 0;
    if (ctx->lctx && lower_lookup_local_vreg(ctx->lctx, name, &vreg) == 0)
        return vreg;
    return 0;
}

static hir_node_t *lower_node(hir_lower_ctx_t *ctx, const ast_node_t *ast);

static hir_node_t *lower_node(hir_lower_ctx_t *ctx, const ast_node_t *ast) {
    if (!ast)
        return NULL;

    hir_node_t *hir = NULL;

    switch (ast->type) {
        case AST_BLOCK: {
            if (ast->child_count == 0) {
                hir = hir_create_node(HIR_BLOCK, 0);
                break;
            }
            hir_node_t **body =
                (hir_node_t **)malloc(ast->child_count * sizeof(hir_node_t *));
            uint32_t count = 0;
            for (uint32_t i = 0; i < ast->child_count; i++) {
                hir_node_t *child = lower_node(ctx, ast->children[i]);
                if (!child) {
                    free(body);
                    return NULL;
                }
                body[count++] = child;
            }
            hir = hir_create_node(HIR_BLOCK, 0);
            hir->as.block.body = body;
            hir->as.block.count = count;
            break;
        }
        case AST_IF: {
            hir_node_t *cond = lower_node(ctx, ast->children[0]);
            hir_node_t *then_block = lower_node(ctx, ast->children[1]);
            hir_node_t *else_block = NULL;
            if (ast->child_count > 2)
                else_block = lower_node(ctx, ast->children[2]);
            if (!cond || !then_block)
                return NULL;
            hir = hir_create_node(HIR_IF, 0);
            hir->as.if_stmt.cond = cond;
            hir->as.if_stmt.then_block = then_block;
            hir->as.if_stmt.else_block = else_block;
            break;
        }
        case AST_VAR_DECL:
        case AST_CONST_DECL:
            /* Tuple destructuring needs legacy lower_stmt (sym_define + Q_ARR_GET). */
            if (ast->int_val & 0x4000)
                return NULL;
            /* Fallback: tuple names live in children when decl->name is empty. */
            if (!ast->name[0] && ast->child_count > 0 &&
                ast->children[0] &&
                ast->children[0]->type == AST_IDENTIFIER)
                return NULL;
            if (ast->type == AST_CONST_DECL)
                return NULL;
            {
                uint32_t vreg = 0;
                if (ctx->lctx &&
                    lower_lookup_local_vreg(ctx->lctx, ast->name, &vreg) != 0 &&
                    lower_declare_var(ctx->lctx, ast->name, &vreg) != 0)
                    return NULL;
                hir = hir_create_node(HIR_VAR_DECL, 0);
                hir->as.var_decl.var_id = vreg;
                if (ast->child_count > 0) {
                    hir->as.var_decl.init_value =
                        lower_node(ctx, ast->children[0]);
                    if (ast->children[0] && !hir->as.var_decl.init_value)
                        return NULL;
                }
            }
            break;
        case AST_FIELD_ASSIGN:
        case AST_INDEX_ASSIGN:
            return NULL;
        case AST_WHILE:
        case AST_LOOP: {
            hir = hir_create_node(HIR_LOOP, 0);

            uint32_t body_idx = (ast->child_count > 1) ? 1 : 0;
            hir_node_t *body = NULL;
            if (ast->children[body_idx] &&
                ast->children[body_idx]->type == AST_BLOCK) {
                const ast_node_t *b = ast->children[body_idx];
                body = hir_create_node(HIR_BLOCK, 0);
                body->as.block.body =
                    (hir_node_t **)malloc(b->child_count * sizeof(hir_node_t *));
                body->as.block.count = b->child_count;
                for (uint32_t i = 0; i < b->child_count; i++) {
                    body->as.block.body[i] = lower_node(ctx, b->children[i]);
                    if (b->children[i] && !body->as.block.body[i]) {
                        hir_free_node(body);
                        return NULL;
                    }
                }
            } else {
                body = hir_create_node(HIR_BLOCK, 0);
            }

            if (ast->type == AST_WHILE && ast->child_count > 1) {
                hir_node_t *if_stmt = hir_create_node(HIR_IF, 0);
                if_stmt->as.if_stmt.cond = lower_node(ctx, ast->children[0]);
                if (ast->children[0] && !if_stmt->as.if_stmt.cond) {
                    hir_free_node(body);
                    hir_free_node(hir);
                    return NULL;
                }
                if_stmt->as.if_stmt.then_block = body;
                if_stmt->as.if_stmt.else_block = hir_create_node(HIR_BREAK, 0);

                hir->as.block.body = (hir_node_t **)malloc(sizeof(hir_node_t *));
                hir->as.block.count = 1;
                hir->as.block.body[0] = if_stmt;
            } else {
                hir->as.block.body = (hir_node_t **)malloc(sizeof(hir_node_t *));
                hir->as.block.count = 1;
                hir->as.block.body[0] = body;
            }
            break;
        }
        case AST_FOR_RANGE: {
            hir = hir_create_node(HIR_BLOCK, 0);
            hir->as.block.count = 1;
            hir->as.block.body = (hir_node_t **)malloc(sizeof(hir_node_t *));

            hir_node_t *loop = hir_create_node(HIR_LOOP, 0);

            uint32_t body_idx =
                (ast->child_count > 3) ? 3 : (ast->child_count > 2 ? 2 : 1);
            hir_node_t *body = hir_create_node(HIR_BLOCK, 0);
            if (ast->children[body_idx] &&
                ast->children[body_idx]->type == AST_BLOCK) {
                const ast_node_t *b = ast->children[body_idx];
                body->as.block.body =
                    (hir_node_t **)malloc(b->child_count * sizeof(hir_node_t *));
                body->as.block.count = b->child_count;
                for (uint32_t i = 0; i < b->child_count; i++) {
                    body->as.block.body[i] = lower_node(ctx, b->children[i]);
                    if (b->children[i] && !body->as.block.body[i]) {
                        hir_free_node(body);
                        hir_free_node(loop);
                        hir_free_node(hir);
                        return NULL;
                    }
                }
            }
            loop->as.block.body = (hir_node_t **)malloc(sizeof(hir_node_t *));
            loop->as.block.count = 1;
            loop->as.block.body[0] = body;

            hir->as.block.body[0] = loop;
            break;
        }
        case AST_BREAK:
            hir = hir_create_node(HIR_BREAK, 0);
            break;
        case AST_CONTINUE:
        case AST_SKIP:
            hir = hir_create_node(HIR_CONTINUE, 0);
            break;
        case AST_RETURN:
        case AST_OUT:
            /* Multi-value `out (a, b, c)` lowers to tuple array via legacy path. */
            if (ast->child_count > 0 &&
                ast->children[0]->type == AST_TUPLE_LITERAL)
                return NULL;
            hir = hir_create_node(HIR_RETURN, 0);
            if (ast->child_count > 0) {
                hir->as.ret.value = lower_node(ctx, ast->children[0]);
                if (ast->children[0] && !hir->as.ret.value)
                    return NULL;
            }
            break;
        case AST_LITERAL_INT:
            hir = hir_create_node(HIR_CONST, 0);
            hir->as.constant.value = ast->int_val;
            break;
        case AST_IDENTIFIER: {
            uint32_t vreg = resolve_var(ctx, ast->name);
            if (!vreg && ast->name[0])
                return NULL;
            hir = hir_create_node(HIR_LOAD, 0);
            hir->as.load.var_id = vreg;
            break;
        }
        case AST_ASSIGN: {
            uint32_t vreg = resolve_var(ctx, ast->name);
            if (!vreg && ast->name[0])
                return NULL;
            hir = hir_create_node(HIR_STORE, 0);
            hir->as.store.var_id = vreg;
            if (ast->child_count > 0) {
                hir->as.store.value = lower_node(ctx, ast->children[0]);
                if (ast->child_count > 0 && ast->children[0] && !hir->as.store.value)
                    return NULL;
            }
            break;
        }
        case AST_BINOP:
        case AST_COMPARE: {
            hir_node_t *left = NULL;
            hir_node_t *right = NULL;
            if (ast->child_count > 0)
                left = lower_node(ctx, ast->children[0]);
            if (ast->child_count > 1)
                right = lower_node(ctx, ast->children[1]);
            if ((ast->child_count > 0 && ast->children[0] && !left) ||
                (ast->child_count > 1 && ast->children[1] && !right))
                return NULL;
            hir = hir_create_node(HIR_BINOP, 0);
            hir->as.binop.op = ast->op;
            hir->as.binop.left = left;
            hir->as.binop.right = right;
            break;
        }
        case AST_CALL:
            /* Regular calls stay on HIR_CALL; builtins use legacy Q-IR opcodes. */
            if (ast->type == AST_CALL) {
                hir_node_t **args = NULL;
                if (ast->child_count > 0) {
                    args = (hir_node_t **)malloc(
                        ast->child_count * sizeof(hir_node_t *));
                    for (uint32_t i = 0; i < ast->child_count; i++) {
                        args[i] = lower_node(ctx, ast->children[i]);
                        if (ast->children[i] && !args[i]) {
                            free(args);
                            return NULL;
                        }
                    }
                }
                hir = hir_create_node(HIR_CALL, 0);
                strncpy(hir->as.call.callee_name, ast->name,
                        sizeof(hir->as.call.callee_name) - 1);
                hir->as.call.callee_name[sizeof(hir->as.call.callee_name) - 1] =
                    '\0';
                hir->as.call.argc = ast->child_count;
                hir->as.call.args = args;
            }
            break;
        case AST_BUILTIN_CALL: {
            hir_node_t **args = NULL;
            if (ast->child_count > 0) {
                args = (hir_node_t **)malloc(
                    ast->child_count * sizeof(hir_node_t *));
                for (uint32_t i = 0; i < ast->child_count; i++) {
                    args[i] = lower_node(ctx, ast->children[i]);
                    if (ast->children[i] && !args[i]) {
                        free(args);
                        return NULL;
                    }
                }
            }
            hir = hir_create_node(HIR_INTRINSIC_CALL, 0);
            hir->as.intrinsic_call.intrinsic_id = ast->builtin_id;
            strncpy(hir->as.intrinsic_call.callee_name, ast->name,
                    sizeof(hir->as.intrinsic_call.callee_name) - 1);
            hir->as.intrinsic_call.callee_name[
                sizeof(hir->as.intrinsic_call.callee_name) - 1] = '\0';
            hir->as.intrinsic_call.argc = ast->child_count;
            hir->as.intrinsic_call.args = args;
            break;
        }
        case AST_PRINT:
            hir = hir_create_node(HIR_PRINT, 0);
            if (ast->child_count > 0) {
                hir->as.print.value = lower_node(ctx, ast->children[0]);
                if (ast->children[0] && !hir->as.print.value)
                    return NULL;
            }
            break;
        case AST_LITERAL_FLOAT:
            hir = hir_create_node(HIR_CONST, 0);
            hir->as.constant.value = (int64_t)ast->float_val;
            break;
        case AST_LITERAL_STR:
            hir = hir_create_node(HIR_CONST, 0);
            hir->as.constant.is_string = 1;
            strncpy(hir->as.constant.str_value, ast->name,
                    sizeof(hir->as.constant.str_value) - 1);
            hir->as.constant.str_value[sizeof(hir->as.constant.str_value) - 1] =
                '\0';
            break;
        case AST_FIELD_ACCESS:
        case AST_SAFE_ACCESS: {
            if (ast->child_count < 1)
                return NULL;
            hir_node_t *base = lower_node(ctx, ast->children[0]);
            if (!base)
                return NULL;
            int offset = -1;
            if (ctx->lctx)
                offset = lower_record_field_offset(ctx->lctx, ast->children[0],
                                                   ast->name);
            if (offset < 0)
                return NULL;
            hir = hir_create_node(HIR_FIELD_LOAD, 0);
            hir->as.field_load.base = base;
            hir->as.field_load.offset = offset;
            break;
        }
        case AST_INDEX_ACCESS:
        case AST_TUPLE_LITERAL:
        case AST_ARRAY_LITERAL:
        case AST_MAP_LITERAL:
            return NULL;
        case AST_INPUT:
            hir = hir_create_node(HIR_INTRINSIC_CALL, 0);
            hir->as.intrinsic_call.intrinsic_id = 1;
            break;
        default:
            break;
    }

    return hir;
}

hir_node_t *lower_ast_to_hir(const ast_node_t *ast, lower_ctx_t *lctx) {
    hir_lower_ctx_t ctx = {lctx};
    return lower_node(&ctx, ast);
}
