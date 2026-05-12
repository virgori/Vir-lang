/*
 * async_runtime.c – Platform Async Event Loop (kqueue / epoll / IOCP)
 * ====================================================================
 * Phase V – Async I/O runtime backing stdlib/vir/async/*.vri
 *
 * macOS:   kqueue
 * Linux:   epoll (+ io_uring if available)
 * Windows: IOCP (stub)
 *
 * Provides extern func implementations:
 *   _kqueue, _kevent_register, _kevent_poll, _close
 *   native_epoll_create, native_epoll_wait, native_epoll_add_fd
 *   async_event_loop_create, async_event_loop_run, async_timer_arm
 */

#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <errno.h>
#include <unistd.h>
#include <fcntl.h>

/* ═══════════════════════════════════════════════════════
 * Platform detection
 * ═══════════════════════════════════════════════════════ */
#if defined(__APPLE__)
  #define VIR_ASYNC_KQUEUE 1
  #include <sys/event.h>
  #include <sys/time.h>
#elif defined(__linux__)
  #define VIR_ASYNC_EPOLL 1
  #include <sys/epoll.h>
  #include <sys/timerfd.h>
#endif

/* ═══════════════════════════════════════════════════════
 * Constants
 * ═══════════════════════════════════════════════════════ */
#define ASYNC_MAX_EVENTS     256
#define ASYNC_MAX_FDS        4096
#define ASYNC_MAX_TIMERS     256

/* ═══════════════════════════════════════════════════════
 * Callback types
 * ═══════════════════════════════════════════════════════ */
typedef void (*vir_async_callback_t)(int fd, int events, void *user_data);
typedef void (*vir_timer_callback_t)(int timer_id, void *user_data);

/* ═══════════════════════════════════════════════════════
 * FD Watcher
 * ═══════════════════════════════════════════════════════ */
typedef struct {
    int                   fd;
    int                   events;   /* 1=READ, 2=WRITE, 3=BOTH */
    vir_async_callback_t  callback;
    void                 *user_data;
    int                   active;
} vir_fd_watcher_t;

/* ═══════════════════════════════════════════════════════
 * Timer
 * ═══════════════════════════════════════════════════════ */
typedef struct {
    int                   id;
    int                   fd;       /* timerfd (Linux) or slot id (macOS) */
    uint64_t              interval_ms;
    int                   oneshot;
    vir_timer_callback_t  callback;
    void                 *user_data;
    int                   active;
} vir_timer_t;

/* ═══════════════════════════════════════════════════════
 * Event Loop
 * ═══════════════════════════════════════════════════════ */
typedef struct {
    int               backend_fd;     /* kqueue fd or epoll fd */
    int               running;
    int               fd_count;
    int               timer_count;
    vir_fd_watcher_t  watchers[ASYNC_MAX_FDS];
    vir_timer_t       timers[ASYNC_MAX_TIMERS];
} vir_event_loop_t;

/* Global event loop instance */
static vir_event_loop_t g_loop = { .backend_fd = -1, .running = 0 };

/* ═══════════════════════════════════════════════════════
 * Non-blocking helper
 * ═══════════════════════════════════════════════════════ */
static int set_nonblocking(int fd)
{
    int flags = fcntl(fd, F_GETFL, 0);
    if (flags < 0) return -1;
    return fcntl(fd, F_SETFL, flags | O_NONBLOCK);
}

/* ═══════════════════════════════════════════════════════
 * Event Loop Create / Destroy
 * ═══════════════════════════════════════════════════════ */
int async_event_loop_create(void)
{
    if (g_loop.backend_fd >= 0) return 0; /* already created */

    memset(&g_loop, 0, sizeof(g_loop));
    g_loop.backend_fd = -1;

#if VIR_ASYNC_KQUEUE
    g_loop.backend_fd = kqueue();
    if (g_loop.backend_fd < 0) {
        perror("vir: kqueue() failed");
        return -1;
    }
#elif VIR_ASYNC_EPOLL
    g_loop.backend_fd = epoll_create1(EPOLL_CLOEXEC);
    if (g_loop.backend_fd < 0) {
        perror("vir: epoll_create1() failed");
        return -1;
    }
#else
    fprintf(stderr, "vir: async runtime not supported on this platform\n");
    return -1;
#endif

    g_loop.running = 1;
    return 0;
}

void async_event_loop_destroy(void)
{
    if (g_loop.backend_fd >= 0) {
        close(g_loop.backend_fd);
        g_loop.backend_fd = -1;
    }
    /* Close timer fds on Linux */
#if VIR_ASYNC_EPOLL
    for (int i = 0; i < g_loop.timer_count; i++) {
        if (g_loop.timers[i].active && g_loop.timers[i].fd >= 0) {
            close(g_loop.timers[i].fd);
        }
    }
#endif
    g_loop.running = 0;
}

/* ═══════════════════════════════════════════════════════
 * FD Watcher Registration
 * ═══════════════════════════════════════════════════════ */
int async_register_fd(int fd, int events, vir_async_callback_t cb, void *user_data)
{
    if (g_loop.backend_fd < 0) return -1;
    if (g_loop.fd_count >= ASYNC_MAX_FDS) return -1;

    set_nonblocking(fd);

    int slot = g_loop.fd_count++;
    g_loop.watchers[slot] = (vir_fd_watcher_t){
        .fd = fd, .events = events, .callback = cb,
        .user_data = user_data, .active = 1
    };

#if VIR_ASYNC_KQUEUE
    struct kevent kev[2];
    int n = 0;
    if (events & 1) { /* READ */
        EV_SET(&kev[n++], fd, EVFILT_READ, EV_ADD | EV_ENABLE, 0, 0, (void*)(intptr_t)slot);
    }
    if (events & 2) { /* WRITE */
        EV_SET(&kev[n++], fd, EVFILT_WRITE, EV_ADD | EV_ENABLE, 0, 0, (void*)(intptr_t)slot);
    }
    if (kevent(g_loop.backend_fd, kev, n, NULL, 0, NULL) < 0) {
        perror("vir: kevent register failed");
        return -1;
    }
#elif VIR_ASYNC_EPOLL
    struct epoll_event ev;
    ev.events = 0;
    if (events & 1) ev.events |= EPOLLIN;
    if (events & 2) ev.events |= EPOLLOUT;
    ev.data.u32 = (uint32_t)slot;
    if (epoll_ctl(g_loop.backend_fd, EPOLL_CTL_ADD, fd, &ev) < 0) {
        perror("vir: epoll_ctl ADD failed");
        return -1;
    }
#endif

    return slot;
}

int async_unregister_fd(int fd)
{
    if (g_loop.backend_fd < 0) return -1;

#if VIR_ASYNC_KQUEUE
    struct kevent kev[2];
    EV_SET(&kev[0], fd, EVFILT_READ, EV_DELETE, 0, 0, NULL);
    EV_SET(&kev[1], fd, EVFILT_WRITE, EV_DELETE, 0, 0, NULL);
    kevent(g_loop.backend_fd, kev, 2, NULL, 0, NULL); /* ignore errors */
#elif VIR_ASYNC_EPOLL
    epoll_ctl(g_loop.backend_fd, EPOLL_CTL_DEL, fd, NULL);
#endif

    /* Deactivate watcher */
    for (int i = 0; i < g_loop.fd_count; i++) {
        if (g_loop.watchers[i].fd == fd && g_loop.watchers[i].active) {
            g_loop.watchers[i].active = 0;
            break;
        }
    }
    return 0;
}

/* ═══════════════════════════════════════════════════════
 * Timer Registration
 * ═══════════════════════════════════════════════════════ */
int async_timer_arm(uint64_t interval_ms, int oneshot,
                    vir_timer_callback_t cb, void *user_data)
{
    if (g_loop.backend_fd < 0) return -1;
    if (g_loop.timer_count >= ASYNC_MAX_TIMERS) return -1;

    int slot = g_loop.timer_count++;
    vir_timer_t *t = &g_loop.timers[slot];
    t->id = slot;
    t->interval_ms = interval_ms;
    t->oneshot = oneshot;
    t->callback = cb;
    t->user_data = user_data;
    t->active = 1;

#if VIR_ASYNC_KQUEUE
    struct kevent kev;
    uint16_t flags = EV_ADD | EV_ENABLE;
    if (oneshot) flags |= EV_ONESHOT;
    EV_SET(&kev, slot + 10000, EVFILT_TIMER, flags, NOTE_MSECONDS,
           (intptr_t)interval_ms, (void*)(intptr_t)slot);
    if (kevent(g_loop.backend_fd, &kev, 1, NULL, 0, NULL) < 0) {
        perror("vir: kevent timer failed");
        return -1;
    }
    t->fd = slot + 10000; /* ident */
#elif VIR_ASYNC_EPOLL
    int tfd = timerfd_create(CLOCK_MONOTONIC, TFD_NONBLOCK | TFD_CLOEXEC);
    if (tfd < 0) {
        perror("vir: timerfd_create failed");
        return -1;
    }
    struct itimerspec its = {0};
    its.it_value.tv_sec = interval_ms / 1000;
    its.it_value.tv_nsec = (interval_ms % 1000) * 1000000;
    if (!oneshot) {
        its.it_interval = its.it_value;
    }
    timerfd_settime(tfd, 0, &its, NULL);

    struct epoll_event ev;
    ev.events = EPOLLIN;
    ev.data.u32 = (uint32_t)(slot | 0x80000000u); /* high bit = timer flag */
    epoll_ctl(g_loop.backend_fd, EPOLL_CTL_ADD, tfd, &ev);
    t->fd = tfd;
#endif

    return slot;
}

void async_timer_cancel(int timer_id)
{
    if (timer_id < 0 || timer_id >= g_loop.timer_count) return;
    vir_timer_t *t = &g_loop.timers[timer_id];
    if (!t->active) return;
    t->active = 0;

#if VIR_ASYNC_KQUEUE
    struct kevent kev;
    EV_SET(&kev, t->fd, EVFILT_TIMER, EV_DELETE, 0, 0, NULL);
    kevent(g_loop.backend_fd, &kev, 1, NULL, 0, NULL);
#elif VIR_ASYNC_EPOLL
    if (t->fd >= 0) {
        epoll_ctl(g_loop.backend_fd, EPOLL_CTL_DEL, t->fd, NULL);
        close(t->fd);
        t->fd = -1;
    }
#endif
}

/* ═══════════════════════════════════════════════════════
 * Event Loop Run (main poll loop)
 * ═══════════════════════════════════════════════════════ */
int async_event_loop_run(int timeout_ms)
{
    if (g_loop.backend_fd < 0) return -1;

#if VIR_ASYNC_KQUEUE
    struct kevent events[ASYNC_MAX_EVENTS];
    struct timespec ts, *tsp = NULL;
    if (timeout_ms >= 0) {
        ts.tv_sec = timeout_ms / 1000;
        ts.tv_nsec = (timeout_ms % 1000) * 1000000L;
        tsp = &ts;
    }

    while (g_loop.running) {
        int n = kevent(g_loop.backend_fd, NULL, 0, events, ASYNC_MAX_EVENTS, tsp);
        if (n < 0) {
            if (errno == EINTR) continue;
            perror("vir: kevent poll failed");
            return -1;
        }
        if (n == 0 && timeout_ms >= 0) break; /* timeout */

        for (int i = 0; i < n; i++) {
            int slot = (int)(intptr_t)events[i].udata;
            if (events[i].filter == EVFILT_TIMER) {
                /* Timer event */
                if (slot >= 0 && slot < g_loop.timer_count && g_loop.timers[slot].active) {
                    vir_timer_t *t = &g_loop.timers[slot];
                    if (t->callback) t->callback(t->id, t->user_data);
                    if (t->oneshot) t->active = 0;
                }
            } else {
                /* FD event */
                int ev_type = 0;
                if (events[i].filter == EVFILT_READ) ev_type = 1;
                if (events[i].filter == EVFILT_WRITE) ev_type = 2;
                if (slot >= 0 && slot < g_loop.fd_count && g_loop.watchers[slot].active) {
                    vir_fd_watcher_t *w = &g_loop.watchers[slot];
                    if (w->callback) w->callback(w->fd, ev_type, w->user_data);
                }
            }
        }
        if (timeout_ms >= 0) break; /* single poll */
    }

#elif VIR_ASYNC_EPOLL
    struct epoll_event events[ASYNC_MAX_EVENTS];

    while (g_loop.running) {
        int n = epoll_wait(g_loop.backend_fd, events, ASYNC_MAX_EVENTS, timeout_ms);
        if (n < 0) {
            if (errno == EINTR) continue;
            perror("vir: epoll_wait failed");
            return -1;
        }
        if (n == 0 && timeout_ms >= 0) break;

        for (int i = 0; i < n; i++) {
            uint32_t slot = events[i].data.u32;
            if (slot & 0x80000000u) {
                /* Timer event */
                int tidx = (int)(slot & 0x7FFFFFFFu);
                if (tidx >= 0 && tidx < g_loop.timer_count && g_loop.timers[tidx].active) {
                    /* Drain timerfd */
                    uint64_t exp;
                    (void)read(g_loop.timers[tidx].fd, &exp, sizeof(exp));
                    vir_timer_t *t = &g_loop.timers[tidx];
                    if (t->callback) t->callback(t->id, t->user_data);
                    if (t->oneshot) {
                        t->active = 0;
                        close(t->fd);
                        t->fd = -1;
                    }
                }
            } else {
                /* FD event */
                int ev_type = 0;
                if (events[i].events & EPOLLIN) ev_type |= 1;
                if (events[i].events & EPOLLOUT) ev_type |= 2;
                if ((int)slot < g_loop.fd_count && g_loop.watchers[slot].active) {
                    vir_fd_watcher_t *w = &g_loop.watchers[slot];
                    if (w->callback) w->callback(w->fd, ev_type, w->user_data);
                }
            }
        }
        if (timeout_ms >= 0) break;
    }
#endif

    return 0;
}

void async_event_loop_stop(void)
{
    g_loop.running = 0;
}

/* ═══════════════════════════════════════════════════════
 * Vir FFI exports (backing stdlib extern func declarations)
 * ═══════════════════════════════════════════════════════ */

/* For stdlib/vir/async/kqueue.vri */
int _kqueue(void)
{
    return async_event_loop_create();
}

int _kevent_register(int kq_fd, int fd, int filter, int flags)
{
    (void)kq_fd; /* uses global loop */
    int events = 0;
    if (filter == 1) events = 1;       /* READ */
    else if (filter == 2) events = 2;  /* WRITE */
    else events = 3;                    /* BOTH */
    return async_register_fd(fd, events, NULL, NULL);
}

int _kevent_poll(int kq_fd, int timeout_ms)
{
    (void)kq_fd;
    return async_event_loop_run(timeout_ms);
}

int _close(int fd)
{
    return close(fd);
}

/* For stdlib/vir/async/async.vri */
int native_epoll_create(void)
{
    return async_event_loop_create();
}

int native_epoll_add_fd(int epoll_fd, int fd, int events)
{
    (void)epoll_fd;
    return async_register_fd(fd, events, NULL, NULL);
}

int native_epoll_wait(int epoll_fd, int timeout_ms)
{
    (void)epoll_fd;
    return async_event_loop_run(timeout_ms);
}
