/*
 * huge_alloc.c – Huge-Page Memory Allocator
 * ============================================
 * OS-level huge/super page allocation with graceful fallback.
 *
 * Linux:  mmap(MAP_ANONYMOUS | MAP_PRIVATE | MAP_HUGETLB)
 * macOS:  mach_vm_allocate with VM_FLAGS_SUPERPAGE_SIZE_2MB
 * Windows: VirtualAlloc(MEM_LARGE_PAGES | MEM_COMMIT | MEM_RESERVE)
 */

#include "huge_alloc.h"

#include <string.h>
#include <stdio.h>

#if defined(__APPLE__)
  #include <mach/mach.h>
  #include <mach/mach_vm.h>
  #include <mach/vm_statistics.h>
  #include <sys/mman.h>
  #include <unistd.h>
#elif defined(__linux__)
  #include <sys/mman.h>
  #include <unistd.h>
#elif defined(_WIN32)
  #include <windows.h>
#endif

/* ── Static stats ────────────────────────────────────── */
static huge_alloc_stats_t g_stats;

/* ═══════════════════════════════════════════════════════
 * Platform constants
 * ═══════════════════════════════════════════════════════ */

#define HUGE_2MB  (2UL * 1024 * 1024)
#define HUGE_1GB  (1UL * 1024 * 1024 * 1024)

/* Minimum allocation to attempt huge pages (default 2 MB) */
#define HUGE_MIN_ALLOC  HUGE_2MB

/* ═══════════════════════════════════════════════════════
 * Query
 * ═══════════════════════════════════════════════════════ */

int huge_page_query(huge_page_info_t *info, const cpu_caps_t *caps)
{
    if (!info) return -1;
    memset(info, 0, sizeof(*info));

    /* If cpu_caps already detected huge pages, use that */
    if (caps && caps->tlb.huge_pages) {
        info->supported  = true;
        info->page_size  = caps->tlb.huge_page_size;
        info->min_alloc  = info->page_size;
        return 0;
    }

#if defined(__APPLE__)
    /* macOS supports 2 MB superpages on both arm64 and x86_64 */
    info->supported  = true;
    info->page_size  = HUGE_2MB;
    info->min_alloc  = HUGE_2MB;
#elif defined(__linux__)
    /* Read /proc/meminfo for Hugepagesize */
    FILE *f = fopen("/proc/meminfo", "r");
    if (f) {
        char line[256];
        while (fgets(line, sizeof(line), f)) {
            unsigned long sz;
            if (sscanf(line, "Hugepagesize: %lu kB", &sz) == 1) {
                info->supported  = true;
                info->page_size  = sz * 1024;
                info->min_alloc  = info->page_size;
                break;
            }
        }
        fclose(f);
    }
    if (!info->supported) {
        /* Fallback: assume 2 MB if /proc read fails */
        info->supported  = true;
        info->page_size  = HUGE_2MB;
        info->min_alloc  = HUGE_2MB;
    }
#elif defined(_WIN32)
    SIZE_T lp = GetLargePageMinimum();
    if (lp > 0) {
        info->supported  = true;
        info->page_size  = (size_t)lp;
        info->min_alloc  = (size_t)lp;
    }
#endif

    return 0;
}

/* ═══════════════════════════════════════════════════════
 * Internal: round up to page boundary
 * ═══════════════════════════════════════════════════════ */

static size_t round_up(size_t size, size_t alignment)
{
    return (size + alignment - 1) & ~(alignment - 1);
}

/* ═══════════════════════════════════════════════════════
 * Internal: platform huge allocation
 * ═══════════════════════════════════════════════════════ */

static void *os_huge_alloc(size_t size)
{
#if defined(__APPLE__)
    /* mach_vm_allocate with superpage flag */
    mach_vm_address_t addr = 0;
    kern_return_t kr = mach_vm_allocate(
        mach_task_self(),
        &addr,
        (mach_vm_size_t)size,
        VM_FLAGS_ANYWHERE | VM_FLAGS_SUPERPAGE_SIZE_2MB
    );
    if (kr == KERN_SUCCESS) return (void *)addr;
    return NULL;

#elif defined(__linux__)
    void *p = mmap(NULL, size,
                   PROT_READ | PROT_WRITE,
                   MAP_ANONYMOUS | MAP_PRIVATE | MAP_HUGETLB,
                   -1, 0);
    if (p == MAP_FAILED) return NULL;
    return p;

#elif defined(_WIN32)
    void *p = VirtualAlloc(NULL, size,
                           MEM_COMMIT | MEM_RESERVE | MEM_LARGE_PAGES,
                           PAGE_READWRITE);
    return p;

#else
    (void)size;
    return NULL;
#endif
}

static void *os_regular_alloc(size_t size)
{
#if defined(_WIN32)
    return VirtualAlloc(NULL, size, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
#else
    void *p = mmap(NULL, size,
                   PROT_READ | PROT_WRITE,
                   MAP_ANONYMOUS | MAP_PRIVATE,
                   -1, 0);
    if (p == MAP_FAILED) return NULL;
    return p;
#endif
}

/* ═══════════════════════════════════════════════════════
 * Public API
 * ═══════════════════════════════════════════════════════ */

void *huge_alloc(size_t size)
{
    if (size == 0) return NULL;

    /* Only attempt huge pages for large allocations */
    if (size >= HUGE_MIN_ALLOC) {
        size_t aligned = round_up(size, HUGE_2MB);
        void *p = os_huge_alloc(aligned);
        if (p) {
            g_stats.huge_allocs++;
            g_stats.total_huge_bytes += aligned;
            return p;
        }
    }

    /* Fallback to regular pages */
    size_t page_sz = 4096;
#if !defined(_WIN32)
    page_sz = (size_t)sysconf(_SC_PAGESIZE);
#endif
    size_t aligned = round_up(size, page_sz);
    void *p = os_regular_alloc(aligned);
    if (p) {
        g_stats.fallback_allocs++;
        g_stats.total_fallback_bytes += aligned;
    }
    return p;
}

void *huge_alloc_strict(size_t size)
{
    if (size == 0) return NULL;
    size_t aligned = round_up(size, HUGE_2MB);
    void *p = os_huge_alloc(aligned);
    if (p) {
        g_stats.huge_allocs++;
        g_stats.total_huge_bytes += aligned;
    }
    return p;
}

void huge_free(void *ptr, size_t size)
{
    if (!ptr || size == 0) return;

#if defined(__APPLE__)
    mach_vm_deallocate(mach_task_self(), (mach_vm_address_t)ptr,
                       (mach_vm_size_t)size);
#elif defined(__linux__)
    munmap(ptr, size);
#elif defined(_WIN32)
    VirtualFree(ptr, 0, MEM_RELEASE);
    (void)size;
#endif
}

void huge_alloc_get_stats(huge_alloc_stats_t *stats)
{
    if (stats) *stats = g_stats;
}

void huge_alloc_reset_stats(void)
{
    memset(&g_stats, 0, sizeof(g_stats));
}
