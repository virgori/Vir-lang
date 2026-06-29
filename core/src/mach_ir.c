#include "mach_ir.h"
#include <stdlib.h>
#include <string.h>

mach_func_t* mach_create_func(uint32_t id) {
    mach_func_t *f = malloc(sizeof(mach_func_t));
    f->id = id;
    f->blocks = NULL;
    return f;
}

mach_block_t* mach_create_block(mach_func_t *func) {
    mach_block_t *b = malloc(sizeof(mach_block_t));
    memset(b, 0, sizeof(mach_block_t));
    
    // Auto-assign ID simply
    if (!func->blocks) {
        b->id = 0;
        func->blocks = b;
    } else {
        mach_block_t *curr = func->blocks;
        while (curr->next) curr = curr->next;
        b->id = curr->id + 1;
        curr->next = b;
    }
    return b;
}

mach_instr_t* mach_append_instr(mach_block_t *block, mach_opcode_t op) {
    mach_instr_t *instr = malloc(sizeof(mach_instr_t));
    memset(instr, 0, sizeof(mach_instr_t));
    instr->op = op;
    
    if (!block->head) {
        block->head = instr;
        block->tail = instr;
    } else {
        instr->prev = block->tail;
        block->tail->next = instr;
        block->tail = instr;
    }
    return instr;
}

void mach_free_func(mach_func_t *func) {
    if (!func) return;
    
    mach_block_t *b = func->blocks;
    while (b) {
        mach_instr_t *i = b->head;
        while (i) {
            mach_instr_t *next = i->next;
            free(i);
            i = next;
        }
        mach_block_t *next_b = b->next;
        free(b);
        b = next_b;
    }
    free(func);
}
