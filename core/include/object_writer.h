#ifndef VIR_OBJECT_WRITER_H
#define VIR_OBJECT_WRITER_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

// Allocates executable memory and copies the binary buffer into it.
// Returns a function pointer that can be cast and executed.
void* mach_emit_executable_memory(const uint8_t *buffer, size_t size);

// Frees the executable memory.
void mach_free_executable_memory(void *ptr, size_t size);

#ifdef __cplusplus
}
#endif

#endif // VIR_OBJECT_WRITER_H
