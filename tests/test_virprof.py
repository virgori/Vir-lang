"""
Tests for VirProf — Timer and StartupProfile.
================================================
"""

import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.virprof.timer import Timer, TimerRecord, profile_block
from src.virprof.startup_profile import StartupProfile


# =============================================================================
#  Timer tests
# =============================================================================

def test_timer_basic():
    """Timer should measure elapsed time."""
    t = Timer("test")
    with t:
        time.sleep(0.01)  # 10ms
    assert t.count == 1
    assert t.total_ns > 0
    assert t.total_ms > 0


def test_timer_multiple():
    """Timer accumulates multiple measurements."""
    t = Timer("multi")
    for _ in range(3):
        with t:
            time.sleep(0.001)
    assert t.count == 3
    assert t.mean_ns > 0


def test_timer_min_max():
    """Timer tracks min/max."""
    t = Timer("minmax")
    with t:
        pass  # fast
    with t:
        time.sleep(0.01)  # slower
    assert t.max_ns >= t.min_ns
    assert t.min_ns >= 0


def test_timer_reset():
    t = Timer("reset")
    with t:
        pass
    assert t.count == 1
    t.reset()
    assert t.count == 0
    assert t.total_ns == 0


def test_timer_last():
    t = Timer("last")
    assert t.last() is None
    with t:
        pass
    rec = t.last()
    assert rec is not None
    assert rec.name == "last"
    assert rec.elapsed_ns >= 0


def test_timer_summary():
    t = Timer("summary")
    with t:
        pass
    s = t.summary()
    assert "summary" in s
    assert "total=" in s
    assert "count=1" in s


def test_timer_record_repr():
    rec = TimerRecord("test_op", 5_000_000, 0, 5_000_000)
    r = repr(rec)
    assert "test_op" in r
    assert "ms" in r  # 5ms should show ms unit

    rec_small = TimerRecord("small", 500, 0, 500)
    r2 = repr(rec_small)
    assert "µs" in r2  # sub-ms should show µs


def test_timer_properties():
    rec = TimerRecord("props", 1_000_000_000, 0, 1_000_000_000)
    assert abs(rec.elapsed_s - 1.0) < 1e-6
    assert abs(rec.elapsed_ms - 1000.0) < 1e-3
    assert abs(rec.elapsed_us - 1_000_000.0) < 1e-1


# =============================================================================
#  profile_block tests
# =============================================================================

def test_profile_block(capsys):
    """profile_block should print timing."""
    with profile_block("test_init") as t:
        pass
    captured = capsys.readouterr()
    assert "[profile]" in captured.out
    assert "test_init" in captured.out


# =============================================================================
#  StartupProfile tests
# =============================================================================

def test_startup_profile_manual():
    """Manual phase recording."""
    sp = StartupProfile()
    sp.begin()
    sp.phase_start("phase_a")
    time.sleep(0.005)
    sp.phase_end(details={"key": "val"})
    sp.phase_start("phase_b")
    sp.phase_end()
    sp.finish()

    assert len(sp.phases) == 2
    assert sp.phases[0].name == "phase_a"
    assert sp.phases[0].elapsed_ms > 0
    assert sp.phases[0].details == {"key": "val"}
    assert sp.total_ms > 0


def test_startup_profile_report():
    sp = StartupProfile()
    sp.begin()
    sp.phase_start("init")
    sp.phase_end()
    sp.finish()
    report = sp.report()
    assert "Vir Startup Profile" in report
    assert "init" in report
    assert "Total:" in report


def test_startup_profile_full():
    """Full startup profile should run without error."""
    sp = StartupProfile()
    sp.profile_full_startup()
    assert sp.total_ms > 0
    assert len(sp.phases) >= 3  # cpu_probe + scalar + neon + registry
    report = sp.report()
    assert "cpu_probe" in report
