#include "lexer.h"

/*
 * Optional SubLib hook for C lexer keyword aliases.
 * Natural-language aliases live in stdlib/vir/lang/*.vri and are loaded via
 * `import` in user/compiler code — not wired into core or the compiler by default.
 */
void vir_sublib_adapter_init(void) {
}
