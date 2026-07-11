#ifndef VIR_HIR_H
#define VIR_HIR_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    HIR_INTRINSIC_CALL,
    HIR_CALL,
    HIR_RETURN,
    HIR_IF,
    HIR_LOOP,
    HIR_BLOCK,
    HIR_CONST,
    HIR_LOAD,
    HIR_STORE,
    HIR_BREAK,
    HIR_CONTINUE,
    HIR_BINOP,
    HIR_VAR_DECL,
    HIR_PRINT,
} hir_kind_t;

typedef struct hir_node {
    hir_kind_t kind;
    uint32_t type_id;

    union {
        struct {
            uint32_t intrinsic_id;
            struct hir_node** args;
            uint32_t argc;
        } intrinsic_call;
        struct {
            struct hir_node* callee;
            struct hir_node** args;
            uint32_t argc;
        } call;
        struct {
            struct hir_node* value;
        } ret;
        struct {
            struct hir_node* cond;
            struct hir_node* then_block;
            struct hir_node* else_block;
        } if_stmt;
        struct {
            struct hir_node** body;
            uint32_t count;
        } block;
        struct {
            int64_t value;
        } constant;
        struct {
            uint32_t var_id;
        } load;
        struct {
            uint32_t var_id;
            struct hir_node* value;
        } store;
        struct {
            uint32_t op; // Opcode (e.g. OP_ADD)
            struct hir_node* left;
            struct hir_node* right;
        } binop;
        struct {
            uint32_t var_id;
            struct hir_node* init_value;
        } var_decl;
        struct {
            struct hir_node* value;
        } print;
    } as;
} hir_node_t;

/* Helper Functions */
hir_node_t* hir_create_node(hir_kind_t kind, uint32_t type_id);
void hir_free_node(hir_node_t* node);

#ifdef __cplusplus
}
#endif

#endif // VIR_HIR_H
