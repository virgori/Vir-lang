/*
 * vir.c – Top-level lifecycle API
 * ================================
 * Implements vir_init(), vir_shutdown(), vir_version()
 * declared in vir.h.
 */

#include "vir.h"
#include <string.h>

/* ── Global engine state ──────────────────────────────── */
static int g_initialized = 0;

int vir_init(void)
{
    if (g_initialized) return 0;   /* idempotent */
    g_initialized = 1;
    return 0;
}

void vir_shutdown(void)
{
    if (!g_initialized) return;
    g_initialized = 0;
}

const char* vir_version(void)
{
    return VIR_VERSION_STRING;
}
