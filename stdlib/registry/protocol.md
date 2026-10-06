---
module: protocol
title: Protocol (internal)
summary: Shared HTTP/1.1 wire types, parser, and framing helpers owned by Vir stdlib.
source:
  - name: http.status
    path: vir/protocol/http_status.vri
  - name: http.types
    path: vir/protocol/http_types.vri
  - name: http1.parser
    path: vir/protocol/http1_parser.vri
  - name: http1.serializer
    path: vir/protocol/http1_serializer.vri
  - name: memory.slice
    path: vir/protocol/buffer_slice.vri
status: draft
notes: >-
  Module IDs retain the names used by InterVir callers while their only
  implementation and registration live in Vir stdlib. Symbols may retain
  snake_case (e.g. parser_new, parse_into).
---

# Protocol (internal)

These modules let `http`, server stacks, and tests share one wire implementation.

| Include | Role |
|---|---|
| `http.status` | `status.phrase`, `status.line`, and status category checks |
| `http.types` | request/response wire entities |
| `http1.parser` | incremental HTTP/1.1 parser |
| `http1.serializer` | `serializer.chunkEnd` and `serializer.estimateSize` |
| `memory.slice` | byte slice helper for parser |

The `http.status` module exposes its own dot-style `status.*` API. Its legacy
free functions remain available to existing include callers, but public
facades must not re-export `phrase`, `statusLine`, `parser_new`, or `parse_into`
as documented user API.
