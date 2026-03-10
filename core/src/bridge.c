/*
 * bridge.c – OS-Specific JIT Memory Bridge
 * ═══════════════════════════════════════════
 * Spec §4.1 – Platform Abstraction Layer.
 *
 * Direct system calls for executable memory allocation:
 *   macOS:   mmap(MAP_JIT) + pthread_jit_write_protect_np
 *   Linux:   mmap + mprotect
 *   Windows: VirtualAlloc + VirtualProtect
 *
 * Also provides CPU pressure monitoring via sysctl/sysinfo.
 */

#include "bridge.h"
#include "codegen.h"
#include <stdio.h>
#include <string.h>

/* ═══════════════════════════════════════════════════════
 * OS Detection
 * ═══════════════════════════════════════════════════════ */

os_type_t bridge_detect_os(void)
{
#if defined(__APPLE__)
    return OS_MACOS;
#elif defined(__linux__)
    return OS_LINUX;
#elif defined(_WIN32)
    return OS_WINDOWS;
#else
    return OS_UNKNOWN;
#endif
}

/* ═══════════════════════════════════════════════════════
 * POSIX (macOS + Linux) Implementation
 * ═══════════════════════════════════════════════════════ */

#if defined(__APPLE__) || defined(__linux__)

#include <sys/mman.h>
#include <unistd.h>
#include <errno.h>

#if defined(__APPLE__)
#include <pthread.h>
#include <mach/mach.h>
#include <mach/mach_host.h>
#include <sys/sysctl.h>
#ifndef MAP_JIT
#define MAP_JIT 0x0800
#endif
#endif

#if defined(__linux__)
#include <sys/sysinfo.h>
#endif

void *bridge_jit_alloc(size_t size)
{
    int flags = MAP_PRIVATE | MAP_ANONYMOUS;
    int prot  = PROT_READ | PROT_WRITE;

#if defined(__APPLE__)
    flags |= MAP_JIT;
    prot  |= PROT_EXEC;
#endif

    void *ptr = mmap(NULL, size, prot, flags, -1, 0);
    if (ptr == MAP_FAILED) {
        fprintf(stderr, "[bridge] mmap failed: %s (errno=%d)\n",
                strerror(errno), errno);
        return NULL;
    }
    return ptr;
}

void bridge_jit_free(void *ptr, size_t size)
{
    if (ptr && ptr != MAP_FAILED) {
        munmap(ptr, size);
    }
}

int bridge_mprotect(void *addr, size_t size, int prot)
{
    int sys_prot = 0;
    if (prot & BRIDGE_PROT_READ)  sys_prot |= PROT_READ;
    if (prot & BRIDGE_PROT_WRITE) sys_prot |= PROT_WRITE;
    if (prot & BRIDGE_PROT_EXEC)  sys_prot |= PROT_EXEC;

    if (mprotect(addr, size, sys_prot) != 0) {
        fprintf(stderr, "[bridge] mprotect failed: %s\n", strerror(errno));
        return -1;
    }
    return 0;
}

void bridge_jit_write_protect(int enable)
{
#if defined(__APPLE__) && defined(__aarch64__)
    pthread_jit_write_protect_np(enable);
#else
    (void)enable;
#endif
}

/* ── CPU Helpers ──────────────────────────────────────── */

int bridge_get_cpu_count(void)
{
#if defined(__APPLE__)
    int ncpu = 0;
    size_t sz = sizeof(ncpu);
    if (sysctlbyname("hw.logicalcpu", &ncpu, &sz, NULL, 0) == 0)
        return ncpu;
    return 1;
#else
    return (int)sysconf(_SC_NPROCESSORS_ONLN);
#endif
}

double bridge_get_load_avg(void)
{
#if defined(__APPLE__)
    host_cpu_load_info_data_t cpuinfo;
    mach_msg_type_number_t count = HOST_CPU_LOAD_INFO_COUNT;
    if (host_statistics(mach_host_self(), HOST_CPU_LOAD_INFO,
                       (host_info_t)&cpuinfo, &count) == KERN_SUCCESS) {
        natural_t total = cpuinfo.cpu_ticks[CPU_STATE_USER]
                        + cpuinfo.cpu_ticks[CPU_STATE_SYSTEM]
                        + cpuinfo.cpu_ticks[CPU_STATE_IDLE]
                        + cpuinfo.cpu_ticks[CPU_STATE_NICE];
        if (total > 0) {
            natural_t busy = total - cpuinfo.cpu_ticks[CPU_STATE_IDLE];
            return (double)busy / (double)total * 100.0;
        }
    }
    return 0.0;
#elif defined(__linux__)
    FILE *f = fopen("/proc/loadavg", "r");
    if (f) {
        double load1;
        int ncpu = bridge_get_cpu_count();
        if (fscanf(f, "%lf", &load1) == 1) {
            fclose(f);
            double pct = (load1 / ncpu) * 100.0;
            return (pct > 100.0) ? 100.0 : pct;
        }
        fclose(f);
    }
    return 0.0;
#else
    return 0.0;
#endif
}

uint32_t bridge_get_gp_register_count(void)
{
#if defined(__aarch64__)
    return 31;  /* X0-X30 */
#elif defined(__x86_64__)
    return 16;  /* RAX-R15 */
#else
    return 8;
#endif
}

int bridge_probe_cpu(cpu_state_t *state)
{
    memset(state, 0, sizeof(*state));

    state->arch = codegen_detect_arch();
    state->total_gp_regs = bridge_get_gp_register_count();

    int ncpu = bridge_get_cpu_count();
    double load = bridge_get_load_avg();

    state->cpu_load_percent = load;
    state->estimated_free = (uint32_t)((100.0 - load) / 100.0 * ncpu);
    state->high_perf_mode = (state->estimated_free > 0) ? 1 : 0;

    return 0;
}

/* ── Instruction Cache Flush ─────────────────────────── */

void bridge_flush_icache(void *addr, size_t size)
{
#if defined(__APPLE__) && defined(__aarch64__)
    /* Use sys_icache_invalidate on macOS ARM64 */
    extern void sys_icache_invalidate(void *, size_t);
    sys_icache_invalidate(addr, size);
#elif defined(__aarch64__)
    /* Linux ARM64: iterate cache lines with DC CVAU + IC IVAU */
    const size_t line = 64;
    uint8_t *p = (uint8_t *)addr;
    uint8_t *end = p + size;
    for (; p < end; p += line) {
        __asm__ volatile("dc cvau, %0" : : "r"(p));
    }
    __asm__ volatile("dsb ish");
    p = (uint8_t *)addr;
    for (; p < end; p += line) {
        __asm__ volatile("ic ivau, %0" : : "r"(p));
    }
    __asm__ volatile("dsb ish; isb");
#elif defined(__x86_64__) || defined(_M_X64)
    /* x86_64: coherent I-cache, just need a serialising fence */
    (void)addr; (void)size;
    __asm__ volatile("mfence" ::: "memory");
#else
    (void)addr; (void)size;
#endif
}

/* ── Page-aligned Executable Allocation ──────────────── */

void *bridge_alloc_executable(size_t size)
{
    /* Round up to page boundary */
    size_t pgsz = (size_t)sysconf(_SC_PAGESIZE);
    size = (size + pgsz - 1) & ~(pgsz - 1);
    return bridge_jit_alloc(size);
}

int bridge_make_executable(void *addr, size_t size)
{
#if defined(__APPLE__) && defined(__aarch64__)
    /* MAP_JIT on Apple Silicon: toggle W^X to execute mode */
    bridge_jit_write_protect(1);
    bridge_flush_icache(addr, size);
    return 0;
#else
    int rc = bridge_mprotect(addr, size, BRIDGE_PROT_READ | BRIDGE_PROT_EXEC);
    bridge_flush_icache(addr, size);
    return rc;
#endif
}

int bridge_make_writable(void *addr, size_t size)
{
#if defined(__APPLE__) && defined(__aarch64__)
    /* MAP_JIT on Apple Silicon: toggle W^X to write mode */
    bridge_jit_write_protect(0);
    (void)addr; (void)size;
    return 0;
#else
    return bridge_mprotect(addr, size, BRIDGE_PROT_READ | BRIDGE_PROT_WRITE);
#endif
}

/* ═══════════════════════════════════════════════════════
 * Windows Implementation
 * ═══════════════════════════════════════════════════════ */

#elif defined(_WIN32)

#include <windows.h>

void *bridge_jit_alloc(size_t size)
{
    void *ptr = VirtualAlloc(NULL, size,
                             MEM_COMMIT | MEM_RESERVE,
                             PAGE_READWRITE);
    if (!ptr) {
        fprintf(stderr, "[bridge] VirtualAlloc failed: %lu\n", GetLastError());
    }
    return ptr;
}

void bridge_jit_free(void *ptr, size_t size)
{
    (void)size;
    if (ptr) VirtualFree(ptr, 0, MEM_RELEASE);
}

int bridge_mprotect(void *addr, size_t size, int prot)
{
    DWORD win_prot = 0;
    DWORD old;

    int rwx = prot & (BRIDGE_PROT_READ | BRIDGE_PROT_WRITE | BRIDGE_PROT_EXEC);
    switch (rwx) {
    case BRIDGE_PROT_READ:
        win_prot = PAGE_READONLY; break;
    case BRIDGE_PROT_READ | BRIDGE_PROT_WRITE:
        win_prot = PAGE_READWRITE; break;
    case BRIDGE_PROT_READ | BRIDGE_PROT_EXEC:
        win_prot = PAGE_EXECUTE_READ; break;
    case BRIDGE_PROT_READ | BRIDGE_PROT_WRITE | BRIDGE_PROT_EXEC:
        win_prot = PAGE_EXECUTE_READWRITE; break;
    default:
        win_prot = PAGE_NOACCESS; break;
    }

    if (!VirtualProtect(addr, size, win_prot, &old)) {
        fprintf(stderr, "[bridge] VirtualProtect failed: %lu\n", GetLastError());
        return -1;
    }
    return 0;
}

void bridge_jit_write_protect(int enable) { (void)enable; }

int bridge_get_cpu_count(void)
{
    SYSTEM_INFO si;
    GetSystemInfo(&si);
    return (int)si.dwNumberOfProcessors;
}

double bridge_get_load_avg(void)
{
    FILETIME idle, kernel, user;
    if (GetSystemTimes(&idle, &kernel, &user)) {
        uint64_t u_idle   = ((uint64_t)idle.dwHighDateTime << 32) | idle.dwLowDateTime;
        uint64_t u_kernel = ((uint64_t)kernel.dwHighDateTime << 32) | kernel.dwLowDateTime;
        uint64_t u_user   = ((uint64_t)user.dwHighDateTime << 32) | user.dwLowDateTime;
        uint64_t total    = u_kernel + u_user;
        if (total > 0)
            return (double)(total - u_idle) / (double)total * 100.0;
    }
    return 0.0;
}

uint32_t bridge_get_gp_register_count(void)
{
#if defined(_M_X64)
    return 16;
#elif defined(_M_ARM64)
    return 31;
#else
    return 8;
#endif
}

int bridge_probe_cpu(cpu_state_t *state)
{
    memset(state, 0, sizeof(*state));
    state->arch = codegen_detect_arch();
    state->total_gp_regs = bridge_get_gp_register_count();
    state->cpu_load_percent = bridge_get_load_avg();
    int ncpu = bridge_get_cpu_count();
    state->estimated_free = (uint32_t)((100.0 - state->cpu_load_percent) / 100.0 * ncpu);
    state->high_perf_mode = (state->estimated_free > 0) ? 1 : 0;
    return 0;
}

void bridge_flush_icache(void *addr, size_t size)
{
    (void)addr; (void)size; /* Windows: coherent cache */
}

void *bridge_alloc_executable(size_t size)
{
    return bridge_jit_alloc(size);
}

int bridge_make_executable(void *addr, size_t size)
{
    int rc = bridge_mprotect(addr, size, BRIDGE_PROT_READ | BRIDGE_PROT_EXEC);
    bridge_flush_icache(addr, size);
    return rc;
}

int bridge_make_writable(void *addr, size_t size)
{
    return bridge_mprotect(addr, size, BRIDGE_PROT_READ | BRIDGE_PROT_WRITE);
}

#else
/* ═══════════════════════════════════════════════════════
 * Unknown OS – Fallback stubs
 * ═══════════════════════════════════════════════════════ */

void *bridge_jit_alloc(size_t size)
{
    (void)size;
    fprintf(stderr, "[bridge] Unsupported OS\n");
    return NULL;
}
void bridge_jit_free(void *ptr, size_t size) { (void)ptr; (void)size; }
int bridge_mprotect(void *addr, size_t size, int prot)
{
    (void)addr; (void)size; (void)prot;
    return -1;
}
void bridge_jit_write_protect(int enable) { (void)enable; }
int bridge_get_cpu_count(void) { return 1; }
double bridge_get_load_avg(void) { return 0.0; }
uint32_t bridge_get_gp_register_count(void) { return 8; }
int bridge_probe_cpu(cpu_state_t *state)
{
    memset(state, 0, sizeof(*state));
    state->arch = ARCH_UNKNOWN;
    state->total_gp_regs = 8;
    return -1;
}
void bridge_flush_icache(void *addr, size_t size) { (void)addr; (void)size; }
void *bridge_alloc_executable(size_t size) { (void)size; return NULL; }
int bridge_make_executable(void *addr, size_t size)
{
    (void)addr; (void)size; return -1;
}
int bridge_make_writable(void *addr, size_t size)
{
    (void)addr; (void)size; return -1;
}

#endif

/* ═══════════════════════════════════════════════════════
 * ABI Register Mapping (platform-independent)
 * ═══════════════════════════════════════════════════════
 *
 * Maps abstract roles → physical register IDs.
 * Uses codegen.h register enums (x86_reg_t / arm_reg_t).
 */

static const abi_info_t abi_x86_64 = {
    .arch = ARCH_X86_64,
    .reg = {
        [ABI_ROLE_RET]  = 0,  /* RAX */
        [ABI_ROLE_ARG0] = 7,  /* RDI */
        [ABI_ROLE_ARG1] = 6,  /* RSI */
        [ABI_ROLE_ARG2] = 2,  /* RDX */
        [ABI_ROLE_ARG3] = 1,  /* RCX */
        [ABI_ROLE_ARG4] = 8,  /* R8  */
        [ABI_ROLE_ARG5] = 9,  /* R9  */
        [ABI_ROLE_SP]   = 4,  /* RSP */
        [ABI_ROLE_FP]   = 5,  /* RBP */
        [ABI_ROLE_LR]   = 0,  /* N/A (push return addr on stack) */
    },
    .caller_saved       = { 0,1,2,6,7,8,9,10,11 }, /* RAX RCX RDX RSI RDI R8-R11 */
    .caller_saved_count = 9,
    .callee_saved       = { 3,5,12,13,14,15 },      /* RBX RBP R12-R15 */
    .callee_saved_count = 6,
    .max_int_args       = 6,
};

static const abi_info_t abi_arm64 = {
    .arch = ARCH_ARM64,
    .reg = {
        [ABI_ROLE_RET]  = 0,  /* X0  */
        [ABI_ROLE_ARG0] = 0,  /* X0  */
        [ABI_ROLE_ARG1] = 1,  /* X1  */
        [ABI_ROLE_ARG2] = 2,  /* X2  */
        [ABI_ROLE_ARG3] = 3,  /* X3  */
        [ABI_ROLE_ARG4] = 4,  /* X4  */
        [ABI_ROLE_ARG5] = 5,  /* X5  */
        [ABI_ROLE_SP]   = 31, /* SP  */
        [ABI_ROLE_FP]   = 29, /* FP  */
        [ABI_ROLE_LR]   = 30, /* LR  */
    },
    .caller_saved       = { 0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17 },
    .caller_saved_count = 18,
    .callee_saved       = { 19,20,21,22,23,24,25,26,27,28 },
    .callee_saved_count = 10,
    .max_int_args       = 8,
};

static const abi_info_t abi_unknown = {
    .arch = ARCH_UNKNOWN,
    .reg  = {0},
    .caller_saved_count = 0,
    .callee_saved_count = 0,
    .max_int_args       = 0,
};

const abi_info_t *bridge_get_abi(target_arch_t arch)
{
    switch (arch) {
    case ARCH_X86_64: return &abi_x86_64;
    case ARCH_ARM64:  return &abi_arm64;
    default:          return &abi_unknown;
    }
}
