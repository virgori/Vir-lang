#ifndef VIR_LANG_H
#define VIR_LANG_H

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    VIR_LANG_NONE = 0,
    VIR_LANG_VI,   /* Vietnamese (Tiếng Việt) */
    VIR_LANG_ZH,   /* Simplified Chinese (中文) */
    VIR_LANG_JA,   /* Japanese (日本語) */
    VIR_LANG_KO,   /* Korean (한국어) */
} vir_lang_t;

/*
 * Load language-specific keyword aliases and stop words.
 * This internally calls vir_register_keyword(), vir_register_multi_keyword(),
 * and vir_register_stop_word().
 * Returns 0 on success.
 */
int vir_lang_load(vir_lang_t lang);

/*
 * Clears the dynamic keyword registry.
 */
void vir_lang_unload_all(void);

/* Internal load functions for specific languages */
int vir_lang_load_vi(void);
int vir_lang_load_zh(void);
int vir_lang_load_ja(void);
int vir_lang_load_ko(void);

#ifdef __cplusplus
}
#endif

#endif /* VIR_LANG_H */
