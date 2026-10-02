---
module: protocol
title: Protocol (internal)
summary: InterVir HTTP/1.1 wire types and parsers — not a public user namespace.
source:
  - name: protocol.http_status
    path: vir/protocol/http_status.vri
  - name: protocol.http_types
    path: vir/protocol/http_types.vri
  - name: protocol.http1_parser
    path: vir/protocol/http1_parser.vri
  - name: protocol.buffer_slice
    path: vir/protocol/buffer_slice.vri
status: draft
notes: >-
  Compiler/include names use protocol.* for layering. Symbols may retain
  snake_case (e.g. parser_new, parse_into). User docs and registry SSOT for
  HTTP client/server must use http.* / net.* only.
---

# Protocol (internal)

**Not** part of the camelCase public stdlib surface. Modules exist so `http`,
future server stacks, and tests can share InterVir-aligned wire logic.

| Include | Role |
|---|---|
| `protocol.http_status` | reason phrases, status line bytes |
| `protocol.http_types` | request/response wire entities |
| `protocol.http1_parser` | incremental HTTP/1.1 parser |
| `protocol.buffer_slice` | byte slice helper for parser |

Public facades must not re-export `phrase`, `statusLine`, `parser_new`, or
`parse_into` as documented user API.
