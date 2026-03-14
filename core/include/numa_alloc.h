/*
 * numa_alloc.h – NUMA-Aware Memory Allocator
 * =============================================
 * Provides NUMA-local memory allocation for multi-socket servers:
 *   Linux:  mbind(), set_mempolicy(), /sys/devices/system/node/
 *   macOS:  Unified memory — thread affinity via thread_policy_set
 *   Windows: VirtualAllocExNuma
 *
 * Falls back to regular allocation on single-node systems.
 */

#ifndef VIR_NUMA_ALLOC_H
#define VIR_NUMA_ALLOC_H

#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ═══════════════════════════════════════════════════════
 * NUMA Topology
 * ═══════════════════════════════════════════════════════ */

#define NUMA_MAX_NODES  64

typedef struct {
    uint32_t num_nodes;                  /* Number of NUMA nodes         */
    uint64_t node_mem_bytes[NUMA_MAX_NODES]; /* Memory per node          */
    uint32_t cpus_per_node[NUMA_MAX_NODES];  /* CPUs per node            */
    bool     available;                  /* NUMA topology detected       */
} numa_topology_t;

/* Detect NUMA topology from OS. */
int numa_detect_topology(numa_topology_t *topo);

/* ═══════════════════════════════════════════════════════
 * NUMA-Aware Allocation
 * ═══════════════════════════════════════════════════════ */

/* Allocate memory on a specific NUMA node.
 * Falls back to regular alloc on macOS or single-node. */
void *numa_alloc_on_node(size_t size, uint32_t node);

/* Allocate memory local to the calling thread's CPU. */
void *numa_alloc_local(size_t size);

/* Interleave allocation across all NUMA nodes
 * (good for data accessed by multiple threads). */
void *numa_alloc_interleaved(size_t size);

/* Free NUMA-allocated memory. */
void numa_free(void *ptr, size_t size);

/* ═══════════════════════════════════════════════════════
 * Thread Affinity
 * ═══════════════════════════════════════════════════════ */

/* Pin current thread to a specific NUMA node.
 * Returns 0 on success, -1 on error. */
int numa_bind_thread_to_node(uint32_t node);

/* Get the NUMA node of the current CPU. */
int numa_current_node(void);

/* ═══════════════════════════════════════════════════════
 * Statistics
 * ═══════════════════════════════════════════════════════ */

typedef struct {
    uint64_t local_allocs;
    uint64_t remote_allocs;
    uint64_t interleaved_allocs;
    uint64_t total_bytes;
} numa_alloc_stats_t;

void numa_alloc_get_stats(numa_alloc_stats_t *stats);
void numa_alloc_reset_stats(void);

#ifdef __cplusplus
}
#endif

#endif /* VIR_NUMA_ALLOC_H */
