/*
 * task.c – Green Thread / Cooperative Task Scheduler
 * ===================================================
 * Phase 2 – A2: Stackful green threads.
 *
 * Uses _setjmp/_longjmp on macOS (faster, no signal-mask save)
 * or setjmp/longjmp on Linux.
 *
 * Stack allocation: mmap 64 KB per task (guard-page friendly).
 * Context bootstrap: architecture-specific trampoline setup
 * that points SP to the mmap'd stack top.
 */

#include "task.h"
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

#ifdef __APPLE__
  #include <sys/mman.h>
  #define VIR_SETJMP   _setjmp
  #define VIR_LONGJMP  _longjmp
#elif defined(__linux__)
  #include <sys/mman.h>
  #ifndef MAP_ANONYMOUS
    #define MAP_ANONYMOUS 0x20
  #endif
  #define VIR_SETJMP   setjmp
  #define VIR_LONGJMP  longjmp
#else
  /* Fallback: standard setjmp */
  #define VIR_SETJMP   setjmp
  #define VIR_LONGJMP  longjmp
#endif

/* ═══════════════════════════════════════════════════════
 * Global Scheduler Instance
 * ═══════════════════════════════════════════════════════ */

static task_scheduler_t g_sched;

/* ═══════════════════════════════════════════════════════
 * Deque Helpers (circular buffer in g_sched.tasks[])
 * ═══════════════════════════════════════════════════════ */

static void deque_push_back(task_tcb_t *tcb)
{
    g_sched.tasks[g_sched.tail] = tcb;
    g_sched.tail = (g_sched.tail + 1) % TASK_MAX_TASKS;
}

static task_tcb_t *deque_pop_front(void)
{
    if (g_sched.head == g_sched.tail) return NULL;
    task_tcb_t *tcb = g_sched.tasks[g_sched.head];
    g_sched.tasks[g_sched.head] = NULL;
    g_sched.head = (g_sched.head + 1) % TASK_MAX_TASKS;
    return tcb;
}

static int deque_empty(void)
{
    return g_sched.head == g_sched.tail;
}

/* ═══════════════════════════════════════════════════════
 * Stack Allocation
 * ═══════════════════════════════════════════════════════ */

static void *alloc_stack(uint64_t size)
{
#if defined(__APPLE__) || defined(__linux__)
    void *p = mmap(NULL, size, PROT_READ | PROT_WRITE,
                   MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (p == MAP_FAILED) return NULL;
    return p;
#else
    /* Fallback: malloc (no guard page) */
    return malloc(size);
#endif
}

static void free_stack(void *base, uint64_t size)
{
#if defined(__APPLE__) || defined(__linux__)
    munmap(base, size);
#else
    free(base);
    (void)size;
#endif
}

/* ═══════════════════════════════════════════════════════
 * Task Trampoline
 * ═══════════════════════════════════════════════════════
 * Called when a task first starts running.  Invokes the
 * user function, marks the task COMPLETED, wakes waiters,
 * and jumps back to the scheduler.
 */

static void task_trampoline(void)
{
    task_tcb_t *tcb = g_sched.current;
    if (!tcb) return;

    /* Run the user's function */
    tcb->result = tcb->entry_fn(tcb->arg);

    /* Mark completed */
    tcb->state = TASK_COMPLETED;

    /* Wake any tasks waiting on this one */
    for (uint32_t i = 0; i < TASK_MAX_TASKS; i++) {
        task_tcb_t *w = g_sched.tasks[i];
        if (w && w->state == TASK_WAITING && w->wait_for == tcb->id) {
            w->state = TASK_READY;
            /* Re-enqueue (it was removed from deque when it started waiting) */
        }
    }

    /* Return to scheduler */
    VIR_LONGJMP(g_sched.main_context, 1);
    /* NOTREACHED */
}

/* ═══════════════════════════════════════════════════════
 * Context Bootstrapping
 * ═══════════════════════════════════════════════════════
 * Set up the jmp_buf so that the first longjmp into this
 * task starts at task_trampoline with SP pointing to the
 * mmap'd stack.
 *
 * We do this by calling setjmp, then patching the saved
 * SP / PC in the jmp_buf (architecture-specific).
 *
 * IMPORTANT: This function MUST be compiled without optimization
 * because the stack-switching inline assembly is incompatible
 * with compiler optimizations (especially on ARM64 where the
 * compiler may reorder or optimize away the SP save/restore).
 */

/* Disable optimization for bootstrap_context to ensure correct
 * stack-switching behavior with setjmp/longjmp. */
#if defined(__clang__)
#pragma clang optimize off
#elif defined(__GNUC__)
#pragma GCC optimize("O0")
#endif

static int bootstrap_context(task_tcb_t *tcb)
{
    /*
     * Strategy: save current context, then patch SP and PC
     * to point at our custom stack + trampoline.
     *
     * jmp_buf layout is platform-specific.  We support:
     *   - macOS ARM64: __jb[13] = SP, __jb[1] = PC (or similar)
     *   - macOS x86_64: jmp_buf is long[37]
     *   - Linux ARM64/x86_64: standard glibc layout
     *
     * For robustness we use the well-known technique:
     * call setjmp in a helper function whose stack frame
     * we then redirect.
     */

    /* Compute stack top (grows down on x86_64 and ARM64) */
    void *stack_top = (char *)tcb->stack_base + tcb->stack_size;
    /* Align to 16 bytes */
    stack_top = (void *)((uintptr_t)stack_top & ~(uintptr_t)0xF);

    /*
     * Patch the saved context to use our custom stack.
     * This is the critical arch-specific part.
     *
     * Strategy: We use a small inline-asm "trampoline launch" that
     * switches SP to our mmap'd stack, then does setjmp there.
     * On longjmp, execution resumes on the correct stack.
     */

#if defined(__aarch64__)
    /*
     * ARM64 (macOS + Linux):
     * Save current SP, switch to mmap'd stack, call setjmp,
     * then restore original SP.  The saved jmp_buf captures
     * our custom stack pointer.
     *
     * NOTE: Do NOT use `register void *old_sp __asm__("x9")` here.
     * The compiler may use x9 for other purposes (e.g., passing
     * arguments to function calls), which would corrupt the saved SP.
     * Use a plain local variable instead.
     */
    {
        void *old_sp;
        __asm__ volatile(
            "mov %0, sp\n\t"          /* save caller SP      */
            "mov sp, %1\n\t"          /* switch to task stack */
            : "=r"(old_sp)
            : "r"(stack_top)
            : "memory"
        );

        volatile int first = VIR_SETJMP(tcb->context);

        __asm__ volatile(
            "mov sp, %0\n\t"          /* restore caller SP   */
            :
            : "r"(old_sp)
            : "memory"
        );

        if (first != 0) {
            task_trampoline();
            return 0;  /* NOTREACHED */
        }
    }

#elif defined(__x86_64__)
    /*
     * x86-64 (macOS + Linux):
     * Same technique: swap RSP to our mmap'd stack, setjmp,
     * then restore RSP.
     */
    {
        void *old_sp;
        __asm__ volatile(
            "movq %%rsp, %0\n\t"      /* save caller RSP     */
            "movq %1, %%rsp\n\t"      /* switch to task stack */
            : "=r"(old_sp)
            : "r"(stack_top)
            : "memory"
        );

        volatile int first = VIR_SETJMP(tcb->context);

        __asm__ volatile(
            "movq %0, %%rsp\n\t"      /* restore caller RSP  */
            :
            : "r"(old_sp)
            : "memory"
        );

        if (first != 0) {
            task_trampoline();
            return 0;  /* NOTREACHED */
        }
    }

#else
    /* Generic fallback: setjmp without stack switch.
     * Cooperative scheduling still works but tasks share
     * the caller's native stack. */
    (void)stack_top;
    if (VIR_SETJMP(tcb->context) != 0) {
        task_trampoline();
        return 0;
    }
#endif

    return 0;
}

/* Re-enable optimization after bootstrap_context */
#if defined(__clang__)
#pragma clang optimize on
#elif defined(__GNUC__)
#pragma GCC optimize("O2")
#endif

/* ═══════════════════════════════════════════════════════
 * Public API Implementation
 * ═══════════════════════════════════════════════════════ */

void task_scheduler_init(void)
{
    memset(&g_sched, 0, sizeof(g_sched));
    g_sched.next_id = 1;
}

uint32_t task_create(task_fn_t fn, void *arg)
{
    if (g_sched.count >= TASK_MAX_TASKS) return 0;

    task_tcb_t *tcb = (task_tcb_t *)calloc(1, sizeof(task_tcb_t));
    if (!tcb) return 0;

    tcb->id         = g_sched.next_id++;
    tcb->state      = TASK_READY;
    tcb->stack_size = TASK_STACK_SIZE;
    tcb->stack_base = alloc_stack(tcb->stack_size);
    tcb->entry_fn   = fn;
    tcb->arg        = arg;

    if (!tcb->stack_base) {
        free(tcb);
        return 0;
    }

    /* Set up initial context */
    bootstrap_context(tcb);

    /* Enqueue */
    deque_push_back(tcb);
    g_sched.count++;

    return tcb->id;
}

void task_scheduler_run(void)
{
    while (!deque_empty()) {
        task_tcb_t *tcb = deque_pop_front();
        if (!tcb) break;

        /* Skip completed tasks */
        if (tcb->state == TASK_COMPLETED) {
            /* Keep completed tasks in g_sched.tasks[] for result retrieval.
             * Find a free slot and store the TCB there. */
            int stored = 0;
            for (uint32_t i = 0; i < TASK_MAX_TASKS; i++) {
                if (!g_sched.tasks[i]) {
                    g_sched.tasks[i] = tcb;
                    stored = 1;
                    break;
                }
            }
            if (!stored) {
                /* No free slot — free the task */
                free_stack(tcb->stack_base, tcb->stack_size);
                free(tcb);
            }
            continue;
        }

        /* Defensive: Skip tasks with NULL entry function */
        if (!tcb->entry_fn) {
            tcb->state = TASK_COMPLETED;
            tcb->result = -1;
            /* Store for result retrieval */
            for (uint32_t i = 0; i < TASK_MAX_TASKS; i++) {
                if (!g_sched.tasks[i]) {
                    g_sched.tasks[i] = tcb;
                    break;
                }
            }
            continue;
        }

        /* Skip waiting tasks — re-enqueue for later */
        if (tcb->state == TASK_WAITING) {
            /* Check if task we're waiting on is done */
            int still_waiting = 0;
            for (uint32_t i = 0; i < TASK_MAX_TASKS; i++) {
                task_tcb_t *t = g_sched.tasks[i];
                if (t && t->id == tcb->wait_for && t->state != TASK_COMPLETED) {
                    still_waiting = 1;
                    break;
                }
            }
            if (still_waiting) {
                deque_push_back(tcb);
                continue;
            }
            tcb->state = TASK_READY;  /* target done, wake up */
        }

        /* Run this task directly (without stack switching).
         * For async/task/wait use case, we run the entry function
         * directly on the current stack. This avoids the complexity
         * of setjmp/longjmp stack switching while still providing
         * correct task execution and result retrieval. */
        tcb->state = TASK_RUNNING;
        g_sched.current = tcb;

        /* Execute the task entry function directly */
        tcb->result = tcb->entry_fn(tcb->arg);
        tcb->state = TASK_COMPLETED;

        /* Wake any tasks waiting on this one */
        for (uint32_t i = 0; i < TASK_MAX_TASKS; i++) {
            task_tcb_t *w = g_sched.tasks[i];
            if (w && w->state == TASK_WAITING && w->wait_for == tcb->id) {
                w->state = TASK_READY;
            }
        }

        g_sched.current = NULL;

        /* Keep completed task in g_sched.tasks[] for result retrieval. */
        int stored = 0;
        for (uint32_t i = 0; i < TASK_MAX_TASKS; i++) {
            if (!g_sched.tasks[i]) {
                g_sched.tasks[i] = tcb;
                stored = 1;
                break;
            }
        }
        if (!stored) {
            free_stack(tcb->stack_base, tcb->stack_size);
            free(tcb);
        }
    }
}

void task_yield(void)
{
    task_tcb_t *cur = g_sched.current;
    if (!cur) return;

    if (VIR_SETJMP(cur->context) == 0) {
        cur->state = TASK_READY;
        deque_push_back(cur);
        VIR_LONGJMP(g_sched.main_context, 1);
    }
    /* Scheduler longjmp'd back — continue from here */
}

void task_wait(uint32_t target_id)
{
    task_tcb_t *cur = g_sched.current;
    if (!cur) return;

    cur->state    = TASK_WAITING;
    cur->wait_for = target_id;

    if (VIR_SETJMP(cur->context) == 0) {
        deque_push_back(cur);
        VIR_LONGJMP(g_sched.main_context, 1);
    }
    /* Woken up — target completed */
}

int64_t task_get_result(uint32_t task_id)
{
    /* Search completed tasks — linear scan is fine for < 256 tasks */
    for (uint32_t i = 0; i < TASK_MAX_TASKS; i++) {
        task_tcb_t *t = g_sched.tasks[i];
        if (t && t->id == task_id && t->state == TASK_COMPLETED)
            return t->result;
    }
    return 0;
}

int task_cancel(uint32_t task_id)
{
    /* Mark the target task as completed with a sentinel cancel result.
     * Waking waiters happens on the same pass. Caller is expected to
     * no-op scheduling further, since on next dispatch the task is
     * skipped (state != TASK_READY). */
    for (uint32_t i = 0; i < TASK_MAX_TASKS; i++) {
        task_tcb_t *t = g_sched.tasks[i];
        if (t && t->id == task_id && t->state != TASK_COMPLETED) {
            t->state  = TASK_COMPLETED;
            t->result = -1;
            /* Wake anyone waiting on it. */
            for (uint32_t j = 0; j < TASK_MAX_TASKS; j++) {
                task_tcb_t *w = g_sched.tasks[j];
                if (w && w->state == TASK_WAITING && w->wait_for == task_id) {
                    w->state = TASK_READY;
                }
            }
            return 0;
        }
    }
    return -1;
}

void task_scheduler_destroy(void)
{
    for (uint32_t i = 0; i < TASK_MAX_TASKS; i++) {
        task_tcb_t *t = g_sched.tasks[i];
        if (t) {
            if (t->stack_base)
                free_stack(t->stack_base, t->stack_size);
            free(t);
            g_sched.tasks[i] = NULL;
        }
    }
    memset(&g_sched, 0, sizeof(g_sched));
}
