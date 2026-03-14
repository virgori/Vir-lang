/*
 * thread_runtime.c – Thread Runtime for Vir Stdlib
 * ==================================================
 * Phase 3 – G2: Native backing for stdlib/vir/thread/
 *
 * Wraps pthreads with Vir-style API: spawn, join, mutex, rwlock,
 * condition variable, once, thread-local storage.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
#include <unistd.h>

/* ═══════════════════════════════════════════════════════
 * Constants
 * ═══════════════════════════════════════════════════════ */

#define VIR_THREAD_MAX   64
#define VIR_MUTEX_MAX    128
#define VIR_COND_MAX     64
#define VIR_TLS_MAX      32

/* ═══════════════════════════════════════════════════════
 * Types
 * ═══════════════════════════════════════════════════════ */

typedef void (*vir_thread_fn)(void *arg);

typedef struct {
    pthread_t       handle;
    int             active;
    vir_thread_fn   fn;
    void           *arg;
} vir_thread_t;

typedef struct {
    pthread_mutex_t  mtx;
    int              active;
} vir_mutex_t;

typedef struct {
    pthread_rwlock_t rwl;
    int              active;
} vir_rwlock_t;

typedef struct {
    pthread_cond_t   cv;
    int              active;
} vir_cond_t;

typedef struct {
    pthread_key_t    key;
    int              active;
} vir_tls_t;

typedef struct {
    vir_thread_t  threads[VIR_THREAD_MAX];
    vir_mutex_t   mutexes[VIR_MUTEX_MAX];
    vir_rwlock_t  rwlocks[VIR_MUTEX_MAX];
    vir_cond_t    conds[VIR_COND_MAX];
    vir_tls_t     tls_keys[VIR_TLS_MAX];
} vir_thread_ctx_t;

static vir_thread_ctx_t g_thr;

/* ═══════════════════════════════════════════════════════
 * Thread trampoline
 * ═══════════════════════════════════════════════════════ */

typedef struct {
    vir_thread_fn fn;
    void *arg;
} trampoline_arg_t;

static void *thread_trampoline(void *raw) {
    trampoline_arg_t *ta = (trampoline_arg_t *)raw;
    vir_thread_fn fn = ta->fn;
    void *arg = ta->arg;
    free(ta);
    fn(arg);
    return NULL;
}

/* ═══════════════════════════════════════════════════════
 * Thread API
 * ═══════════════════════════════════════════════════════ */

int vir_thread_init(void) {
    memset(&g_thr, 0, sizeof(g_thr));
    return 0;
}

int vir_thread_spawn(vir_thread_fn fn, void *arg) {
    for (int i = 0; i < VIR_THREAD_MAX; i++) {
        if (!g_thr.threads[i].active) {
            trampoline_arg_t *ta = malloc(sizeof(trampoline_arg_t));
            if (!ta) return -1;
            ta->fn = fn;
            ta->arg = arg;
            g_thr.threads[i].fn  = fn;
            g_thr.threads[i].arg = arg;
            int rc = pthread_create(&g_thr.threads[i].handle, NULL,
                                    thread_trampoline, ta);
            if (rc != 0) { free(ta); return -1; }
            g_thr.threads[i].active = 1;
            return i;
        }
    }
    return -1;
}

int vir_thread_join(int id) {
    if (id < 0 || id >= VIR_THREAD_MAX) return -1;
    if (!g_thr.threads[id].active) return -1;
    int rc = pthread_join(g_thr.threads[id].handle, NULL);
    g_thr.threads[id].active = 0;
    return rc;
}

int vir_thread_detach(int id) {
    if (id < 0 || id >= VIR_THREAD_MAX) return -1;
    if (!g_thr.threads[id].active) return -1;
    return pthread_detach(g_thr.threads[id].handle);
}

void vir_thread_yield(void) {
    sched_yield();
}

/* ═══════════════════════════════════════════════════════
 * Mutex API
 * ═══════════════════════════════════════════════════════ */

int vir_mutex_create(void) {
    for (int i = 0; i < VIR_MUTEX_MAX; i++) {
        if (!g_thr.mutexes[i].active) {
            pthread_mutex_init(&g_thr.mutexes[i].mtx, NULL);
            g_thr.mutexes[i].active = 1;
            return i;
        }
    }
    return -1;
}

int vir_mutex_lock(int id) {
    if (id < 0 || id >= VIR_MUTEX_MAX || !g_thr.mutexes[id].active) return -1;
    return pthread_mutex_lock(&g_thr.mutexes[id].mtx);
}

int vir_mutex_unlock(int id) {
    if (id < 0 || id >= VIR_MUTEX_MAX || !g_thr.mutexes[id].active) return -1;
    return pthread_mutex_unlock(&g_thr.mutexes[id].mtx);
}

int vir_mutex_trylock(int id) {
    if (id < 0 || id >= VIR_MUTEX_MAX || !g_thr.mutexes[id].active) return -1;
    return pthread_mutex_trylock(&g_thr.mutexes[id].mtx);
}

int vir_mutex_destroy(int id) {
    if (id < 0 || id >= VIR_MUTEX_MAX || !g_thr.mutexes[id].active) return -1;
    pthread_mutex_destroy(&g_thr.mutexes[id].mtx);
    g_thr.mutexes[id].active = 0;
    return 0;
}

/* ═══════════════════════════════════════════════════════
 * RWLock API
 * ═══════════════════════════════════════════════════════ */

int vir_rwlock_create(void) {
    for (int i = 0; i < VIR_MUTEX_MAX; i++) {
        if (!g_thr.rwlocks[i].active) {
            pthread_rwlock_init(&g_thr.rwlocks[i].rwl, NULL);
            g_thr.rwlocks[i].active = 1;
            return i;
        }
    }
    return -1;
}

int vir_rwlock_rdlock(int id) {
    if (id < 0 || id >= VIR_MUTEX_MAX || !g_thr.rwlocks[id].active) return -1;
    return pthread_rwlock_rdlock(&g_thr.rwlocks[id].rwl);
}

int vir_rwlock_wrlock(int id) {
    if (id < 0 || id >= VIR_MUTEX_MAX || !g_thr.rwlocks[id].active) return -1;
    return pthread_rwlock_wrlock(&g_thr.rwlocks[id].rwl);
}

int vir_rwlock_unlock(int id) {
    if (id < 0 || id >= VIR_MUTEX_MAX || !g_thr.rwlocks[id].active) return -1;
    return pthread_rwlock_unlock(&g_thr.rwlocks[id].rwl);
}

int vir_rwlock_destroy(int id) {
    if (id < 0 || id >= VIR_MUTEX_MAX || !g_thr.rwlocks[id].active) return -1;
    pthread_rwlock_destroy(&g_thr.rwlocks[id].rwl);
    g_thr.rwlocks[id].active = 0;
    return 0;
}

/* ═══════════════════════════════════════════════════════
 * Condition Variable API
 * ═══════════════════════════════════════════════════════ */

int vir_cond_create(void) {
    for (int i = 0; i < VIR_COND_MAX; i++) {
        if (!g_thr.conds[i].active) {
            pthread_cond_init(&g_thr.conds[i].cv, NULL);
            g_thr.conds[i].active = 1;
            return i;
        }
    }
    return -1;
}

int vir_cond_wait(int cond_id, int mutex_id) {
    if (cond_id < 0 || cond_id >= VIR_COND_MAX || !g_thr.conds[cond_id].active)
        return -1;
    if (mutex_id < 0 || mutex_id >= VIR_MUTEX_MAX || !g_thr.mutexes[mutex_id].active)
        return -1;
    return pthread_cond_wait(&g_thr.conds[cond_id].cv,
                             &g_thr.mutexes[mutex_id].mtx);
}

int vir_cond_signal(int id) {
    if (id < 0 || id >= VIR_COND_MAX || !g_thr.conds[id].active) return -1;
    return pthread_cond_signal(&g_thr.conds[id].cv);
}

int vir_cond_broadcast(int id) {
    if (id < 0 || id >= VIR_COND_MAX || !g_thr.conds[id].active) return -1;
    return pthread_cond_broadcast(&g_thr.conds[id].cv);
}

int vir_cond_destroy(int id) {
    if (id < 0 || id >= VIR_COND_MAX || !g_thr.conds[id].active) return -1;
    pthread_cond_destroy(&g_thr.conds[id].cv);
    g_thr.conds[id].active = 0;
    return 0;
}

/* ═══════════════════════════════════════════════════════
 * Thread-Local Storage
 * ═══════════════════════════════════════════════════════ */

int vir_tls_create(void) {
    for (int i = 0; i < VIR_TLS_MAX; i++) {
        if (!g_thr.tls_keys[i].active) {
            if (pthread_key_create(&g_thr.tls_keys[i].key, NULL) != 0) return -1;
            g_thr.tls_keys[i].active = 1;
            return i;
        }
    }
    return -1;
}

int vir_tls_set(int id, void *value) {
    if (id < 0 || id >= VIR_TLS_MAX || !g_thr.tls_keys[id].active) return -1;
    return pthread_setspecific(g_thr.tls_keys[id].key, value);
}

void *vir_tls_get(int id) {
    if (id < 0 || id >= VIR_TLS_MAX || !g_thr.tls_keys[id].active) return NULL;
    return pthread_getspecific(g_thr.tls_keys[id].key);
}

int vir_tls_destroy(int id) {
    if (id < 0 || id >= VIR_TLS_MAX || !g_thr.tls_keys[id].active) return -1;
    pthread_key_delete(g_thr.tls_keys[id].key);
    g_thr.tls_keys[id].active = 0;
    return 0;
}

/* ═══════════════════════════════════════════════════════
 * Once (singleton init)
 * ═══════════════════════════════════════════════════════ */

static pthread_once_t g_once_flags[16] = {
    PTHREAD_ONCE_INIT, PTHREAD_ONCE_INIT, PTHREAD_ONCE_INIT, PTHREAD_ONCE_INIT,
    PTHREAD_ONCE_INIT, PTHREAD_ONCE_INIT, PTHREAD_ONCE_INIT, PTHREAD_ONCE_INIT,
    PTHREAD_ONCE_INIT, PTHREAD_ONCE_INIT, PTHREAD_ONCE_INIT, PTHREAD_ONCE_INIT,
    PTHREAD_ONCE_INIT, PTHREAD_ONCE_INIT, PTHREAD_ONCE_INIT, PTHREAD_ONCE_INIT,
};

int vir_once(int id, void (*init_fn)(void)) {
    if (id < 0 || id >= 16 || !init_fn) return -1;
    return pthread_once(&g_once_flags[id], init_fn);
}
