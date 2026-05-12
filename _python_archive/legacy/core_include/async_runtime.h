/*
 * async_runtime.h – Vir Async Event Loop (kqueue / epoll / IOCP)
 * ================================================================
 * Phase V – Platform-specific async I/O runtime.
 */

#ifndef VIR_ASYNC_RUNTIME_H
#define VIR_ASYNC_RUNTIME_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Callback types */
typedef void (*vir_async_callback_t)(int fd, int events, void *user_data);
typedef void (*vir_timer_callback_t)(int timer_id, void *user_data);

/* Event types */
#define VIR_EVENT_READ   1
#define VIR_EVENT_WRITE  2
#define VIR_EVENT_BOTH   3

/* ── Event Loop lifecycle ────────────────────────────── */
int  async_event_loop_create(void);
void async_event_loop_destroy(void);
int  async_event_loop_run(int timeout_ms);
void async_event_loop_stop(void);

/* ── FD Watcher ──────────────────────────────────────── */
int  async_register_fd(int fd, int events, vir_async_callback_t cb, void *user_data);
int  async_unregister_fd(int fd);

/* ── Timer ───────────────────────────────────────────── */
int  async_timer_arm(uint64_t interval_ms, int oneshot,
                     vir_timer_callback_t cb, void *user_data);
void async_timer_cancel(int timer_id);

/* ── FFI exports for Vir stdlib ──────────────────────── */
int  _kqueue(void);
int  _kevent_register(int kq_fd, int fd, int filter, int flags);
int  _kevent_poll(int kq_fd, int timeout_ms);
int  _close(int fd);

int  native_epoll_create(void);
int  native_epoll_add_fd(int epoll_fd, int fd, int events);
int  native_epoll_wait(int epoll_fd, int timeout_ms);

#ifdef __cplusplus
}
#endif

#endif /* VIR_ASYNC_RUNTIME_H */
