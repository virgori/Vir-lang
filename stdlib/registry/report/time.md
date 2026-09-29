# `time` — harden report

**Date:** 2026-09-29 (wave close)  
**Source:** `stdlib/vir/time/time.vri`  
**Registry:** [`../time.md`](../time.md) (SCHEMA — single namespace `time.*`)

## Surface

- Public **only** `time.<method>` + types `Duration`, `Timer`.
- Monotonic stamp: **`int` nanoseconds** (`time.now()`), not wall clock.
- Wall: `time.unixSecs` / `unixMs` / `unixNs`.
- Sleep / `timerStop`: **`Result`** (`Ok(0)` / `Err` invalid or platform fail).
- Legacy free aliases (`now`, `duration_*`, `time_now`, `Instant`, …) **removed**; dependents migrated in-tree.

## Rename (registry)

| Previous | Public |
|---|---|
| `time.elapsedNanos` | `time.elapsedNs` |
| `time.unixMillis` | `time.unixMs` |
| `unix_timestamp_nanos` | `time.unixNs` |
| `fromMillis` / `toMillis` … | `fromMs` / `toMs` … |
| `timerElapsedNs` / `timerElapsedMs` | `timerNs` / `timerMs` |

## Evidence (`bin/virc`, macos-arm64)

```text
include time
time.now() → time.sleepMs(50) → time.elapsedMs ≥ 20 ms     PASS (exit 0)
time.unixSecs() ≥ 1700000000                               PASS
time.add(time.fromSecs(1), time.fromMs(500)) → toMs == 1500 PASS
time.timer + timerMs + timerStop (Result)                  PASS
```

Compile include `time`: **OK** (libc `clock_gettime` / `nanosleep`; scalar `out` for durations).

## Open (registry)

- Negative `Duration` / overflow on convert+arith — verify.
- Repeated `timerStop`; sleep interruption — verify.
- Log timestamp formatting → `datetime` / future `chrono`, not `time`.

## Verdict

**PASS (Layer-1 wave)** — registry + impl aligned; not certified for leap-second / NTP edge cases.
