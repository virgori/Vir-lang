/*
 * numa_alloc.c – NUMA-Aware Memory Allocator
 * =============================================
 * Linux:  mbind() + sched_getcpu() + /sys/devices/system/node/
 * macOS:  thread_policy_set (unified memory, no NUMA nodes)
 * Windows: VirtualAllocExNuma + GetNumaHighestNodeNumber
 */

#include "numa_alloc.h"

#include <string.h>
#include <stdio.h>
#include <stdlib.h>

#if defined(__APPLE__)
  #include <mach/mach.h>
  #include <mach/thread_act.h>
  #include <mach/thread_policy.h>
  #include <sys/sysctl.h>
  #include <sys/mman.h>
  #include <unistd.h>
  #include <pthread.h>
#elif defined(__linux__)
  #include <sys/mman.h>
  #include <sched.h>
  #include <unistd.h>
  #include <dirent.h>
  /* Linux NUMA syscalls — avoid libnuma dependency */
  #include <sys/syscall.h>
  #include <errno.h>

  /* Memory policy constants */
  #ifndef MPOL_DEFAULT
    #define MPOL_DEFAULT    0
    #define MPOL_PREFERRED  1
    #define MPOL_BIND       2
    #define MPOL_INTERLEAVE 3
  #endif

  static long sys_mbind(void *addr, unsigned long len, int mode,
                        const unsigned long *nodemask, unsigned long maxnode,
                        unsigned flags)
  {
      return syscall(SYS_mbind, addr, len, mode, nodemask, maxnode, flags);
  }

  static int sys_getcpu(unsigned *cpu, unsigned *node)
  {
      return (int)syscall(SYS_getcpu, cpu, node, NULL);
  }

#elif defined(_WIN32)
  #include <windows.h>
#endif

/* ── Static state ────────────────────────────────────── */
static numa_alloc_stats_t g_stats;

/* ═══════════════════════════════════════════════════════
 * Topology Detection
 * ═══════════════════════════════════════════════════════ */

int numa_detect_topology(numa_topology_t *topo)
{
    if (!topo) return -1;
    memset(topo, 0, sizeof(*topo));

#if defined(__APPLE__)
    /* macOS has unified memory — single NUMA node */
    topo->num_nodes = 1;
    topo->available = false; /* No real NUMA */

    /* Get total memory */
    uint64_t memsize = 0;
    size_t sz = sizeof(memsize);
    if (sysctlbyname("hw.memsize", &memsize, &sz, NULL, 0) == 0)
        topo->node_mem_bytes[0] = memsize;

    int ncpu = 0;
    sz = sizeof(ncpu);
    if (sysctlbyname("hw.logicalcpu", &ncpu, &sz, NULL, 0) == 0)
        topo->cpus_per_node[0] = (uint32_t)ncpu;

#elif defined(__linux__)
    /* Enumerate /sys/devices/system/node/node* */
    DIR *d = opendir("/sys/devices/system/node");
    if (!d) {
        topo->num_nodes = 1;
        topo->available = false;
        return 0;
    }

    struct dirent *ent;
    uint32_t count = 0;
    while ((ent = readdir(d)) != NULL) {
        unsigned node_id;
        if (sscanf(ent->d_name, "node%u", &node_id) == 1) {
            if (node_id < NUMA_MAX_NODES) {
                /* Read memory size */
                char path[256];
                snprintf(path, sizeof(path),
                         "/sys/devices/system/node/node%u/meminfo", node_id);
                FILE *f = fopen(path, "r");
                if (f) {
                    char line[256];
                    while (fgets(line, sizeof(line), f)) {
                        unsigned long kb;
                        if (sscanf(line, "Node %*u MemTotal: %lu kB", &kb) == 1) {
                            topo->node_mem_bytes[node_id] = kb * 1024UL;
                            break;
                        }
                    }
                    fclose(f);
                }

                /* Count CPUs in this node */
                snprintf(path, sizeof(path),
                         "/sys/devices/system/node/node%u/cpulist", node_id);
                f = fopen(path, "r");
                if (f) {
                    char buf[256];
                    if (fgets(buf, sizeof(buf), f)) {
                        /* Count by parsing CPU ranges like "0-7,16-23" */
                        uint32_t cpus = 0;
                        char *p = buf;
                        while (*p) {
                            unsigned lo, hi;
                            if (sscanf(p, "%u-%u", &lo, &hi) == 2) {
                                cpus += (hi - lo + 1);
                            } else if (sscanf(p, "%u", &lo) == 1) {
                                cpus++;
                            }
                            while (*p && *p != ',') p++;
                            if (*p == ',') p++;
                        }
                        topo->cpus_per_node[node_id] = cpus;
                    }
                    fclose(f);
                }

                if (node_id + 1 > count) count = node_id + 1;
            }
        }
    }
    closedir(d);

    topo->num_nodes = (count > 0) ? count : 1;
    topo->available = (count > 1);

#elif defined(_WIN32)
    ULONG highest = 0;
    if (GetNumaHighestNodeNumber(&highest)) {
        topo->num_nodes = highest + 1;
        topo->available = (topo->num_nodes > 1);
    } else {
        topo->num_nodes = 1;
        topo->available = false;
    }
#endif

    return 0;
}

/* ═══════════════════════════════════════════════════════
 * Internal: page-aligned mmap
 * ═══════════════════════════════════════════════════════ */

static size_t page_round_up(size_t size)
{
    size_t pg = 4096;
#if !defined(_WIN32)
    pg = (size_t)sysconf(_SC_PAGESIZE);
#endif
    return (size + pg - 1) & ~(pg - 1);
}

/* ═══════════════════════════════════════════════════════
 * NUMA Allocation
 * ═══════════════════════════════════════════════════════ */

void *numa_alloc_on_node(size_t size, uint32_t node)
{
    if (size == 0) return NULL;
    size = page_round_up(size);

#if defined(__linux__)
    void *p = mmap(NULL, size, PROT_READ | PROT_WRITE,
                   MAP_ANONYMOUS | MAP_PRIVATE, -1, 0);
    if (p == MAP_FAILED) return NULL;

    /* Bind to specific node */
    unsigned long nodemask = 1UL << node;
    if (sys_mbind(p, size, MPOL_BIND, &nodemask, NUMA_MAX_NODES, 0) != 0) {
        /* mbind failed — still usable, just not NUMA-bound */
        g_stats.remote_allocs++;
    } else {
        g_stats.local_allocs++;
    }
    g_stats.total_bytes += size;
    return p;

#elif defined(_WIN32)
    void *p = VirtualAllocExNuma(GetCurrentProcess(), NULL, size,
                                  MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE,
                                  (UCHAR)node);
    if (p) {
        g_stats.local_allocs++;
        g_stats.total_bytes += size;
    }
    return p;

#else
    /* macOS: no NUMA, just allocate normally */
    (void)node;
    void *p = mmap(NULL, size, PROT_READ | PROT_WRITE,
                   MAP_ANONYMOUS | MAP_PRIVATE, -1, 0);
    if (p == MAP_FAILED) return NULL;
    g_stats.local_allocs++;
    g_stats.total_bytes += size;
    return p;
#endif
}

void *numa_alloc_local(size_t size)
{
    int node = numa_current_node();
    if (node < 0) node = 0;
    return numa_alloc_on_node(size, (uint32_t)node);
}

void *numa_alloc_interleaved(size_t size)
{
    if (size == 0) return NULL;
    size = page_round_up(size);

#if defined(__linux__)
    void *p = mmap(NULL, size, PROT_READ | PROT_WRITE,
                   MAP_ANONYMOUS | MAP_PRIVATE, -1, 0);
    if (p == MAP_FAILED) return NULL;

    /* Interleave across all nodes */
    unsigned long all_nodes = ~0UL;
    sys_mbind(p, size, MPOL_INTERLEAVE, &all_nodes, NUMA_MAX_NODES, 0);

    g_stats.interleaved_allocs++;
    g_stats.total_bytes += size;
    return p;

#else
    /* Non-Linux: regular allocation */
    void *p = mmap(NULL, size, PROT_READ | PROT_WRITE,
                   MAP_ANONYMOUS | MAP_PRIVATE, -1, 0);
    if (p == MAP_FAILED) return NULL;
    g_stats.interleaved_allocs++;
    g_stats.total_bytes += size;
    return p;
#endif
}

void numa_free(void *ptr, size_t size)
{
    if (!ptr || size == 0) return;
#if defined(_WIN32)
    VirtualFree(ptr, 0, MEM_RELEASE);
    (void)size;
#else
    munmap(ptr, page_round_up(size));
#endif
}

/* ═══════════════════════════════════════════════════════
 * Thread Affinity
 * ═══════════════════════════════════════════════════════ */

int numa_bind_thread_to_node(uint32_t node)
{
#if defined(__linux__)
    /* Build CPU set from node's CPUs */
    char path[256];
    snprintf(path, sizeof(path),
             "/sys/devices/system/node/node%u/cpulist", node);
    FILE *f = fopen(path, "r");
    if (!f) return -1;

    cpu_set_t mask;
    CPU_ZERO(&mask);
    char buf[256];
    if (fgets(buf, sizeof(buf), f)) {
        char *p = buf;
        while (*p) {
            unsigned lo, hi;
            if (sscanf(p, "%u-%u", &lo, &hi) == 2) {
                for (unsigned c = lo; c <= hi; c++) CPU_SET(c, &mask);
            } else if (sscanf(p, "%u", &lo) == 1) {
                CPU_SET(lo, &mask);
            }
            while (*p && *p != ',') p++;
            if (*p == ',') p++;
        }
    }
    fclose(f);

    return sched_setaffinity(0, sizeof(mask), &mask);

#elif defined(__APPLE__)
    /* macOS: thread affinity hint via thread_policy_set */
    thread_affinity_policy_data_t policy = { .affinity_tag = (integer_t)(node + 1) };
    kern_return_t kr = thread_policy_set(
        pthread_mach_thread_np(pthread_self()),
        THREAD_AFFINITY_POLICY,
        (thread_policy_t)&policy,
        THREAD_AFFINITY_POLICY_COUNT
    );
    return (kr == KERN_SUCCESS) ? 0 : -1;

#elif defined(_WIN32)
    GROUP_AFFINITY ga;
    memset(&ga, 0, sizeof(ga));
    ga.Group = (WORD)node;
    ga.Mask  = ~(KAFFINITY)0;
    return SetThreadGroupAffinity(GetCurrentThread(), &ga, NULL) ? 0 : -1;

#else
    (void)node;
    return -1;
#endif
}

int numa_current_node(void)
{
#if defined(__linux__)
    unsigned cpu = 0, node = 0;
    if (sys_getcpu(&cpu, &node) == 0)
        return (int)node;
    return 0;

#elif defined(__APPLE__)
    return 0; /* Unified memory, always node 0 */

#elif defined(_WIN32)
    PROCESSOR_NUMBER pn;
    GetCurrentProcessorNumberEx(&pn);
    USHORT node;
    if (GetNumaProcessorNodeEx(&pn, &node))
        return (int)node;
    return 0;

#else
    return 0;
#endif
}

/* ═══════════════════════════════════════════════════════
 * Statistics
 * ═══════════════════════════════════════════════════════ */

void numa_alloc_get_stats(numa_alloc_stats_t *stats)
{
    if (stats) *stats = g_stats;
}

void numa_alloc_reset_stats(void)
{
    memset(&g_stats, 0, sizeof(g_stats));
}
