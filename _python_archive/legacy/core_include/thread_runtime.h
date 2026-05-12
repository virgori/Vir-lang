/*
 * thread_runtime.h – Thread Runtime for Vir Stdlib
 * ==================================================
 * Phase 3 – G2
 */

#ifndef VIR_THREAD_RUNTIME_H
#define VIR_THREAD_RUNTIME_H

#ifdef __cplusplus
extern "C" {
#endif

typedef void (*vir_thread_fn)(void *arg);

int vir_thread_init(void);
int vir_thread_spawn(vir_thread_fn fn, void *arg);
int vir_thread_join(int id);
int vir_thread_detach(int id);
void vir_thread_yield(void);

/* Mutex */
int vir_mutex_create(void);
int vir_mutex_lock(int id);
int vir_mutex_unlock(int id);
int vir_mutex_trylock(int id);
int vir_mutex_destroy(int id);

/* RWLock */
int vir_rwlock_create(void);
int vir_rwlock_rdlock(int id);
int vir_rwlock_wrlock(int id);
int vir_rwlock_unlock(int id);
int vir_rwlock_destroy(int id);

/* Condition Variable */
int vir_cond_create(void);
int vir_cond_wait(int cond_id, int mutex_id);
int vir_cond_signal(int id);
int vir_cond_broadcast(int id);
int vir_cond_destroy(int id);

/* Thread-Local Storage */
int vir_tls_create(void);
int vir_tls_set(int id, void *value);
void *vir_tls_get(int id);
int vir_tls_destroy(int id);

/* Once */
int vir_once(int id, void (*init_fn)(void));

#ifdef __cplusplus
}
#endif

#endif /* VIR_THREAD_RUNTIME_H */
