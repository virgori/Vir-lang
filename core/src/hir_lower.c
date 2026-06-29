#include "hir_lower.h"
#include <stdlib.h>
#include <string.h>

// Simple symbol table for variable tracking in HIR
typedef struct hir_sym {
    char name[AST_NAME_LEN];
    uint32_t var_id;
    struct hir_sym* next;
} hir_sym_t;

typedef struct {
    hir_sym_t* locals;
    uint32_t next_var_id;
} hir_lower_ctx_t;

static uint32_t resolve_or_create_var(hir_lower_ctx_t* ctx, const char* name) {
    if (!name || !name[0]) return 0;
    hir_sym_t* curr = ctx->locals;
    while (curr) {
        if (strcmp(curr->name, name) == 0) return curr->var_id;
        curr = curr->next;
    }
    hir_sym_t* sym = (hir_sym_t*)malloc(sizeof(hir_sym_t));
    strncpy(sym->name, name, AST_NAME_LEN - 1);
    sym->name[AST_NAME_LEN - 1] = '\0';
    sym->var_id = ++ctx->next_var_id;
    sym->next = ctx->locals;
    ctx->locals = sym;
    return sym->var_id;
}

static void free_ctx(hir_lower_ctx_t* ctx) {
    hir_sym_t* curr = ctx->locals;
    while (curr) {
        hir_sym_t* next = curr->next;
        free(curr);
        curr = next;
    }
}

static hir_node_t* lower_node(hir_lower_ctx_t* ctx, const ast_node_t* ast) {
    if (!ast) return NULL;

    hir_node_t* hir = NULL;

    switch (ast->type) {
        case AST_BLOCK: {
            hir = hir_create_node(HIR_BLOCK, 0);
            if (ast->child_count > 0) {
                hir->as.block.body = (hir_node_t**)malloc(ast->child_count * sizeof(hir_node_t*));
                hir->as.block.count = ast->child_count;
                for (uint32_t i = 0; i < ast->child_count; i++) {
                    hir->as.block.body[i] = lower_node(ctx, ast->children[i]);
                }
            }
            break;
        }
        case AST_IF: {
            hir = hir_create_node(HIR_IF, 0);
            hir->as.if_stmt.cond = lower_node(ctx, ast->children[0]);
            hir->as.if_stmt.then_block = lower_node(ctx, ast->children[1]);
            if (ast->child_count > 2) {
                hir->as.if_stmt.else_block = lower_node(ctx, ast->children[2]);
            }
            break;
        }
        case AST_VAR_DECL: {
            hir = hir_create_node(HIR_VAR_DECL, 0);
            hir->as.var_decl.var_id = resolve_or_create_var(ctx, ast->name);
            if (ast->child_count > 0) {
                hir->as.var_decl.init_value = lower_node(ctx, ast->children[0]);
            }
            break;
        }
        case AST_WHILE:
        case AST_LOOP: {
            hir = hir_create_node(HIR_LOOP, 0);
            
            uint32_t body_idx = (ast->child_count > 1) ? 1 : 0;
            hir_node_t* body = NULL;
            if (ast->children[body_idx] && ast->children[body_idx]->type == AST_BLOCK) {
                const ast_node_t* b = ast->children[body_idx];
                body = hir_create_node(HIR_BLOCK, 0);
                body->as.block.body = (hir_node_t**)malloc(b->child_count * sizeof(hir_node_t*));
                body->as.block.count = b->child_count;
                for (uint32_t i = 0; i < b->child_count; i++) {
                    body->as.block.body[i] = lower_node(ctx, b->children[i]);
                }
            } else {
                body = hir_create_node(HIR_BLOCK, 0); // Empty body
            }

            if (ast->type == AST_WHILE && ast->child_count > 1) {
                // Desugar: loop { if cond { body } else { break } }
                hir_node_t* if_stmt = hir_create_node(HIR_IF, 0);
                if_stmt->as.if_stmt.cond = lower_node(ctx, ast->children[0]);
                if_stmt->as.if_stmt.then_block = body;
                if_stmt->as.if_stmt.else_block = hir_create_node(HIR_BREAK, 0);
                
                hir->as.block.body = (hir_node_t**)malloc(sizeof(hir_node_t*));
                hir->as.block.count = 1;
                hir->as.block.body[0] = if_stmt;
            } else {
                // Infinite loop: loop { body }
                hir->as.block.body = (hir_node_t**)malloc(sizeof(hir_node_t*));
                hir->as.block.count = 1;
                hir->as.block.body[0] = body;
            }
            break;
        }
        case AST_FOR_RANGE: {
            // For range is more complex, we'll desugar it to an infinite loop with counter
            // AST_FOR_RANGE children: [0] = start, [1] = end, [2] = step (optional), [3] = body (or [2] if step missing)
            hir = hir_create_node(HIR_BLOCK, 0);
            // ... (A simplified desugaring for demonstration of Phase 2 LIR draft)
            hir->as.block.count = 1;
            hir->as.block.body = (hir_node_t**)malloc(sizeof(hir_node_t*));
            
            hir_node_t* loop = hir_create_node(HIR_LOOP, 0);
            
            uint32_t body_idx = (ast->child_count > 3) ? 3 : (ast->child_count > 2 ? 2 : 1);
            hir_node_t* body = hir_create_node(HIR_BLOCK, 0);
            if (ast->children[body_idx] && ast->children[body_idx]->type == AST_BLOCK) {
                const ast_node_t* b = ast->children[body_idx];
                body->as.block.body = (hir_node_t**)malloc(b->child_count * sizeof(hir_node_t*));
                body->as.block.count = b->child_count;
                for (uint32_t i = 0; i < b->child_count; i++) {
                    body->as.block.body[i] = lower_node(ctx, b->children[i]);
                }
            }
            loop->as.block.body = (hir_node_t**)malloc(sizeof(hir_node_t*));
            loop->as.block.count = 1;
            loop->as.block.body[0] = body;
            
            hir->as.block.body[0] = loop;
            break;
        }
        case AST_BREAK: {
            hir = hir_create_node(HIR_BREAK, 0);
            break;
        }
        case AST_CONTINUE:
        case AST_SKIP: {
            hir = hir_create_node(HIR_CONTINUE, 0);
            break;
        }
        case AST_RETURN:
        case AST_OUT: {
            hir = hir_create_node(HIR_RETURN, 0);
            if (ast->child_count > 0) {
                hir->as.ret.value = lower_node(ctx, ast->children[0]);
            }
            break;
        }
        case AST_LITERAL_INT: {
            hir = hir_create_node(HIR_CONST, 0);
            hir->as.constant.value = ast->int_val;
            break;
        }
        case AST_IDENTIFIER: {
            hir = hir_create_node(HIR_LOAD, 0);
            hir->as.load.var_id = resolve_or_create_var(ctx, ast->name);
            break;
        }
        case AST_ASSIGN: {
            hir = hir_create_node(HIR_STORE, 0);
            // In AST_ASSIGN, child[0] is the variable (AST_IDENTIFIER), child[1] is the value
            if (ast->child_count > 0 && ast->children[0]->type == AST_IDENTIFIER) {
                hir->as.store.var_id = resolve_or_create_var(ctx, ast->children[0]->name);
            } else {
                hir->as.store.var_id = 0;
            }
            // children[0] is the binop or value (Wait! parser desugars `x += v` to `AST_ASSIGN(AST_BINOP(x, v))`)
            // Actually, parser says:
            // assign->name = x;
            // ast_add_child(assign, bin);
            // So ast->children[0] is the value to store.
            if (ast->child_count > 0) {
                hir->as.store.value = lower_node(ctx, ast->children[0]);
            }
            break;
        }
        case AST_BINOP:
        case AST_COMPARE: {
            hir = hir_create_node(HIR_BINOP, 0);
            hir->as.binop.op = ast->op;
            if (ast->child_count > 0) {
                hir->as.binop.left = lower_node(ctx, ast->children[0]);
            }
            if (ast->child_count > 1) {
                hir->as.binop.right = lower_node(ctx, ast->children[1]);
            }
            break;
        }
        case AST_CALL: {
            hir = hir_create_node(HIR_CALL, 0);
            if (ast->child_count > 0) {
                hir->as.call.callee = lower_node(ctx, ast->children[0]);
                hir->as.call.argc = ast->child_count - 1;
                if (hir->as.call.argc > 0) {
                    hir->as.call.args = (hir_node_t**)malloc(hir->as.call.argc * sizeof(hir_node_t*));
                    for (uint32_t i = 0; i < hir->as.call.argc; i++) {
                        hir->as.call.args[i] = lower_node(ctx, ast->children[i + 1]);
                    }
                }
            }
            break;
        }
        case AST_FUNC_DEF: {
            uint32_t body_idx = 0;
            for (uint32_t i = 0; i < ast->child_count; i++) {
                if (ast->children[i]->type == AST_BLOCK) {
                    body_idx = i;
                    break;
                }
            }
            if (ast->child_count > body_idx) {
                hir = lower_node(ctx, ast->children[body_idx]);
            } else {
                hir = hir_create_node(HIR_BLOCK, 0);
            }
            break;
        }
        case AST_PROGRAM: {
            hir = hir_create_node(HIR_BLOCK, 0);
            hir->as.block.body = (hir_node_t**)malloc(ast->child_count * sizeof(hir_node_t*));
            hir->as.block.count = ast->child_count;
            for (uint32_t i = 0; i < ast->child_count; i++) {
                hir->as.block.body[i] = lower_node(ctx, ast->children[i]);
            }
            break;
        }
        default:
            hir = hir_create_node(HIR_BLOCK, 0);
            break;
    }

    return hir;
}

hir_node_t* lower_ast_to_hir(const ast_node_t* ast) {
    hir_lower_ctx_t ctx = { NULL, 0 };
    hir_node_t* hir = lower_node(&ctx, ast);
    free_ctx(&ctx);
    return hir;
}
