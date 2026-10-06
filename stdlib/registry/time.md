---
module: time
title: Time
summary: Monotonic timing, wall-clock timestamps, durations, sleep, and timers.
source:
  - name: time
    path: vir/time/time.vri
status: draft
---

# Time

`time` provides monotonic timestamps for intervals, Unix wall-clock timestamps, duration helpers, sleep, and lightweight timers.

## Boundary

Use monotonic time for elapsed-time measurement and Unix time only for wall-clock timestamps.

`rand` and date/time formatting are outside this namespace.

## Migration map

| Current symbol | Proposed public | Signature (target) | Implementation source | Action |
|---|---|---|---|---|
| `time.now` | `time.now` | `time.now() -> int` | `vir/time/time.vri` | keep |
| `time.elapsed` | `time.elapsed` | `time.elapsed(start: int) -> Duration` | `vir/time/time.vri` | keep |
| `time.elapsedMs` | `time.elapsedMs` | `time.elapsedMs(start: int) -> int` | `vir/time/time.vri` | keep |
| `time.elapsedNanos` | `time.elapsedNs` | `time.elapsedNs(start: int) -> int` | `vir/time/time.vri` | rename |
| `time.since` | `time.since` | `time.since(start: int, stop: int) -> Duration` | `vir/time/time.vri` | keep |
| `time.unixSecs` | `time.unixSecs` | `time.unixSecs() -> int` | `vir/time/time.vri` | keep |
| `time.unixMillis` | `time.unixMs` | `time.unixMs() -> int` | `vir/time/time.vri` | rename |
| `unix_timestamp_nanos` | `time.unixNs` | `time.unixNs() -> int` | `vir/time/time.vri` | rename |
| `time.sleep` | `time.sleep` | `time.sleep(duration: Duration) -> Result` | `vir/time/time.vri` | keep |
| `time.sleepMs` | `time.sleepMs` | `time.sleepMs(ms: int) -> Result` | `vir/time/time.vri` | keep |
| `time.sleepSecs` | `time.sleepSecs` | `time.sleepSecs(secs: int) -> Result` | `vir/time/time.vri` | keep |
| `duration_zero` | `time.zero` | `time.zero() -> Duration` | `vir/time/time.vri` | rename |
| `duration_from_secs` | `time.fromSecs` | `time.fromSecs(secs: int) -> Duration` | `vir/time/time.vri` | rename |
| `duration_from_millis` | `time.fromMs` | `time.fromMs(ms: int) -> Duration` | `vir/time/time.vri` | rename |
| `duration_from_micros` | `time.fromUs` | `time.fromUs(us: int) -> Duration` | `vir/time/time.vri` | rename |
| `duration_from_nanos` | `time.fromNs` | `time.fromNs(ns: int) -> Duration` | `vir/time/time.vri` | rename |
| `duration_to_secs` | `time.toSecs` | `time.toSecs(duration: Duration) -> int` | `vir/time/time.vri` | rename |
| `duration_to_millis` | `time.toMs` | `time.toMs(duration: Duration) -> int` | `vir/time/time.vri` | rename |
| `duration_to_micros` | `time.toUs` | `time.toUs(duration: Duration) -> int` | `vir/time/time.vri` | rename |
| `duration_to_nanos` | `time.toNs` | `time.toNs(duration: Duration) -> int` | `vir/time/time.vri` | rename |
| `duration_add` | `time.add` | `time.add(a: Duration, b: Duration) -> Duration` | `vir/time/time.vri` | rename |
| `duration_sub` | `time.sub` | `time.sub(a: Duration, b: Duration) -> Duration` | `vir/time/time.vri` | rename |
| `duration_is_zero` | `time.isZero` | `time.isZero(duration: Duration) -> bool` | `vir/time/time.vri` | rename |
| `timer_start` | `time.timer` | `time.timer(label: string) -> Timer` | `vir/time/time.vri` | rename |
| `timer_elapsed` | `time.timerElapsed` | `time.timerElapsed(timer: Timer) -> Duration` | `vir/time/time.vri` | rename |
| `timer_elapsed_ns` | `time.timerNs` | `time.timerNs(timer: Timer) -> int` | `vir/time/time.vri` | rename |
| `timer_elapsed_ms` | `time.timerMs` | `time.timerMs(timer: Timer) -> int` | `vir/time/time.vri` | rename |
| `timer_stop` | `time.timerStop` | `time.timerStop(timer: Timer) -> Result` | `vir/time/time.vri` | rename |
| `now` | `—` | `—` | `vir/time/time.vri` | remove alias |
| `instant_now` | `—` | `—` | `vir/time/time.vri` | remove alias |
| `instant_elapsed_ns` | `—` | `—` | `vir/time/time.vri` | remove alias |
| `duration_*` free functions | `—` | `—` | `vir/time/time.vri` | remove alias |
| `time_now` | `—` | `—` | `vir/time/time.vri` | remove alias |
| `time_format` | `—` | `—` | `vir/time/time.vri` | remove alias |

## API

| ID | Symbol | Signature | Status |
|---|---|---|---|
| `time.now` | `time.now` | `time.now() -> int` | draft |
| `time.elapsed` | `time.elapsed` | `time.elapsed(start: int) -> Duration` | draft |
| `time.elapsed.ms` | `time.elapsedMs` | `time.elapsedMs(start: int) -> int` | draft |
| `time.elapsed.ns` | `time.elapsedNs` | `time.elapsedNs(start: int) -> int` | proposed |
| `time.since` | `time.since` | `time.since(start: int, stop: int) -> Duration` | draft |
| `time.unix.secs` | `time.unixSecs` | `time.unixSecs() -> int` | draft |
| `time.unix.ms` | `time.unixMs` | `time.unixMs() -> int` | proposed |
| `time.unix.ns` | `time.unixNs` | `time.unixNs() -> int` | proposed |
| `time.sleep` | `time.sleep` | `time.sleep(duration: Duration) -> Result` | draft |
| `time.sleep.ms` | `time.sleepMs` | `time.sleepMs(ms: int) -> Result` | draft |
| `time.sleep.secs` | `time.sleepSecs` | `time.sleepSecs(secs: int) -> Result` | draft |
| `time.zero` | `time.zero` | `time.zero() -> Duration` | proposed |
| `time.from.secs` | `time.fromSecs` | `time.fromSecs(secs: int) -> Duration` | proposed |
| `time.from.ms` | `time.fromMs` | `time.fromMs(ms: int) -> Duration` | proposed |
| `time.from.us` | `time.fromUs` | `time.fromUs(us: int) -> Duration` | proposed |
| `time.from.ns` | `time.fromNs` | `time.fromNs(ns: int) -> Duration` | proposed |
| `time.to.secs` | `time.toSecs` | `time.toSecs(duration: Duration) -> int` | proposed |
| `time.to.ms` | `time.toMs` | `time.toMs(duration: Duration) -> int` | proposed |
| `time.to.us` | `time.toUs` | `time.toUs(duration: Duration) -> int` | proposed |
| `time.to.ns` | `time.toNs` | `time.toNs(duration: Duration) -> int` | proposed |
| `time.add` | `time.add` | `time.add(a: Duration, b: Duration) -> Duration` | proposed |
| `time.sub` | `time.sub` | `time.sub(a: Duration, b: Duration) -> Duration` | proposed |
| `time.is.zero` | `time.isZero` | `time.isZero(duration: Duration) -> bool` | proposed |
| `time.timer` | `time.timer` | `time.timer(label: string) -> Timer` | proposed |
| `time.timer.elapsed` | `time.timerElapsed` | `time.timerElapsed(timer: Timer) -> Duration` | proposed |
| `time.timer.ms` | `time.timerMs` | `time.timerMs(timer: Timer) -> int` | proposed |
| `time.timer.ns` | `time.timerNs` | `time.timerNs(timer: Timer) -> int` | proposed |
| `time.timer.stop` | `time.timerStop` | `time.timerStop(timer: Timer) -> Result` | proposed |

---

<a id="time.now"></a>
## `time.now`

<!--
id: time.now
api: time.now
-->

```vir
time.now() -> int
```

Returns a monotonic timestamp in nanoseconds.

Use this value only for interval measurement. It is not a Unix timestamp.

### Parameters

None.

### Returns

`int` — monotonic nanoseconds from an implementation-defined origin.

The origin has no wall-clock meaning.

### Errors

None.

### Example

```vir
include time

let start = time.now()
```

---

<a id="time.elapsed"></a>
## `time.elapsed`

<!--
id: time.elapsed
api: time.elapsed
-->

```vir
time.elapsed(start: int) -> Duration
```

Returns the monotonic duration elapsed since `start`.

### Parameters

#### `start: int`

A monotonic timestamp previously returned by `time.now()`.

It must not be a Unix timestamp.

### Returns

`Duration` — elapsed monotonic duration.

### Errors

None.

### Example

```vir
include time

let start = time.now()
let d = time.elapsed(start)
```

---

<a id="time.elapsed.ms"></a>
## `time.elapsedMs`

<!--
id: time.elapsed.ms
api: time.elapsedMs
-->

```vir
time.elapsedMs(start: int) -> int
```

Returns elapsed monotonic time in milliseconds.

### Parameters

#### `start: int`

A monotonic timestamp returned by `time.now()`.

### Returns

`int` — elapsed whole milliseconds.

### Errors

None.

### Example

```vir
include time

let start = time.now()
let ms = time.elapsedMs(start)
```

---

<a id="time.elapsed.ns"></a>
## `time.elapsedNs`

<!--
id: time.elapsed.ns
api: time.elapsedNs
previous: time.elapsedNanos
-->

```vir
time.elapsedNs(start: int) -> int
```

Returns elapsed monotonic time in nanoseconds.

### Parameters

#### `start: int`

A monotonic timestamp returned by `time.now()`.

### Returns

`int` — elapsed nanoseconds.

### Errors

None.

### Example

```vir
include time

let start = time.now()
let ns = time.elapsedNs(start)
```

---

<a id="time.since"></a>
## `time.since`

<!--
id: time.since
api: time.since
-->

```vir
time.since(start: int, stop: int) -> Duration
```

Returns the monotonic duration between two timestamps.

### Parameters

#### `start: int`

Start monotonic timestamp.

#### `stop: int`

Stop monotonic timestamp.

Both values must come from the same monotonic clock domain.

### Returns

`Duration` — duration between `start` and `stop`.

### Errors

None.

### Example

```vir
include time

let a = time.now()
let b = time.now()
let d = time.since(a, b)
```

---

<a id="time.unix.secs"></a>
## `time.unixSecs`

<!--
id: time.unix.secs
api: time.unixSecs
-->

```vir
time.unixSecs() -> int
```

Returns the current Unix wall-clock timestamp in seconds.

### Parameters

None.

### Returns

`int` — seconds since the Unix epoch.

### Errors

None.

### Example

```vir
include time

let ts = time.unixSecs()
```

---

<a id="time.unix.ms"></a>
## `time.unixMs`

<!--
id: time.unix.ms
api: time.unixMs
previous: time.unixMillis
-->

```vir
time.unixMs() -> int
```

Returns the current Unix timestamp in milliseconds.

### Parameters

None.

### Returns

`int` — milliseconds since the Unix epoch.

### Errors

None.

### Example

```vir
include time

let ts = time.unixMs()
```

---

<a id="time.unix.ns"></a>
## `time.unixNs`

<!--
id: time.unix.ns
api: time.unixNs
previous: unix_timestamp_nanos
-->

```vir
time.unixNs() -> int
```

Returns the current Unix timestamp in nanoseconds.

### Parameters

None.

### Returns

`int` — nanoseconds since the Unix epoch.

### Errors

None.

### Example

```vir
include time

let ts = time.unixNs()
```

---

<a id="time.sleep"></a>
## `time.sleep`

<!--
id: time.sleep
api: time.sleep
-->

```vir
time.sleep(duration: Duration) -> Result
```

Sleeps for the requested duration.

### Parameters

#### `duration: Duration`

Requested sleep duration.

Zero duration is allowed. Negative duration is invalid.

### Returns

Bare `Result` — `Ok()` when the sleep completes, `Err(error)` when the platform call fails.

### Errors

Returns an error when the duration is invalid or the platform sleep operation fails.

### Example

```vir
include time

let delay = time.fromMs(500)
ensure time.sleep(delay)
```

---

<a id="time.sleep.ms"></a>
## `time.sleepMs`

<!--
id: time.sleep.ms
api: time.sleepMs
-->

```vir
time.sleepMs(ms: int) -> Result
```

Sleeps for a number of milliseconds.

### Parameters

#### `ms: int`

Milliseconds to sleep.

Must be zero or greater.

### Returns

Bare `Result`.

### Errors

Returns an error for a negative duration or platform sleep failure.

### Example

```vir
include time

ensure time.sleepMs(250)
```

---

<a id="time.sleep.secs"></a>
## `time.sleepSecs`

<!--
id: time.sleep.secs
api: time.sleepSecs
-->

```vir
time.sleepSecs(secs: int) -> Result
```

Sleeps for a number of seconds.

### Parameters

#### `secs: int`

Seconds to sleep.

Must be zero or greater.

### Returns

Bare `Result`.

### Errors

Returns an error for a negative duration or platform sleep failure.

### Example

```vir
include time

ensure time.sleepSecs(1)
```

---

<a id="time.zero"></a>
## `time.zero`

<!--
id: time.zero
api: time.zero
previous: duration_zero
-->

```vir
time.zero() -> Duration
```

Creates a zero duration.

### Parameters

None.

### Returns

`Duration` — zero seconds and zero nanoseconds.

### Errors

None.

### Example

```vir
include time

let d = time.zero()
```

---

<a id="time.from.secs"></a>
## `time.fromSecs`

<!--
id: time.from.secs
api: time.fromSecs
previous: duration_from_secs
-->

```vir
time.fromSecs(secs: int) -> Duration
```

Creates a duration from seconds.

### Parameters

#### `secs: int`

Whole seconds.

Must be zero or greater.

### Returns

`Duration`.

### Errors

None observable.

### Example

```vir
include time

let d = time.fromSecs(2)
```

---

<a id="time.from.ms"></a>
## `time.fromMs`

<!--
id: time.from.ms
api: time.fromMs
previous: duration_from_millis
-->

```vir
time.fromMs(ms: int) -> Duration
```

Creates a duration from milliseconds.

### Parameters

#### `ms: int`

Milliseconds.

Must be zero or greater.

### Returns

`Duration`.

### Errors

None observable.

### Example

```vir
include time

let d = time.fromMs(500)
```

---

<a id="time.from.us"></a>
## `time.fromUs`

<!--
id: time.from.us
api: time.fromUs
previous: duration_from_micros
-->

```vir
time.fromUs(us: int) -> Duration
```

Creates a duration from microseconds.

### Parameters

#### `us: int`

Microseconds.

Must be zero or greater.

### Returns

`Duration`.

### Errors

None observable.

### Example

```vir
include time

let d = time.fromUs(500)
```

---

<a id="time.from.ns"></a>
## `time.fromNs`

<!--
id: time.from.ns
api: time.fromNs
previous: duration_from_nanos
-->

```vir
time.fromNs(ns: int) -> Duration
```

Creates a duration from nanoseconds.

### Parameters

#### `ns: int`

Nanoseconds.

Must be zero or greater.

### Returns

`Duration`.

### Errors

None observable.

### Example

```vir
include time

let d = time.fromNs(1000)
```

---

<a id="time.to.secs"></a>
## `time.toSecs`

<!--
id: time.to.secs
api: time.toSecs
previous: duration_to_secs
-->

```vir
time.toSecs(duration: Duration) -> int
```

Converts a duration to whole seconds.

### Parameters

#### `duration: Duration`

Duration to convert.

### Returns

`int` — whole seconds.

### Errors

None.

### Example

```vir
include time

let secs = time.toSecs(d)
```

---

<a id="time.to.ms"></a>
## `time.toMs`

<!--
id: time.to.ms
api: time.toMs
previous: duration_to_millis
-->

```vir
time.toMs(duration: Duration) -> int
```

Converts a duration to whole milliseconds.

### Parameters

#### `duration: Duration`

Duration to convert.

### Returns

`int` — whole milliseconds.

### Errors

None.

### Example

```vir
include time

let ms = time.toMs(d)
```

---

<a id="time.to.us"></a>
## `time.toUs`

<!--
id: time.to.us
api: time.toUs
previous: duration_to_micros
-->

```vir
time.toUs(duration: Duration) -> int
```

Converts a duration to whole microseconds.

### Parameters

#### `duration: Duration`

Duration to convert.

### Returns

`int` — whole microseconds.

### Errors

None.

### Example

```vir
include time

let us = time.toUs(d)
```

---

<a id="time.to.ns"></a>
## `time.toNs`

<!--
id: time.to.ns
api: time.toNs
previous: duration_to_nanos
-->

```vir
time.toNs(duration: Duration) -> int
```

Converts a duration to nanoseconds.

### Parameters

#### `duration: Duration`

Duration to convert.

### Returns

`int` — nanoseconds.

### Errors

None.

### Example

```vir
include time

let ns = time.toNs(d)
```

---

<a id="time.add"></a>
## `time.add`

<!--
id: time.add
api: time.add
previous: duration_add
-->

```vir
time.add(a: Duration, b: Duration) -> Duration
```

Adds two durations.

### Parameters

#### `a: Duration`

First duration.

#### `b: Duration`

Second duration.

### Returns

`Duration` — the sum of `a` and `b`.

### Errors

None observable.

### Example

```vir
include time

let total = time.add(a, b)
```

---

<a id="time.sub"></a>
## `time.sub`

<!--
id: time.sub
api: time.sub
previous: duration_sub
-->

```vir
time.sub(a: Duration, b: Duration) -> Duration
```

Subtracts `b` from `a`.

### Parameters

#### `a: Duration`

Left duration.

#### `b: Duration`

Duration to subtract.

### Returns

`Duration` — resulting duration.

### Errors

Behavior for negative results must be verified at implementation time.

### Example

```vir
include time

let remaining = time.sub(total, used)
```

---

<a id="time.is.zero"></a>
## `time.isZero`

<!--
id: time.is.zero
api: time.isZero
previous: duration_is_zero
-->

```vir
time.isZero(duration: Duration) -> bool
```

Tests whether a duration is zero.

### Parameters

#### `duration: Duration`

Duration to test.

### Returns

`bool` — `true` when the duration is exactly zero.

### Errors

None.

### Example

```vir
include time

when time.isZero(d):
    # ...
end
```

---

<a id="time.timer"></a>
## `time.timer`

<!--
id: time.timer
api: time.timer
previous: timer_start
-->

```vir
time.timer(label: string) -> Timer
```

Starts a timer associated with a label.

### Parameters

#### `label: string`

Human-readable timer label.

An empty label is allowed.

### Returns

`Timer` — active timer state.

### Errors

None observable.

### Example

```vir
include time

let timer = time.timer("compile")
```

---

<a id="time.timer.elapsed"></a>
## `time.timerElapsed`

<!--
id: time.timer.elapsed
api: time.timerElapsed
previous: timer_elapsed
-->

```vir
time.timerElapsed(timer: Timer) -> Duration
```

Returns elapsed time for a timer.

### Parameters

#### `timer: Timer`

Timer created by `time.timer`.

### Returns

`Duration`.

### Errors

Behavior for an already stopped timer must be verified at implementation time.

### Example

```vir
include time

let d = time.timerElapsed(timer)
```

---

<a id="time.timer.ms"></a>
## `time.timerMs`

<!--
id: time.timer.ms
api: time.timerMs
previous: timer_elapsed_ms
-->

```vir
time.timerMs(timer: Timer) -> int
```

Returns timer elapsed time in milliseconds.

### Parameters

#### `timer: Timer`

Timer created by `time.timer`.

### Returns

`int` — whole elapsed milliseconds.

### Errors

Behavior for an invalid or stopped timer must be verified at implementation time.

### Example

```vir
include time

let ms = time.timerMs(timer)
```

---

<a id="time.timer.ns"></a>
## `time.timerNs`

<!--
id: time.timer.ns
api: time.timerNs
previous: timer_elapsed_ns
-->

```vir
time.timerNs(timer: Timer) -> int
```

Returns timer elapsed time in nanoseconds.

### Parameters

#### `timer: Timer`

Timer created by `time.timer`.

### Returns

`int` — elapsed nanoseconds.

### Errors

Behavior for an invalid or stopped timer must be verified at implementation time.

### Example

```vir
include time

let ns = time.timerNs(timer)
```

---

<a id="time.timer.stop"></a>
## `time.timerStop`

<!--
id: time.timer.stop
api: time.timerStop
previous: timer_stop
-->

```vir
time.timerStop(timer: Timer) -> Result
```

Stops a timer.

### Parameters

#### `timer: Timer`

Active timer created by `time.timer`.

### Returns

Bare `Result` — `Ok()` on success.

### Errors

Returns an error if the timer cannot be stopped or is already invalid.

Exact repeated-stop behavior must be verified at implementation time.

### Example

```vir
include time

ensure time.timerStop(timer)
```

## Open questions

- Verify whether `Duration` accepts negative values.
- Verify overflow behavior for duration conversions and arithmetic.
- Verify repeated `timerStop` behavior.
- Verify whether sleep interruption is observable.
- Remove legacy free functions only after migration map is closed and dependents are updated.
