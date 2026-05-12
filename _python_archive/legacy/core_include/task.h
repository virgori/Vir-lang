/*
 * task.h – Green Thread / Cooperative Task Scheduler
 * ===================================================
 * Phase 2 – A2: Stackful green threads via _setjmp/_longjmp.
 *
 * Each task gets a 64KB mmap'd stack.  The scheduler uses
 * cooperative round-robin: tasks run until they call yield_now()
 * or complete.  task_wait() blocks the calling task until the
 * target task finishes.
 */

#ifndef VIR_TASK_H
#define VIR_TASK_H

#include <stdint.h>
#include <setjmp.h>

/* ═══════════════════════════════════════════════════════
 * Configuration
 * ═══════════════════════════════════════════════════════ */

#define TASK_STACK_SIZE   65536        /* 64 KB per task           */
#define TASK_MAX_TASKS    256          /* Max concurrent tasks     */

/* ═══════════════════════════════════════════════════════
 * Task States
 * ═══════════════════════════════════════════════════════ */

typedef enum {
    TASK_READY     = 0,
    TASK_RUNNING   = 1,
    TASK_WAITING   = 2,
    TASK_COMPLETED = 3,
} task_state_t;

/* ═══════════════════════════════════════════════════════
 * Task Function Signature
 * ═══════════════════════════════════════════════════════ */

typedef int64_t (*task_fn_t)(void *arg);

/* ═══════════════════════════════════════════════════════
 * Task Control Block (TCB)
 * ═══════════════════════════════════════════════════════ */

typedef struct task_tcb {
    uint32_t      id;
    task_state_t  state;
    void         *stack_base;        /* mmap'd region             */
    uint64_t      stack_size;
    jmp_buf       context;           /* saved registers           */
    task_fn_t     entry_fn;
    void         *arg;
    int64_t       result;            /* return value              */
    uint32_t      wait_for;          /* task ID we're waiting on  */
} task_tcb_t;

/* ═══════════════════════════════════════════════════════
 * Scheduler
 * ═══════════════════════════════════════════════════════ */

typedef struct {
    task_tcb_t   *tasks[TASK_MAX_TASKS];
    uint32_t      head;              /* deque front               */
    uint32_t      tail;              /* deque back                */
    uint32_t      count;             /* total tasks (incl done)   */
    task_tcb_t   *current;           /* currently running task    */
    jmp_buf       main_context;      /* scheduler's saved context */
    uint32_t      next_id;           /* monotonic task ID counter */
} task_scheduler_t;

/* ═══════════════════════════════════════════════════════
 * Public API
 * ═══════════════════════════════════════════════════════ */

/* Initialize the global scheduler (call once). */
void task_scheduler_init(void);

/* Create a new task.  Returns task ID. */
uint32_t task_create(task_fn_t fn, void *arg);

/* Run the scheduler until all tasks complete. */
void task_scheduler_run(void);

/* Yield the current task — returns to scheduler. */
void task_yield(void);

/* Block current task until target task completes. */
void task_wait(uint32_t target_id);

/* Get result of a completed task.  Returns 0 if not found/not done. */
int64_t task_get_result(uint32_t task_id);

/* Shut down scheduler, free all stacks. */
void task_scheduler_destroy(void);

#endif /* VIR_TASK_H */
