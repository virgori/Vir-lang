# Vir Modules (AI Spec)

**Spec:** Vir v2.0  
Path map: `A.B.C` → `A/B/C.vri` from project roots / stdlib.

## Declaration order (module level)

```text
include → import/get → const → var → entity → func → export → share
```

## include — physical load

Embeds a module into the compile graph (namespace access).

```vir
include math
include net.http as web
include math, io.file as file, net.http as web
```

## import — bring exported symbols

Does **not** require a prior `include`. Prefer Vir v2.0 form:

```vir
import add from math
import add, sub from math
import from net.http
import get from net.http as fetch
```

Legacy `from math import add` may exist for compatibility — **not** the preferred form.

## get — constants / vars into local scope

```vir
get MAX_RETRY from net.config
get PI from math as TAU
```

## export / share / port

```vir
export add, subtract
share counter, mode
port signals, commands
```

| | `share` / `ref` | `port` |
|---|---|---|
| Use | In-process shared data | Message coordination |
| Access | Memory | Send/recv queue |

## lazy

For mutual **type** dependencies only:

```vir
lazy include satellite
lazy import SomeType from A
```

Calling functions from a lazy-only module is a compile error — upgrade to full `include`.

## Agent rules

1. Prefer `import X from mod` over inventing `use` / `require` / `package`.
2. Do not invent module paths; check `stdlib/vir/` or the project tree.
3. Compiler include pipeline for production lives under `stdlib/vir/compiler/` (`main.vri`, `virc.vri`) — do not invent include semantics.
