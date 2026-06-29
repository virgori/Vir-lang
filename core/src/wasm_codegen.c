#include "vir.h"
#include <stddef.h>
#include <stdint.h>
#include "q_ir.h"
int codegen_emit_wasm(const q_module_t *module, uint8_t **out_buf, size_t *out_len) {
    (void)module; (void)out_buf; (void)out_len;
    return -1; /* Not implemented in bootstrap dummy */
}
