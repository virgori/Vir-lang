"""Tests for VirMem — arena, pool, and memory planner."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.virmem.arena import ArenaAllocator
from src.virmem.pool import TempPool
from src.virmem.planner import MemoryPlanner


def test_arena_alloc():
    arena = ArenaAllocator(block_size=1024)
    buf = arena.alloc(100)
    assert len(buf) == 100
    assert arena.peak_bytes > 0

def test_arena_multiple_allocs():
    arena = ArenaAllocator(block_size=256)
    b1 = arena.alloc(100)
    b2 = arena.alloc(100)
    b3 = arena.alloc(100)
    assert len(b1) == 100 and len(b2) == 100 and len(b3) == 100

def test_arena_reset():
    arena = ArenaAllocator(block_size=512)
    arena.alloc(200)
    arena.reset()
    buf = arena.alloc(200)
    assert len(buf) == 200

def test_pool_acquire_release():
    pool = TempPool()
    buf = pool.acquire(64)
    assert len(buf) == 64
    pool.release(buf)
    buf2 = pool.acquire(64)
    assert len(buf2) == 64

def test_pool_clear():
    pool = TempPool()
    pool.acquire(32)
    pool.acquire(64)
    pool.clear()

def test_memory_planner():
    planner = MemoryPlanner()
    planner.add_interval(tensor_id=0, size_bytes=100, start=0, end=3)
    planner.add_interval(tensor_id=1, size_bytes=200, start=1, end=4)
    planner.add_interval(tensor_id=2, size_bytes=100, start=4, end=6)
    assignments = planner.plan()
    assert planner.peak_bytes > 0
    assert planner.num_buffers >= 1
    assert len(assignments) == 3
