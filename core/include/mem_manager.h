/*
 * mem_manager.h – Memory Manager for Vir Runtime
 * Phase 3 – H2
 */

#ifndef VIR_MEM_MANAGER_H
#define VIR_MEM_MANAGER_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Arena allocator */
int    vir_arena_create(size_t size);
void  *vir_arena_alloc(int arena_id, size_t size);
void   vir_arena_reset(int arena_id);
void   vir_arena_destroy(int arena_id);
size_t vir_arena_used(int arena_id);

/* Reference counting */
void *vir_rc_alloc(size_t size);
int   vir_rc_retain(void *ptr);
int   vir_rc_release(void *ptr);
int   vir_rc_count(void *ptr);

/* Explicit free */
void  vir_free(void *ptr);

/* Memory pool */
int   vir_pool_create(size_t elem_size, size_t count);
void *vir_pool_alloc(int pool_id);
void  vir_pool_free(int pool_id, void *ptr);
void  vir_pool_destroy(int pool_id);

/* Stats */
void   vir_mem_stats_print(void);
size_t vir_mem_live_objects(void);
size_t vir_mem_total_allocs(void);
size_t vir_mem_total_frees(void);

#ifdef __cplusplus
}
#endif

#endif /* VIR_MEM_MANAGER_H */
