/*
 * vir.h – Quizz-Core Engine: Master Header
 * ==========================================
 * Cú pháp Tiếng Việt · Lõi máy trừu tượng Q-IR · Tự vá mã máy
 *
 * This is the top-level include for the Vir native core.
 */

#ifndef VIR_H
#define VIR_H

#include "q_ir.h"
#include "vm.h"
#include "codegen.h"
#include "patcher.h"
#include "bridge.h"
#include "signer.h"
#include "constraints.h"
#include "intrinsics.h"
#include "jit_bridge.h"
#include "ir_lower.h"

/* ── Library version ─────────────────────────────────── */
#define VIR_VERSION_MAJOR 0
#define VIR_VERSION_MINOR 1
#define VIR_VERSION_PATCH 0
#define VIR_VERSION_STRING "0.1.0"

/* ── Export macro (shared library) ───────────────────── */
#ifdef _WIN32
  #ifdef VIR_BUILD_DLL
    #define VIR_API __declspec(dllexport)
  #else
    #define VIR_API __declspec(dllimport)
  #endif
#else
  #define VIR_API __attribute__((visibility("default")))
#endif

/* ── Top-level lifecycle ─────────────────────────────── */
#ifdef __cplusplus
extern "C" {
#endif

VIR_API int  vir_init(void);
VIR_API void vir_shutdown(void);
VIR_API const char* vir_version(void);

#ifdef __cplusplus
}
#endif

#endif /* VIR_H */
