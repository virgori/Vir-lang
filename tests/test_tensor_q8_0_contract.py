from __future__ import annotations

import math
import struct
import subprocess
from dataclasses import dataclass, replace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "stdlib/vir/math/tensor_q8_0.vri"
REGISTRY = ROOT / "stdlib/stdlib.vri"
FIXTURE = ROOT / "tests/fixtures/q80_f64le_block.hex"
SEMANTIC_FIXTURE = ROOT / "tests/spec_gap_contract/q80_external_view_semantic.vri"

BLOCK_ELEMENTS = 32
SCALE_BYTES = 8
BLOCK_BYTES = 40
STORAGE_KIND = 80
OWNERSHIP_BORROWED = 0

OK = 0
ERROR_NULL_BASE = 1
ERROR_NULL_GENERATION = 2
ERROR_DEAD_GENERATION = 3
ERROR_STORAGE_KIND = 4
ERROR_WRITABLE_STORAGE = 5
ERROR_RANK = 6
ERROR_SHAPE = 7
ERROR_OFFSET = 8
ERROR_LENGTH = 9
ERROR_STRIDE = 10
ERROR_ALIGNMENT = 11
ERROR_OVERFLOW = 12
ERROR_OWNERSHIP = 17


@dataclass(frozen=True)
class View:
    base: int = 0x1000
    byte_length: int = 80
    byte_offset: int = 0
    view_byte_length: int = 80
    storage_kind: int = STORAGE_KIND
    rank: int = 2
    rows: int = 2
    columns: int = 32
    row_stride_bytes: int = 40
    alignment: int = 8
    read_only: bool = True
    ownership_kind: int = OWNERSHIP_BORROWED
    generation_cell: int = 0x2000
    generation: int = 1
    current_generation: int = 1


def required_row_bytes(columns: int) -> int:
    if columns <= 0 or columns % BLOCK_ELEMENTS:
        return 0
    blocks = columns // BLOCK_ELEMENTS
    if blocks > 230_584_300_921_369_395:
        return 0
    return blocks * BLOCK_BYTES


def validate(view: View) -> int:
    if view.base == 0:
        return ERROR_NULL_BASE
    if view.generation_cell == 0:
        return ERROR_NULL_GENERATION
    if view.current_generation != view.generation:
        return ERROR_DEAD_GENERATION
    if view.storage_kind != STORAGE_KIND:
        return ERROR_STORAGE_KIND
    if not view.read_only:
        return ERROR_WRITABLE_STORAGE
    if view.ownership_kind != OWNERSHIP_BORROWED:
        return ERROR_OWNERSHIP
    if view.rank != 2:
        return ERROR_RANK
    if view.rows <= 0 or view.columns <= 0 or view.columns % BLOCK_ELEMENTS:
        return ERROR_SHAPE
    if view.byte_length <= 0 or view.view_byte_length <= 0:
        return ERROR_LENGTH
    if view.byte_offset < 0 or view.byte_offset > view.byte_length:
        return ERROR_OFFSET
    if view.view_byte_length > view.byte_length - view.byte_offset:
        return ERROR_LENGTH
    if view.alignment < SCALE_BYTES or view.alignment & (view.alignment - 1):
        return ERROR_ALIGNMENT
    max_i64 = (1 << 63) - 1
    if view.base < 0 or view.byte_offset > max_i64 - view.base:
        return ERROR_OVERFLOW
    view_address = view.base + view.byte_offset
    if view.view_byte_length > max_i64 - view_address:
        return ERROR_OVERFLOW
    if (view.base + view.byte_offset) % view.alignment:
        return ERROR_ALIGNMENT
    row_bytes = required_row_bytes(view.columns)
    if row_bytes == 0:
        return ERROR_OVERFLOW
    if view.row_stride_bytes < row_bytes or view.row_stride_bytes % BLOCK_BYTES:
        return ERROR_STRIDE
    if row_bytes > view.view_byte_length:
        return ERROR_LENGTH
    if view.rows > 1:
        remaining_rows = view.rows - 1
        if remaining_rows > (view.view_byte_length - row_bytes) // view.row_stride_bytes:
            return ERROR_LENGTH
    return OK


def decode_block(block: bytes) -> tuple[float, tuple[int, ...]]:
    assert len(block) == BLOCK_BYTES
    scale = struct.unpack_from("<d", block)[0]
    values = struct.unpack_from("<32b", block, SCALE_BYTES)
    return scale, values


def gemv_scalar(packed: bytes, rows: int, columns: int, activations: list[float]) -> list[float]:
    assert columns % BLOCK_ELEMENTS == 0
    row_stride = required_row_bytes(columns)
    output = []
    for row in range(rows):
        total = 0.0
        for block_index in range(columns // BLOCK_ELEMENTS):
            start = row * row_stride + block_index * BLOCK_BYTES
            scale, values = decode_block(packed[start : start + BLOCK_BYTES])
            act_start = block_index * BLOCK_ELEMENTS
            total += scale * sum(
                value * activations[act_start + index]
                for index, value in enumerate(values)
            )
        output.append(total)
    return output


def gemv_two_lane(packed: bytes, rows: int, columns: int, activations: list[float]) -> list[float]:
    row_stride = required_row_bytes(columns)
    output = []
    for row in range(rows):
        total = 0.0
        for block_index in range(columns // BLOCK_ELEMENTS):
            start = row * row_stride + block_index * BLOCK_BYTES
            scale, values = decode_block(packed[start : start + BLOCK_BYTES])
            lanes = [0.0, 0.0]
            act_start = block_index * BLOCK_ELEMENTS
            for index in range(0, BLOCK_ELEMENTS, 2):
                lanes[0] += values[index] * activations[act_start + index]
                lanes[1] += values[index + 1] * activations[act_start + index + 1]
            total += (lanes[0] + lanes[1]) * scale
        output.append(total)
    return output


def fixture_bytes() -> bytes:
    payload = "".join(
        line.strip()
        for line in FIXTURE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )
    return bytes.fromhex(payload)


def test_authoritative_f64le_codec_fixture() -> None:
    block = fixture_bytes()
    scale, values = decode_block(block)
    assert len(block) == BLOCK_BYTES
    assert scale == 0.5
    assert values == tuple(range(-16, 16))
    assert gemv_scalar(block, 1, 32, [1.0] * 32) == [-8.0]


def test_scalar_two_lane_and_batched_paths_match() -> None:
    first = fixture_bytes()
    second = struct.pack("<d32b", 2.0, *([127, -128] * 16))
    packed = first + second
    batches = [
        [1.0] * 32,
        [float(index - 8) / 4.0 for index in range(32)],
    ]
    scalar = [gemv_scalar(packed, 2, 32, row) for row in batches]
    two_lane = [gemv_two_lane(packed, 2, 32, row) for row in batches]
    assert scalar == two_lane
    assert scalar[0] == [-8.0, -32.0]
    assert all(math.isfinite(value) for row in scalar for value in row)


def test_view_rejects_every_malformed_contract_class() -> None:
    valid = View()
    assert validate(valid) == OK
    cases = [
        (replace(valid, base=0), ERROR_NULL_BASE),
        (replace(valid, generation_cell=0), ERROR_NULL_GENERATION),
        (replace(valid, current_generation=2), ERROR_DEAD_GENERATION),
        (replace(valid, storage_kind=34), ERROR_STORAGE_KIND),
        (replace(valid, read_only=False), ERROR_WRITABLE_STORAGE),
        (replace(valid, ownership_kind=1), ERROR_OWNERSHIP),
        (replace(valid, rank=1), ERROR_RANK),
        (replace(valid, columns=33), ERROR_SHAPE),
        (replace(valid, byte_offset=-1), ERROR_OFFSET),
        (replace(valid, view_byte_length=81), ERROR_LENGTH),
        (replace(valid, row_stride_bytes=39), ERROR_STRIDE),
        (replace(valid, alignment=3), ERROR_ALIGNMENT),
        (replace(valid, base=0x1004), ERROR_ALIGNMENT),
        (
            replace(
                valid,
                base=(1 << 63) - 40,
                byte_length=128,
                byte_offset=48,
            ),
            ERROR_OVERFLOW,
        ),
        (replace(valid, rows=3), ERROR_LENGTH),
        (replace(valid, columns=1 << 63), ERROR_OVERFLOW),
    ]
    for malformed, expected in cases:
        assert validate(malformed) == expected


def test_registered_module_contains_borrowed_view_and_vector_kernel() -> None:
    source = MODULE.read_text(encoding="utf-8")
    registry = REGISTRY.read_text(encoding="utf-8")
    assert "math.tensor_q8_0 = math/tensor_q8_0.vri" in registry
    for field in (
        "base: ptr",
        "byteLength: int",
        "byteOffset: int",
        "viewByteLength: int",
        "storageKind: int",
        "rows: int",
        "columns: int",
        "rowStrideBytes: int",
        "alignment: int",
        "readOnly: bool",
        "ownershipKind: int",
        "generationCell: ptr",
        "generation: int",
    ):
        assert field in source
    assert "flux of (float, 2)" in source
    assert "native_read_f64(block as int, 0)" in source
    assert "func q80GemvScalar:" in source
    assert "func q80GemvSimd:" in source
    assert "func q80GemvNeon:" in source
    assert "func q80Gemm:" in source


def test_public_api_is_semantically_accepted_by_virc() -> None:
    result = subprocess.run(
        [str(ROOT / "bin/virc"), str(SEMANTIC_FIXTURE), "--check"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
