/* ═══════════════════════════════════════════════════════════════════
 * gpu_metal.c — Apple Metal GPU Backend via Objective-C Runtime
 * ═══════════════════════════════════════════════════════════════════
 * Zero-dependency Metal device management + MSL compilation.
 * Uses objc_msgSend + dlopen instead of linking Metal.framework.
 *
 * This allows compiling on ALL platforms; at runtime, Metal calls
 * simply fail gracefully if Metal.framework is absent.
 * ═══════════════════════════════════════════════════════════════════ */

#include "gpu_metal.h"
#include "q_ir.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* ═══════════════════════════════════════════════════════
 * Objective-C Runtime Stubs (zero-dependency)
 * ═══════════════════════════════════════════════════════ */

#if defined(__APPLE__)

#include <dlfcn.h>
#include <objc/objc.h>
#include <objc/message.h>
#include <objc/runtime.h>

/* Objective-C ABI: id objc_msgSend(id self, SEL op, ...) */
typedef id (*msg_send_t)(id, SEL, ...);
typedef id (*msg_send_ptr_t)(id, SEL, const void*, size_t, unsigned long);

static struct {
    bool         initialized;
    void        *metal_lib;         /* Metal.framework handle */
    id           device;            /* MTLDevice */
    id           command_queue;     /* MTLCommandQueue */
    /* Cached selectors */
    SEL          sel_name;
    SEL          sel_new_cmd_buf;
    SEL          sel_new_lib_src;
    SEL          sel_new_func;
    SEL          sel_new_pipeline;
    SEL          sel_new_buffer;
    SEL          sel_new_buffer_data;
    SEL          sel_contents;
    SEL          sel_commit;
    SEL          sel_wait;
    SEL          sel_encode;
    SEL          sel_set_pipeline;
    SEL          sel_set_buffer;
    SEL          sel_dispatch;
    SEL          sel_end_encoding;
    SEL          sel_release;
    SEL          sel_length;
    SEL          sel_max_threads;
    SEL          sel_rec_max_ws;
    SEL          sel_max_tg_mem;
    SEL          sel_is_low_power;
    SEL          sel_is_headless;
    SEL          sel_supports_family;
} metal_state = {0};

/* Helper: get ObjC string (NSString) contents */
static const char *nsstring_utf8(id ns_str) {
    if (!ns_str) return "(null)";
    SEL sel = sel_registerName("UTF8String");
    return (const char *)((msg_send_t)objc_msgSend)(ns_str, sel);
}

/* Helper: create NSString from C string */
static id nsstring_from(const char *s) {
    Class NSString = objc_getClass("NSString");
    SEL sel = sel_registerName("stringWithUTF8String:");
    return ((msg_send_t)objc_msgSend)((id)NSString, sel, s);
}

/* ═══════════════════════════════════════════════════════
 * Init / Shutdown
 * ═══════════════════════════════════════════════════════ */

int vir_metal_init(void) {
    if (metal_state.initialized) return 0;

    /* Try to load Metal.framework */
    metal_state.metal_lib = dlopen(
        "/System/Library/Frameworks/Metal.framework/Metal", RTLD_LAZY);
    if (!metal_state.metal_lib) {
        fprintf(stderr, "[vir-metal] Metal.framework not available\n");
        return -1;
    }

    /* Get default device: MTLCreateSystemDefaultDevice() */
    typedef id (*create_device_fn)(void);
    create_device_fn create_device = (create_device_fn)dlsym(
        metal_state.metal_lib, "MTLCreateSystemDefaultDevice");
    if (!create_device) {
        fprintf(stderr, "[vir-metal] MTLCreateSystemDefaultDevice not found\n");
        dlclose(metal_state.metal_lib);
        return -1;
    }

    metal_state.device = create_device();
    if (!metal_state.device) {
        fprintf(stderr, "[vir-metal] No Metal device available\n");
        dlclose(metal_state.metal_lib);
        return -1;
    }

    /* Create command queue */
    SEL sel_new_q = sel_registerName("newCommandQueue");
    metal_state.command_queue = ((msg_send_t)objc_msgSend)(
        metal_state.device, sel_new_q);
    if (!metal_state.command_queue) {
        fprintf(stderr, "[vir-metal] Failed to create command queue\n");
        dlclose(metal_state.metal_lib);
        return -1;
    }

    /* Cache selectors */
    metal_state.sel_name          = sel_registerName("name");
    metal_state.sel_new_cmd_buf   = sel_registerName("commandBuffer");
    metal_state.sel_new_lib_src   = sel_registerName("newLibraryWithSource:options:error:");
    metal_state.sel_new_func      = sel_registerName("newFunctionWithName:");
    metal_state.sel_new_pipeline  = sel_registerName("newComputePipelineStateWithFunction:error:");
    metal_state.sel_new_buffer    = sel_registerName("newBufferWithLength:options:");
    metal_state.sel_new_buffer_data = sel_registerName("newBufferWithBytes:length:options:");
    metal_state.sel_contents      = sel_registerName("contents");
    metal_state.sel_commit        = sel_registerName("commit");
    metal_state.sel_wait          = sel_registerName("waitUntilCompleted");
    metal_state.sel_encode        = sel_registerName("computeCommandEncoder");
    metal_state.sel_set_pipeline  = sel_registerName("setComputePipelineState:");
    metal_state.sel_set_buffer    = sel_registerName("setBuffer:offset:atIndex:");
    metal_state.sel_dispatch      = sel_registerName("dispatchThreadgroups:threadsPerThreadgroup:");
    metal_state.sel_end_encoding  = sel_registerName("endEncoding");
    metal_state.sel_release       = sel_registerName("release");
    metal_state.sel_length        = sel_registerName("length");
    metal_state.sel_max_threads   = sel_registerName("maxTotalThreadsPerThreadgroup");
    metal_state.sel_rec_max_ws    = sel_registerName("recommendedMaxWorkingSetSize");
    metal_state.sel_max_tg_mem    = sel_registerName("maxThreadgroupMemoryLength");
    metal_state.sel_is_low_power  = sel_registerName("isLowPower");
    metal_state.sel_is_headless   = sel_registerName("isHeadless");
    metal_state.sel_supports_family = sel_registerName("supportsFamily:");

    metal_state.initialized = true;
    return 0;
}

void vir_metal_shutdown(void) {
    if (!metal_state.initialized) return;
    /* Release queue and device (ARC handles in most cases) */
    if (metal_state.metal_lib) {
        dlclose(metal_state.metal_lib);
    }
    memset(&metal_state, 0, sizeof(metal_state));
}

bool vir_metal_available(void) {
    if (metal_state.initialized) return true;
    /* Quick probe */
    void *lib = dlopen("/System/Library/Frameworks/Metal.framework/Metal", RTLD_LAZY);
    if (lib) { dlclose(lib); return true; }
    return false;
}

/* ═══════════════════════════════════════════════════════
 * Device Info
 * ═══════════════════════════════════════════════════════ */

int vir_metal_device_info(vir_metal_device_info_t *info) {
    if (!metal_state.initialized) return -1;
    memset(info, 0, sizeof(*info));

    id dev = metal_state.device;
    msg_send_t send = (msg_send_t)objc_msgSend;

    /* Name */
    id name_ns = send(dev, metal_state.sel_name);
    const char *name = nsstring_utf8(name_ns);
    if (name) {
        strncpy(info->name, name, sizeof(info->name) - 1);
    }

    /* Recommended max working set */
    info->recommended_max_working_set_size =
        (uint64_t)send(dev, metal_state.sel_rec_max_ws);

    /* Max threads per threadgroup */
    info->max_threads_per_threadgroup =
        (uint32_t)(uintptr_t)send(dev, metal_state.sel_max_threads);

    /* Max threadgroup memory */
    info->max_threadgroup_memory_length =
        (uint32_t)(uintptr_t)send(dev, metal_state.sel_max_tg_mem);

    /* Low power / headless */
    info->is_low_power = (bool)(uintptr_t)send(dev, metal_state.sel_is_low_power);
    info->is_headless  = (bool)(uintptr_t)send(dev, metal_state.sel_is_headless);

    /* GPU family support (Apple GPUFamily) */
    /* Apple7=1007, Apple8=1008, Apple9=1009 (MTLGPUFamily enum values) */
    info->supports_family_apple7 =
        (bool)(uintptr_t)send(dev, metal_state.sel_supports_family, (uintptr_t)1007);
    info->supports_family_apple8 =
        (bool)(uintptr_t)send(dev, metal_state.sel_supports_family, (uintptr_t)1008);
    info->supports_family_apple9 =
        (bool)(uintptr_t)send(dev, metal_state.sel_supports_family, (uintptr_t)1009);

    return 0;
}

/* ═══════════════════════════════════════════════════════
 * Shader Compilation
 * ═══════════════════════════════════════════════════════ */

MTLLibrary_h vir_metal_compile_msl(const char *msl_source, size_t len) {
    if (!metal_state.initialized || !msl_source) return NULL;
    (void)len;

    msg_send_t send = (msg_send_t)objc_msgSend;
    id source_ns = nsstring_from(msl_source);
    id error = nil;

    /* [device newLibraryWithSource:source options:nil error:&error] */
    id library = send(metal_state.device, metal_state.sel_new_lib_src,
                      source_ns, nil, &error);
    if (!library || error) {
        if (error) {
            SEL desc = sel_registerName("localizedDescription");
            id desc_ns = send(error, desc);
            fprintf(stderr, "[vir-metal] MSL compile error: %s\n",
                    nsstring_utf8(desc_ns));
        }
        return NULL;
    }
    return (MTLLibrary_h)library;
}

void vir_metal_release_library(MTLLibrary_h lib) {
    if (lib) {
        ((msg_send_t)objc_msgSend)((id)lib, metal_state.sel_release);
    }
}

MTLFunction_h vir_metal_get_function(MTLLibrary_h lib, const char *name) {
    if (!lib || !name) return NULL;
    id name_ns = nsstring_from(name);
    return (MTLFunction_h)((msg_send_t)objc_msgSend)(
        (id)lib, metal_state.sel_new_func, name_ns);
}

void vir_metal_release_function(MTLFunction_h func) {
    if (func) {
        ((msg_send_t)objc_msgSend)((id)func, metal_state.sel_release);
    }
}

MTLComputePipelineState_h vir_metal_create_pipeline(MTLFunction_h func) {
    if (!metal_state.initialized || !func) return NULL;
    id error = nil;
    id pso = ((msg_send_t)objc_msgSend)(
        metal_state.device, metal_state.sel_new_pipeline, func, &error);
    if (!pso || error) {
        if (error) {
            SEL desc = sel_registerName("localizedDescription");
            id desc_ns = ((msg_send_t)objc_msgSend)(error, desc);
            fprintf(stderr, "[vir-metal] Pipeline error: %s\n",
                    nsstring_utf8(desc_ns));
        }
        return NULL;
    }
    return (MTLComputePipelineState_h)pso;
}

void vir_metal_release_pipeline(MTLComputePipelineState_h pso) {
    if (pso) {
        ((msg_send_t)objc_msgSend)((id)pso, metal_state.sel_release);
    }
}

/* ═══════════════════════════════════════════════════════
 * Buffer Management
 * ═══════════════════════════════════════════════════════ */

MTLBuffer_h vir_metal_buffer_create(size_t size) {
    if (!metal_state.initialized) return NULL;
    /* MTLResourceStorageModeShared = 0 */
    return (MTLBuffer_h)((msg_send_t)objc_msgSend)(
        metal_state.device, metal_state.sel_new_buffer,
        (uintptr_t)size, (uintptr_t)0);
}

MTLBuffer_h vir_metal_buffer_create_with_data(const void *data, size_t size) {
    if (!metal_state.initialized || !data) return NULL;
    return (MTLBuffer_h)((msg_send_ptr_t)objc_msgSend)(
        metal_state.device, metal_state.sel_new_buffer_data,
        data, size, 0UL);
}

void *vir_metal_buffer_contents(MTLBuffer_h buf) {
    if (!buf) return NULL;
    return (void *)((msg_send_t)objc_msgSend)((id)buf, metal_state.sel_contents);
}

void vir_metal_buffer_release(MTLBuffer_h buf) {
    if (buf) {
        ((msg_send_t)objc_msgSend)((id)buf, metal_state.sel_release);
    }
}

/* ═══════════════════════════════════════════════════════
 * Compute Dispatch
 * ═══════════════════════════════════════════════════════ */

/* MTLSize struct layout matches {width, height, depth} — 3 x NSUInteger */
typedef struct { unsigned long w, h, d; } mtl_size_t;

int vir_metal_dispatch(MTLComputePipelineState_h pso,
                       MTLBuffer_h *buffers, int num_buffers,
                       const vir_metal_launch_config_t *config) {
    if (!metal_state.initialized || !pso || !config) return -1;

    msg_send_t send = (msg_send_t)objc_msgSend;

    /* Create command buffer */
    id cmd_buf = send(metal_state.command_queue, metal_state.sel_new_cmd_buf);
    if (!cmd_buf) return -1;

    /* Create compute encoder */
    id encoder = send(cmd_buf, metal_state.sel_encode);
    if (!encoder) return -1;

    /* Set pipeline state */
    send(encoder, metal_state.sel_set_pipeline, pso);

    /* Bind buffers */
    for (int i = 0; i < num_buffers; i++) {
        /* [encoder setBuffer:buf offset:0 atIndex:i] */
        send(encoder, metal_state.sel_set_buffer, buffers[i], (uintptr_t)0, (uintptr_t)i);
    }

    /* Dispatch threadgroups */
    mtl_size_t grid = { config->grid_x, config->grid_y, config->grid_z };
    mtl_size_t tg   = { config->threadgroup_x, config->threadgroup_y, config->threadgroup_z };

    /* dispatchThreadgroups:threadsPerThreadgroup: takes MTLSize by value */
    /* On ARM64 ABI, small structs are passed in registers */
    typedef void (*dispatch_fn)(id, SEL, mtl_size_t, mtl_size_t);
    ((dispatch_fn)objc_msgSend)(encoder, metal_state.sel_dispatch, grid, tg);

    /* End encoding */
    send(encoder, metal_state.sel_end_encoding);

    /* Commit */
    send(cmd_buf, metal_state.sel_commit);

    /* Wait */
    send(cmd_buf, metal_state.sel_wait);

    return 0;
}

int vir_metal_sync(void) {
    /* Metal dispatch with waitUntilCompleted is synchronous */
    return 0;
}

/* ═══════════════════════════════════════════════════════
 * Q-IR → MSL Emitter
 * ═══════════════════════════════════════════════════════ */

static int msl_append(char *buf, size_t cap, int pos, const char *fmt, ...) {
    if (pos < 0 || (size_t)pos >= cap) return pos;
    va_list ap;
    va_start(ap, fmt);
    int n = vsnprintf(buf + pos, cap - (size_t)pos, fmt, ap);
    va_end(ap);
    return (n > 0) ? pos + n : pos;
}

int vir_msl_generate_kernel(const vir_msl_kernel_desc_t *desc,
                            const q_instruction_t *instrs, int count,
                            char *out_buf, size_t out_cap) {
    if (!desc || !instrs || !out_buf || out_cap < 256) return -1;

    int p = 0;

    /* Header */
    p = msl_append(out_buf, out_cap, p,
        "#include <metal_stdlib>\n"
        "using namespace metal;\n\n");

    /* Kernel signature */
    p = msl_append(out_buf, out_cap, p,
        "kernel void %s(\n", desc->name);

    for (int i = 0; i < desc->num_params; i++) {
        const char *type = (desc->param_sizes[i] == 8) ? "float" : "float";
        p = msl_append(out_buf, out_cap, p,
            "    device %s *p%d [[buffer(%d)]]%s\n",
            type, i, i, (i < desc->num_params - 1) ? "," : ",");
    }

    p = msl_append(out_buf, out_cap, p,
        "    uint tid [[thread_position_in_grid]]\n) {\n");

    /* Thread index */
    p = msl_append(out_buf, out_cap, p,
        "    const uint idx = tid;\n");

    /* Emit MSL from Q-IR */
    for (int i = 0; i < count; i++) {
        const q_instruction_t *instr = &instrs[i];

        switch (instr->opcode) {
        case Q_ADD:
            p = msl_append(out_buf, out_cap, p,
                "    p%u[idx] = p%u[idx] + p%u[idx];\n",
                instr->dest.vreg, instr->src1.vreg, instr->src2.vreg);
            break;
        case Q_SUB:
            p = msl_append(out_buf, out_cap, p,
                "    p%u[idx] = p%u[idx] - p%u[idx];\n",
                instr->dest.vreg, instr->src1.vreg, instr->src2.vreg);
            break;
        case Q_MUL:
            p = msl_append(out_buf, out_cap, p,
                "    p%u[idx] = p%u[idx] * p%u[idx];\n",
                instr->dest.vreg, instr->src1.vreg, instr->src2.vreg);
            break;
        case Q_DIV:
            p = msl_append(out_buf, out_cap, p,
                "    if (p%u[idx] != 0) p%u[idx] = p%u[idx] / p%u[idx];\n",
                instr->src2.vreg, instr->dest.vreg,
                instr->src1.vreg, instr->src2.vreg);
            break;
        case Q_LOAD:
            p = msl_append(out_buf, out_cap, p,
                "    float r%u = p%u[idx];\n",
                instr->dest.vreg, instr->src1.vreg);
            break;
        case Q_MOVE:
            p = msl_append(out_buf, out_cap, p,
                "    p%u[idx] = p%u[idx];\n",
                instr->dest.vreg, instr->src1.vreg);
            break;
        case Q_VADD:
            p = msl_append(out_buf, out_cap, p,
                "    /* SIMD add — MSL vectorized */\n"
                "    p%u[idx] = p%u[idx] + p%u[idx];\n",
                instr->dest.vreg, instr->src1.vreg, instr->src2.vreg);
            break;
        case Q_VMUL:
            p = msl_append(out_buf, out_cap, p,
                "    p%u[idx] = p%u[idx] * p%u[idx];\n",
                instr->dest.vreg, instr->src1.vreg, instr->src2.vreg);
            break;
        case Q_NOP:
            break;
        default:
            p = msl_append(out_buf, out_cap, p,
                "    /* unhandled Q-IR op %d */\n", instr->opcode);
            break;
        }
    }

    /* Closing brace */
    p = msl_append(out_buf, out_cap, p, "}\n");

    return p;
}

#else /* !__APPLE__ */

/* ═══════════════════════════════════════════════════════
 * Non-Apple stub implementations
 * ═══════════════════════════════════════════════════════ */

int  vir_metal_init(void) { return -1; }
void vir_metal_shutdown(void) { }
bool vir_metal_available(void) { return false; }
int  vir_metal_device_info(vir_metal_device_info_t *info) { (void)info; return -1; }

MTLLibrary_h vir_metal_compile_msl(const char *s, size_t l) { (void)s;(void)l; return 0; }
void vir_metal_release_library(MTLLibrary_h l) { (void)l; }
MTLFunction_h vir_metal_get_function(MTLLibrary_h l, const char *n) { (void)l;(void)n; return 0; }
void vir_metal_release_function(MTLFunction_h f) { (void)f; }
MTLComputePipelineState_h vir_metal_create_pipeline(MTLFunction_h f) { (void)f; return 0; }
void vir_metal_release_pipeline(MTLComputePipelineState_h p) { (void)p; }

MTLBuffer_h vir_metal_buffer_create(size_t s) { (void)s; return 0; }
MTLBuffer_h vir_metal_buffer_create_with_data(const void *d, size_t s) { (void)d;(void)s; return 0; }
void *vir_metal_buffer_contents(MTLBuffer_h b) { (void)b; return 0; }
void vir_metal_buffer_release(MTLBuffer_h b) { (void)b; }

int vir_metal_dispatch(MTLComputePipelineState_h p, MTLBuffer_h *b, int n,
                       const vir_metal_launch_config_t *c) { (void)p;(void)b;(void)n;(void)c; return -1; }
int vir_metal_sync(void) { return -1; }

int vir_msl_generate_kernel(const vir_msl_kernel_desc_t *d,
                            const q_instruction_t *i, int c,
                            char *o, size_t oc) { (void)d;(void)i;(void)c;(void)o;(void)oc; return -1; }

#endif /* __APPLE__ */
