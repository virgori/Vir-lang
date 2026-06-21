#include "hir.h"
#include <stdlib.h>
#include <string.h>

hir_node_t* hir_create_node(hir_kind_t kind, uint32_t type_id) {
    hir_node_t* node = (hir_node_t*)malloc(sizeof(hir_node_t));
    if (node) {
        memset(node, 0, sizeof(hir_node_t));
        node->kind = kind;
        node->type_id = type_id;
    }
    return node;
}

void hir_free_node(hir_node_t* node) {
    if (!node) return;
    
    switch (node->kind) {
        case HIR_INTRINSIC_CALL:
            if (node->as.intrinsic_call.args) {
                for (uint32_t i = 0; i < node->as.intrinsic_call.argc; i++) {
                    hir_free_node(node->as.intrinsic_call.args[i]);
                }
                free(node->as.intrinsic_call.args);
            }
            break;
        case HIR_CALL:
            if (node->as.call.callee) hir_free_node(node->as.call.callee);
            if (node->as.call.args) {
                for (uint32_t i = 0; i < node->as.call.argc; i++) {
                    hir_free_node(node->as.call.args[i]);
                }
                free(node->as.call.args);
            }
            break;
        case HIR_RETURN:
            if (node->as.ret.value) hir_free_node(node->as.ret.value);
            break;
        case HIR_IF:
            if (node->as.if_stmt.cond) hir_free_node(node->as.if_stmt.cond);
            if (node->as.if_stmt.then_block) hir_free_node(node->as.if_stmt.then_block);
            if (node->as.if_stmt.else_block) hir_free_node(node->as.if_stmt.else_block);
            break;
        case HIR_LOOP:
        case HIR_BLOCK:
            if (node->as.block.body) {
                for (uint32_t i = 0; i < node->as.block.count; i++) {
                    hir_free_node(node->as.block.body[i]);
                }
                free(node->as.block.body);
            }
            break;
        case HIR_STORE:
            if (node->as.store.value) hir_free_node(node->as.store.value);
            break;
        case HIR_CONST:
        case HIR_LOAD:
            break; // No children to free
    }
    
    free(node);
}
