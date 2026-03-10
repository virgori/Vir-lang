/*
 * bridge.h – OS Bridge API
 * =========================
 * Spec §4.1 – Tự động chọn "Cổng lách" tùy theo môi trường:
 *   Linux:   mmap + mprotect
 *   macOS:   mmap(MAP_JIT) + pthread_jit_write_protect_np
 *   Windows: VirtualAlloc + VirtualProtect
 */

#ifndef VIR_BRIDGE_H
#define VIR_BRIDGE_H

#include <stdint.h>
#include <stddef.h>
#include "codegen.h"

#ifdef __cplusplus
extern "C" {
#endif

/* ═══════════════════════════════════════════════════════
 * OS Detection
 * ═══════════════════════════════════════════════════════ */
typedef enum {
    OS_LINUX   = 1,
    OS_MACOS   = 2,
    OS_WINDOWS = 3,
    OS_UNKNOWN = 0,
} os_type_t;

os_type_t bridge_detect_os(void);

/* ═══════════════════════════════════════════════════════
 * Memory permissions
 * ═══════════════════════════════════════════════════════ */
#define BRIDGE_PROT_READ   0x01
#define BRIDGE_PROT_WRITE  0x02
#define BRIDGE_PROT_EXEC   0x04

/* ═══════════════════════════════════════════════════════
 * JIT Memory Management
 * ═══════════════════════════════════════════════════════ */

/* Allocate memory suitable for JIT code execution */
void* bridge_jit_alloc(size_t size);

/* Free JIT memory */
void bridge_jit_free(void *ptr, size_t size);

/* Change memory protection */
int bridge_mprotect(void *addr, size_t size, int prot);

/* macOS-specific: toggle JIT write protection (§4.1) */
void bridge_jit_write_protect(int enable);

/* ═══════════════════════════════════════════════════════
 * CPU Information (§3.1)
 * ═══════════════════════════════════════════════════════ */

typedef struct {
    target_arch_t arch;
    uint32_t      total_gp_regs;      /* Total general-purpose registers */
    uint32_t      estimated_free;     /* N_free                          */
    double        cpu_load_percent;
    int           high_perf_mode;     /* 1 if should use register mode   */
} cpu_state_t;

int bridge_probe_cpu(cpu_state_t *state);
int bridge_get_cpu_count(void);
double bridge_get_load_avg(void);
uint32_t bridge_get_gp_register_count(void);

/* ═══════════════════════════════════════════════════════
 * Instruction Cache Flush (Critical for ARM64 self-patching)
 * ═══════════════════════════════════════════════════════
 * After writing machine code into JIT memory, the CPU may
 * still execute stale code from L1 ICache.  This forces
 * synchronisation between D-cache and I-cache.
 */
void bridge_flush_icache(void *addr, size_t size);

/* ═══════════════════════════════════════════════════════
 * Page-aligned Executable Allocation
 * ═══════════════════════════════════════════════════════ */
void *bridge_alloc_executable(size_t size);          /* RW, page-aligned  */
int   bridge_make_executable(void *addr, size_t sz); /* RW → RX           */
int   bridge_make_writable(void *addr, size_t sz);   /* RX → RW           */

/* ═══════════════════════════════════════════════════════
 * ABI Register Mapping  (System V / Apple AAPCS64)
 * ═══════════════════════════════════════════════════════
 * Maps abstract roles (return value, arg0-arg5, stack ptr,
 * frame ptr) to physical registers for each architecture.
 */

typedef enum {
    ABI_ROLE_RET   = 0,   /* Return value           */
    ABI_ROLE_ARG0  = 1,
    ABI_ROLE_ARG1  = 2,
    ABI_ROLE_ARG2  = 3,
    ABI_ROLE_ARG3  = 4,
    ABI_ROLE_ARG4  = 5,
    ABI_ROLE_ARG5  = 6,
    ABI_ROLE_SP    = 7,   /* Stack pointer          */
    ABI_ROLE_FP    = 8,   /* Frame pointer          */
    ABI_ROLE_LR    = 9,   /* Link register (ARM64)  */
    ABI_ROLE_COUNT = 10,
} abi_role_t;

typedef struct {
    target_arch_t arch;
    uint8_t       reg[ABI_ROLE_COUNT];  /* Physical register id per role */
    uint8_t       caller_saved[32];     /* Caller-saved register set     */
    uint8_t       caller_saved_count;
    uint8_t       callee_saved[32];     /* Callee-saved register set     */
    uint8_t       callee_saved_count;
    uint8_t       max_int_args;         /* Max integer args in registers */
} abi_info_t;

/* Get ABI descriptor for detected (or given) architecture */
const abi_info_t *bridge_get_abi(target_arch_t arch);

#ifdef __cplusplus
}
#endif

#endif /* VIR_BRIDGE_H */
