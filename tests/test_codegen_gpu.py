"""Quick smoke test for codegen_gpu.py"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.backend.codegen.codegen_gpu import (
    GPUTarget, GPUCodeGenerator, GPUKernel, LaunchConfig,
    detect_gpu_target, load_builtin_kernel, list_builtin_kernels,
    detect_fuseable_chains, compute_launch_config,
)
from src.ir.instructions.q_ir import Opcode, QInstruction, QFunction, VReg, Immediate

errors = 0

# 1. Platform detection
target = detect_gpu_target()
print(f"[1] Detected target: {target}")
assert isinstance(target, GPUTarget)

# 2. Builtin listing
builtins = list_builtin_kernels()
print(f"[2] Builtin kernels: {builtins}")
assert len(builtins) == 5

# 3. Load all builtins
for name in builtins:
    k = load_builtin_kernel(name, target)
    print(f"  {name}: entry={k.name}, block={k.block_size}, {len(k.source)} chars")
    assert len(k.source) > 50
print("[3] All builtins loaded OK")

# 4. Launch config
k = load_builtin_kernel("vadd_f32", target)
cfg = compute_launch_config(1_000_000, k)
print(f"[4] Launch 1M: grid={cfg.grid}, block={cfg.block}")
assert cfg.grid[0] == 3907  # ceil(1M / 256)

# 5. Fusion detection
instrs = [
    QInstruction(Opcode.Q_VADD, VReg(3), VReg(0), VReg(1)),
    QInstruction(Opcode.Q_VMUL, VReg(4), VReg(3), VReg(2)),
    QInstruction(Opcode.Q_VSUB, VReg(5), VReg(4), VReg(0)),
]
chains = detect_fuseable_chains(instrs)
print(f"[5] Fusion chains: {len(chains)}")
assert len(chains) == 1
assert len(chains[0].ops) == 3
assert len(chains[0].input_regs) == 3  # R0, R1, R2

# 6. Dynamic kernel generation
gen = GPUCodeGenerator()
func = QFunction(name="test", body=instrs)
kernels = gen.compile_function(func)
print(f"[6] Generated {len(kernels)} kernel(s)")
assert len(kernels) == 1
k = kernels[0]
print(f"  name={k.name}, target={k.target.value}")
assert k.target == target
assert len(k.source) > 100
# Print first 5 lines
for line in k.source.split("\n")[:5]:
    print(f"    {line}")

# 7. No fusion for single op
single = [QInstruction(Opcode.Q_VADD, VReg(1), VReg(0), VReg(0))]
assert len(detect_fuseable_chains(single)) == 0
print("[7] Single op correctly not fused")

# 8. Non-fuseable break
mixed = [
    QInstruction(Opcode.Q_VADD, VReg(2), VReg(0), VReg(1)),
    QInstruction(Opcode.Q_PRINT, None, VReg(2)),  # breaks chain
    QInstruction(Opcode.Q_VMUL, VReg(3), VReg(2), VReg(0)),
    QInstruction(Opcode.Q_VSUB, VReg(4), VReg(3), VReg(1)),
]
chains2 = detect_fuseable_chains(mixed)
assert len(chains2) == 1  # only the mul+sub chain
assert len(chains2[0].ops) == 2
print("[8] Non-fuseable break handled correctly")

print()
print("All GPU codegen tests PASSED")
