#include "object_writer.h"
#include <sys/mman.h>
#include <string.h>
#include <stdio.h>

#if defined(__APPLE__) && defined(__aarch64__)
#include <pthread.h>
#include <libkern/OSCacheControl.h>
#endif

void* mach_emit_executable_memory(const uint8_t *buffer, size_t size) {
    if (!buffer || size == 0) return NULL;
    
    // Allocate memory with RWX permissions (or RW, then RX if strict)
    // On Apple Silicon, we must use MAP_JIT and toggle thread permissions.
    int flags = MAP_PRIVATE | MAP_ANONYMOUS;
#if defined(__APPLE__) && defined(__aarch64__)
    flags |= MAP_JIT;
#endif

    void *mem = mmap(NULL, size, PROT_READ | PROT_WRITE | PROT_EXEC, flags, -1, 0);
    if (mem == MAP_FAILED) {
        perror("mmap failed");
        return NULL;
    }
    
#if defined(__APPLE__) && defined(__aarch64__)
    pthread_jit_write_protect_np(0); // Disable write protection
#endif

    // Copy encoded bytes into executable memory
    memcpy(mem, buffer, size);
    
#if defined(__APPLE__) && defined(__aarch64__)
    pthread_jit_write_protect_np(1); // Enable write protection, allow execution
    sys_icache_invalidate(mem, size);
#endif

    return mem;
}

void mach_free_executable_memory(void *ptr, size_t size) {
    if (ptr) {
        munmap(ptr, size);
    }
}
