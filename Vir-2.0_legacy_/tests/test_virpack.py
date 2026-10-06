"""
Tests for VirPack — C ABI bridge and Python thin binding.
============================================================
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.virpack.c_abi import (
    CABIType, CABIParam, CABISignature,
    gemm_signature, elementwise_binary_signature,
    elementwise_unary_signature, reduce_signature,
    generate_vir_kernel_header,
)
from src.virpack.python import VirKernels
from src.virplat.capability_profile import VectorBackend


# =============================================================================
#  C ABI tests
# =============================================================================

def test_gemm_signature():
    sig = gemm_signature()
    assert sig.name == "vir_gemm_f32"
    assert len(sig.params) == 6
    decl = sig.c_declaration()
    assert "void" in decl
    assert "float*" in decl
    assert "size_t" in decl


def test_binary_signature():
    sig = elementwise_binary_signature("add")
    assert sig.name == "vir_add_f32"
    assert len(sig.params) == 4
    assert "float*" in sig.c_declaration()


def test_unary_signature():
    sig = elementwise_unary_signature("relu")
    assert sig.name == "vir_relu_f32"
    assert len(sig.params) == 3


def test_reduce_signature():
    sig = reduce_signature("reduce_sum")
    assert sig.name == "vir_reduce_sum_f32"
    assert sig.return_type == CABIType.FLOAT32
    assert "float" in sig.c_declaration()


def test_header_guard():
    sig = gemm_signature()
    header = sig.c_header_guard("VIR_GEMM_H")
    assert "#ifndef VIR_GEMM_H" in header
    assert "#define VIR_GEMM_H" in header
    assert "#endif" in header
    assert "#include <stdint.h>" in header


def test_generate_header():
    header = generate_vir_kernel_header()
    assert "#ifndef VIR_KERNELS_H" in header
    assert "vir_gemm_f32" in header
    assert "vir_add_f32" in header
    assert "vir_relu_f32" in header
    assert "vir_reduce_sum_f32" in header
    assert 'extern "C"' in header


def test_generate_header_subset():
    header = generate_vir_kernel_header(["gemm", "add"])
    assert "vir_gemm_f32" in header
    assert "vir_add_f32" in header
    assert "vir_relu_f32" not in header


# =============================================================================
#  Python thin binding tests
# =============================================================================

def test_virkernels_init():
    """VirKernels should initialize with auto-detected backend."""
    import src.virmatrix.kernels.scalar.ops  # noqa: F401
    k = VirKernels(backend=VectorBackend.SCALAR)
    assert k.backend == VectorBackend.SCALAR


def test_virkernels_matmul():
    import src.virmatrix.kernels.scalar.ops  # noqa: F401
    k = VirKernels(backend=VectorBackend.SCALAR)
    # (1x2) @ (2x2) = (1x2): [1*3+2*5, 1*4+2*6] = [13, 16]
    result = k.matmul([1.0, 2.0], [3.0, 4.0, 5.0, 6.0], 1, 2, 2)
    assert abs(result[0] - 13.0) < 1e-5
    assert abs(result[1] - 16.0) < 1e-5


def test_virkernels_add():
    import src.virmatrix.kernels.scalar.ops  # noqa: F401
    k = VirKernels(backend=VectorBackend.SCALAR)
    assert k.add([1.0, 2.0], [3.0, 4.0]) == [4.0, 6.0]


def test_virkernels_relu():
    import src.virmatrix.kernels.scalar.ops  # noqa: F401
    k = VirKernels(backend=VectorBackend.SCALAR)
    assert k.relu([-1.0, 0.0, 2.0]) == [0.0, 0.0, 2.0]


def test_virkernels_reduce_sum():
    import src.virmatrix.kernels.scalar.ops  # noqa: F401
    k = VirKernels(backend=VectorBackend.SCALAR)
    assert abs(k.reduce_sum([1.0, 2.0, 3.0]) - 6.0) < 1e-6


def test_virkernels_softmax():
    import src.virmatrix.kernels.scalar.ops  # noqa: F401
    k = VirKernels(backend=VectorBackend.SCALAR)
    r = k.softmax([1.0, 2.0, 3.0])
    assert abs(sum(r) - 1.0) < 1e-5


def test_virkernels_fill():
    import src.virmatrix.kernels.scalar.ops  # noqa: F401
    k = VirKernels(backend=VectorBackend.SCALAR)
    assert k.fill(3, 5.0) == [5.0, 5.0, 5.0]


def test_virkernels_neon_backend():
    """VirKernels should work with NEON backend too."""
    import src.virmatrix.kernels.scalar.ops  # noqa: F401
    import src.virmatrix.kernels.neon.ops  # noqa: F401
    k = VirKernels(backend=VectorBackend.NEON)
    assert k.backend == VectorBackend.NEON
    assert k.add([1.0, 2.0, 3.0, 4.0], [5.0, 6.0, 7.0, 8.0]) == [6.0, 8.0, 10.0, 12.0]
