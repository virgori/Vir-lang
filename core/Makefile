# ═══════════════════════════════════════════════════════════════════
# Vir Engine – Native Core Makefile
# ═══════════════════════════════════════════════════════════════════
# Builds libvir_core as a shared library (.dylib / .so / .dll)
# from C source + platform-specific Assembly.
#
# Usage:
#   make              – build shared library
#   make test         – build and run native tests
#   make clean        – remove build artifacts
#   make install      – copy library to lib/
# ═══════════════════════════════════════════════════════════════════

# ── Detect platform ───────────────────────────────────────
UNAME_S := $(shell uname -s)
UNAME_M := $(shell uname -m)

ifeq ($(UNAME_S),Darwin)
  PLATFORM := macos
  SHARED_EXT := dylib
  SHARED_FLAG := -dynamiclib -install_name @rpath/libvir_core.dylib
  EXTRA_LDFLAGS := -lpthread -lobjc
else ifeq ($(UNAME_S),Linux)
  PLATFORM := linux
  SHARED_EXT := so
  SHARED_FLAG := -shared -Wl,-soname,libvir_core.so
  EXTRA_LDFLAGS := -lpthread -lrt
else ifneq (,$(findstring MINGW,$(UNAME_S))$(findstring MSYS,$(UNAME_S))$(findstring CYGWIN,$(UNAME_S)))
  PLATFORM := windows
  SHARED_EXT := dll
  SHARED_FLAG := -shared -Wl,--out-implib,$(LIB_DIR)/libvir_core.dll.a
  EXTRA_LDFLAGS := -lbcrypt
else
  PLATFORM := unknown
  SHARED_EXT := so
  SHARED_FLAG := -shared
  EXTRA_LDFLAGS :=
endif

# ── Detect architecture ──────────────────────────────────
ifeq ($(UNAME_M),x86_64)
  ARCH := x86_64
  ASM_DIR := asm/x86_64
  ASM_SRC := $(ASM_DIR)/vir_x86_64.S
else ifeq ($(UNAME_M),arm64)
  ARCH := arm64
  ASM_DIR := asm/arm64
  ASM_SRC := $(ASM_DIR)/vir_arm64.S
else ifeq ($(UNAME_M),aarch64)
  ARCH := arm64
  ASM_DIR := asm/arm64
  ASM_SRC := $(ASM_DIR)/vir_arm64.S
else
  ARCH := unknown
  ASM_DIR :=
  ASM_SRC :=
endif

# ── Compiler settings ────────────────────────────────────
CC      := cc
CFLAGS  := -g -Wall -Wextra -Wpedantic -std=c11 -fPIC
CFLAGS  += -Iinclude
CFLAGS  += -DVIR_ARCH_$(shell echo $(ARCH) | tr a-z A-Z)
CFLAGS  += -DVIR_PLATFORM_$(shell echo $(PLATFORM) | tr a-z A-Z)
ASFLAGS := -fPIC

# Debug build
ifneq (,$(filter 1 true yes,$(DEBUG)))
  CFLAGS += -g -O0 -DDEBUG -fsanitize=address
  LDFLAGS += -fsanitize=address
endif

# ── Source files ──────────────────────────────────────────
C_SRCS := src/q_ir.c \
          src/vm.c \
          src/codegen.c \
          src/patcher.c \
          src/bridge.c \
          src/signer.c \
          src/constraints.c \
          src/intrinsics.c \
          src/jit_bridge.c \
          src/ir_lower.c \
          src/hir.c \
          src/hir_lower.c \
          src/mir.c \
          src/mir_lower.c \
          src/mir_cfg.c \
          src/mir_ssa.c \
          src/mir_pass.c \
          src/mir_opt_dce.c \
          src/mir_opt_cp.c \
          src/mir_opt_cf.c \
          src/mir_opt_cfg_cleanup.c \
          src/mir_analysis_def_use.c \
          src/mir_move_resolver.c \
          src/mir_ssa_destruct.c \
          src/mir_verify.c \
          src/lir_lower.c \
          src/lir.c \
          src/lir_liveness.c \
          src/lir_interval.c \
          src/lir_regalloc.c \
          src/lir_opt_coalesce.c \
          src/lir_rewrite.c \
          src/lir_verify.c \
          src/lir_to_qir.c \
          src/compiler_pipeline.c \
          src/borrow_check.c \
          src/mach_isel.c \
          src/mach_ir.c \
          src/mach_encode.c \
          src/target.c \
          src/lexer.c \
          src/parser.c \
          src/diagnostic.c \
          src/cpu_caps.c \
          src/task.c \
          src/vir.c \
          src/huge_alloc.c \
          src/numa_alloc.c \
          src/slab_alloc.c \
          src/simd_dispatch.c \
          src/amx_accel.c \
          src/atomic.c \
          src/gpu_cuda.c \
          src/ptx_gen.c \
          src/simd_index.c \
          src/gpu_metal.c \
          src/mem_manager.c \
          src/wasm_codegen.c

# ── Object files ──────────────────────────────────────────
BUILD_DIR := build
C_OBJS := $(patsubst src/%.c,$(BUILD_DIR)/%.o,$(C_SRCS))
ASM_OBJS :=
ifneq ($(ASM_SRC),)
  ASM_OBJS := $(BUILD_DIR)/vir_$(ARCH).o
endif

ALL_OBJS := $(C_OBJS) $(ASM_OBJS)

# ── Output ────────────────────────────────────────────────
LIB_DIR  := lib
LIB_NAME := libvir_core.$(SHARED_EXT)
LIB_PATH := $(LIB_DIR)/$(LIB_NAME)

# Static library
STATIC_NAME := libvir_core.a
STATIC_PATH := $(LIB_DIR)/$(STATIC_NAME)

# CLI binary
CLI_SRC  := src/main.c
CLI_BIN  := $(BUILD_DIR)/vir

# ══════════════════════════════════════════════════════════
# Targets
# ══════════════════════════════════════════════════════════

.PHONY: all shared static test clean install info

all: shared static cli

shared: $(LIB_PATH)
	@echo "✓ Built $(LIB_PATH) [$(PLATFORM)/$(ARCH)]"

static: $(STATIC_PATH)
	@echo "✓ Built $(STATIC_PATH) [$(PLATFORM)/$(ARCH)]"

cli: $(CLI_BIN)
	@echo "✓ Built $(CLI_BIN) [$(PLATFORM)/$(ARCH)]"

# ── Shared library ────────────────────────────────────────
$(LIB_PATH): $(ALL_OBJS) | $(LIB_DIR)
	$(CC) $(SHARED_FLAG) $(LDFLAGS) $(EXTRA_LDFLAGS) -o $@ $(ALL_OBJS)

# ── Static library ────────────────────────────────────────
$(STATIC_PATH): $(ALL_OBJS) | $(LIB_DIR)
	ar rcs $@ $(ALL_OBJS)

# ── CLI binary ─────────────────────────────────────────────
$(CLI_BIN): $(CLI_SRC) $(STATIC_PATH) | $(BUILD_DIR)
	$(CC) $(CFLAGS) -o $@ $< $(STATIC_PATH) $(EXTRA_LDFLAGS)

# ── Compile C sources ─────────────────────────────────────
$(BUILD_DIR)/%.o: src/%.c | $(BUILD_DIR)
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) -c $< -o $@

# ── Assemble platform ASM ─────────────────────────────────
$(BUILD_DIR)/vir_$(ARCH).o: $(ASM_SRC) | $(BUILD_DIR)
	$(CC) $(ASFLAGS) -c $< -o $@

# ── Create directories ────────────────────────────────────
$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

$(LIB_DIR):
	mkdir -p $(LIB_DIR)

# ══════════════════════════════════════════════════════════
# Test
# ══════════════════════════════════════════════════════════

TEST_SRC := tests/test_native.c
TEST_BIN := $(BUILD_DIR)/test_native

BORROW_TEST_SRC := tests/test_borrow.c
BORROW_TEST_BIN := $(BUILD_DIR)/test_borrow

# Volatile I/O segfault bug condition exploration test
VOLATILE_IO_TEST_SRC := tests/test_volatile_io_segfault.c
VOLATILE_IO_TEST_BIN := $(BUILD_DIR)/test_volatile_io_segfault

# Volatile I/O preservation property test
VOLATILE_IO_PRESERVATION_TEST_SRC := tests/test_volatile_io_preservation.c
VOLATILE_IO_PRESERVATION_TEST_BIN := $(BUILD_DIR)/test_volatile_io_preservation

# Reactive var bug condition exploration test
REACTIVE_VAR_BUG_TEST_SRC := tests/test_reactive_var_bug.c
REACTIVE_VAR_BUG_TEST_BIN := $(BUILD_DIR)/test_reactive_var_bug

# Reactive var preservation property test
REACTIVE_VAR_PRES_TEST_SRC := tests/test_reactive_var_preservation.c
REACTIVE_VAR_PRES_TEST_BIN := $(BUILD_DIR)/test_reactive_var_preservation

test: $(STATIC_PATH) $(TEST_BIN)
	@echo "═══ Running native tests ═══"
	./$(TEST_BIN)

test-borrow: $(BORROW_TEST_BIN)
	@echo "═══ Running borrow checker tests ═══"
	./$(BORROW_TEST_BIN)

$(BORROW_TEST_BIN): $(BORROW_TEST_SRC) $(STATIC_PATH) | $(BUILD_DIR)
	$(CC) $(CFLAGS) -o $@ $< $(STATIC_PATH) $(EXTRA_LDFLAGS)

test-volatile-io: $(STATIC_PATH) $(VOLATILE_IO_TEST_BIN)
	@echo "═══ Running volatile I/O segfault exploration test ═══"
	./$(VOLATILE_IO_TEST_BIN); true

test-volatile-io-preservation: $(STATIC_PATH) $(VOLATILE_IO_PRESERVATION_TEST_BIN)
	@echo "═══ Running volatile I/O preservation property test ═══"
	./$(VOLATILE_IO_PRESERVATION_TEST_BIN)

test-reactive-var-bug: $(STATIC_PATH) $(REACTIVE_VAR_BUG_TEST_BIN)
	@echo "═══ Running reactive var bug condition exploration test ═══"
	cd .. && core/$(REACTIVE_VAR_BUG_TEST_BIN); true

test-reactive-var-preservation: $(STATIC_PATH) $(REACTIVE_VAR_PRES_TEST_BIN)
	@echo "═══ Running reactive var preservation property test ═══"
	./$(REACTIVE_VAR_PRES_TEST_BIN)

$(TEST_BIN): $(TEST_SRC) $(STATIC_PATH) | $(BUILD_DIR)
	$(CC) $(CFLAGS) -o $@ $< $(STATIC_PATH) $(EXTRA_LDFLAGS)

$(VOLATILE_IO_TEST_BIN): $(VOLATILE_IO_TEST_SRC) $(STATIC_PATH) | $(BUILD_DIR)
	$(CC) $(CFLAGS) -o $@ $< $(STATIC_PATH) $(EXTRA_LDFLAGS)

$(VOLATILE_IO_PRESERVATION_TEST_BIN): $(VOLATILE_IO_PRESERVATION_TEST_SRC) $(STATIC_PATH) | $(BUILD_DIR)
	$(CC) $(CFLAGS) -o $@ $< $(STATIC_PATH) $(EXTRA_LDFLAGS)

$(REACTIVE_VAR_BUG_TEST_BIN): $(REACTIVE_VAR_BUG_TEST_SRC) $(STATIC_PATH) | $(BUILD_DIR)
	$(CC) $(CFLAGS) -o $@ $< $(STATIC_PATH) $(EXTRA_LDFLAGS)

$(REACTIVE_VAR_PRES_TEST_BIN): $(REACTIVE_VAR_PRES_TEST_SRC) $(STATIC_PATH) | $(BUILD_DIR)
	$(CC) $(CFLAGS) -o $@ $< $(STATIC_PATH) $(EXTRA_LDFLAGS)

# ══════════════════════════════════════════════════════════
# Micro-Prober (CPU micro-architecture measurement)
# ══════════════════════════════════════════════════════════

PROBER_SRC := src/micro_prober.c
PROBER_BIN := $(BUILD_DIR)/micro_prober

prober: $(PROBER_BIN)
	@echo "✓ Built $(PROBER_BIN) [$(PLATFORM)/$(ARCH)]"

$(PROBER_BIN): $(PROBER_SRC) | $(BUILD_DIR)
	$(CC) $(CFLAGS) -DPROBER_STANDALONE -lm -o $@ $< $(EXTRA_LDFLAGS)

# ══════════════════════════════════════════════════════════
# CPU Capability Detector
# ══════════════════════════════════════════════════════════

CPU_CAPS_SRC := src/cpu_caps.c
CPU_CAPS_BIN := $(BUILD_DIR)/cpu_caps

cpu_caps: $(CPU_CAPS_BIN)
	@echo "✓ Built $(CPU_CAPS_BIN) [$(PLATFORM)/$(ARCH)]"

$(CPU_CAPS_BIN): $(CPU_CAPS_SRC) | $(BUILD_DIR)
	$(CC) $(CFLAGS) -DCPU_CAPS_STANDALONE -o $@ $< $(EXTRA_LDFLAGS)

# ══════════════════════════════════════════════════════════
# Install / Clean
# ══════════════════════════════════════════════════════════

install: shared static
	@echo "Libraries installed to $(LIB_DIR)/"

clean:
	rm -rf $(BUILD_DIR) $(LIB_DIR)
	@echo "✓ Clean"

# ── Info ──────────────────────────────────────────────────
info:
	@echo "Platform:  $(PLATFORM)"
	@echo "Arch:      $(ARCH)"
	@echo "Compiler:  $(CC)"
	@echo "CFLAGS:    $(CFLAGS)"
	@echo "C sources: $(C_SRCS)"
	@echo "ASM:       $(ASM_SRC)"
	@echo "Output:    $(LIB_PATH)"
