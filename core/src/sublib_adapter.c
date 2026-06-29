#include "lexer.h"
#include "lang.h"

void vir_sublib_adapter_init(void) {
    /* Automatically load all supported languages to preserve backward compatibility */
    vir_lang_load(VIR_LANG_VI);
    vir_lang_load(VIR_LANG_ZH);
    vir_lang_load(VIR_LANG_JA);
    vir_lang_load(VIR_LANG_KO);
}
