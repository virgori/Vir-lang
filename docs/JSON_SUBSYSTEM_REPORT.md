# JSON subsystem implementation report

Status: `PARTIALLY_RESOLVED` — the Vir stdlib work below is implemented and
verified. InterVir's targeted duplicate semantics and HTTP request-body adapter
are also migrated and tested. Full collection APIs, checked floating
conversion, deep collection features, conformance/fuzz coverage, and benchmarks
remain incomplete.

## JSON architecture

`stdlib/vir/data/json.vri` remains the only parser, `JsonValue` representation,
and serializer implementation changed in this work. `stdlib/vir/json.vri`
continues to forward to it. The former 581-line implementation in
`stdlib/vir/json/json.vri` has been replaced by compatibility names that forward
to `vir.data.json`; it no longer parses or serializes JSON independently.

The LSP JSON builders now use the canonical `JsonValue` constructors and
object/array operations. `stdlib/vir/auth/oauth2.vri` was migrated to handle
safe conversion results explicitly. Its module check remains blocked by an
unrelated existing selective-import error for `base64_url_encode` from
`encode`.

Vir stdlib's `protocol/http1_parser.vri` now enforces `MAX_BODY_BYTES` while
parsing `Content-Length`, returning 413 before arithmetic can overflow.
InterVir includes that implementation by the registered `http1.parser` name;
its focused unit test covers the exact limit, one byte over, and an
overflowing decimal length. `http/server.vri`, `http/app.vri`, and
`cmd/server.vri` preserve that status as an HTTP 413 response.
The InterVir checkout has extensive preexisting changes,
including in several files named by the request; those were preserved. The
slice module now retains only raw scanning/slice-view behavior; its independent
writer and primitive parser/conversion helpers were removed, and the relevant
tests now use `vir.data.json`. The logger builds a canonical JSON object and
serializes it through stdlib; `observability/json_writer.vri` remains only as
an escaping compatibility wrapper. `http.context` now exposes
`http_request_json` and `HttpContext.json_body`; the app buffers a declared
Content-Length body before routing, within the parser's 10 MiB limit.
Malformed/incomplete JSON returns an error, and the context helper sends 400
when invoked by a handler. Chunked request bodies are not decoded yet.

## Fixed bugs and clarified behavior

- Parsing no longer accumulates every number token into a native integer, so
  fractions, exponents, and large integers do not overflow that accumulator.
- Parsed number tokens remain in `JsonValue.str_val`; stringify emits that
  token unchanged. `asNumber` returns the exact token as `Option<string>`.
- `asInt` / `as_int` now return `Option<int>`. They accept only integer-form
  tokens within signed 64-bit range. Fraction and exponent forms return
  `None`; they are never truncated. The compatibility getters `getInt`,
  `getStr`, and `getBool` retain their default-value behavior.
- `asString` and `asBool` now return `Option` and reject incompatible JSON
  kinds. OAuth2 call sites were adjusted to handle these results.
- Compact stringify no longer inserts spaces after commas or colons. Pretty
  stringify retains its existing two-space indentation.
- The stdlib parser rejects input over `JSON_MAX_DOCUMENT_BYTES` (10 MiB),
  independently of any HTTP limit.
- Duplicate object keys are last-wins; replacing a value preserves the first
  key's insertion-order slot.
- `stdlib/vir/lsp/lsp.vri` now builds objects and arrays with canonical JSON
  APIs rather than map-to-JSON conversion helpers.

## New and changed APIs

- `json.asInt(value)` / `asInt(value)` → `Option<int>` for exact in-range
  integer-form values.
- `json.asString(value)` / `asString(value)` → `Option<string>` for strings.
- `json.asBool(value)` / `asBool(value)` → `Option<bool>` for booleans.
- `json.asNumber(value)` / `asNumber(value)` → `Option<string>` containing the
  exact JSON number token (or the integer spelling for a constructed number).
- `JSON_MAX_DOCUMENT_BYTES` exposes the stdlib input limit.
- The `json.json` compatibility module retains `json_int`,
  `json_to_string`, `json_to_string_pretty`, array push/get/length, and object
  set/get/has wrappers over the canonical implementation.
- Canonical array helpers now include `pop`, checked `insert`, checked
  `removeAt`, primitive `contains`, and `clear`; object helpers include
  `remove`, `keys`, `values`, `entries`, and `clear`. `clear` is also exposed
  for arrays. Failed indexes and missing keys are represented by `false` or
  `Option.None`, not an unchecked access.
- `deepEqual` recursively compares parsed arrays/objects and exact number
  tokens; `deepClone` round-trips through the canonical serializer/parser to
  produce independent nested storage; `merge` performs a shallow object merge
  with source keys replacing target keys.

The changed `asInt`, `asString`, and `asBool` return types are intentionally
source-incompatible with callers that assumed unchecked conversions. Safe
callers must match `Some` / `None`; existing defaulting getters remain
available.

## Removed duplication

The registered `json.json` file no longer contains a second parser, number
model, `JsonValue`, or serializer. The root `json` module still forwards to
`vir.data.json`. The raw offset scanner/view is now stdlib-owned as
`json.slice` (`stdlib/vir/data/json_slice.vri`); its writer and primitive
parser/conversion routines are removed. Logger output also uses
the canonical serializer. No independent JSON semantic implementation remains
in the targeted modules.

The shared `http.types`, `http.status`, `http1.parser`, `memory.slice`, and
`json.slice` module IDs are now registered only in `stdlib/stdlib.vri`.
InterVir keeps the same `include` names but no longer contains their
implementations or local registry entries. The `log.writer` compatibility
module was removed; logger code uses the canonical `json.stringify` and
`string.*` APIs directly.

## Tests and verification

- Baseline: `./bin/virc stdlib/vir/test/json_matrix_vtest.vri -o /private/tmp/vir_json_matrix_baseline`
  compiled and the binary exited 0.
- Baseline InterVir: both `tests/unit/test_protocol_json.vri` and
  `tests/unit/test_json_slice_edge_cases.vri` failed compilation with 26
  `E5001 Use of moved value` diagnostics in `protocol/json_slice.vri` around
  `JsonWriter`.
- After changes: `./bin/virc stdlib/vir/test/json_matrix_vtest.vri -o /private/tmp/vir_json_matrix_final_probe -q`
  compiled and the binary exited 0. The fixture covers fractions, exponents,
  large integer preservation, signed 64-bit minimum, safe conversion failure,
  compact output, duplicate keys, and missing-versus-null lookup.
- After collection changes: the same JSON matrix test compiles and exits 0;
  it additionally checks array insert/remove/pop/contains/clear, invalid-index
  rejection, object key/value/entry views, removal, and clear, plus deep clone,
  deep equality, and shallow merge.
- After changes: `./bin/virc stdlib/vir/lsp/lsp.vri --check -q` succeeded with
  zero diagnostics.
- After changes: `/Users/gengyang/Vir-3.0/bin/virc
  /Users/gengyang/Desktop/Repo/intervir/tests/unit/test_protocol_http1_parser.vri
  -o /private/tmp/intervir_http_body_limit_test -q` compiled from the Vir
  repository root, and the binary exited 0. It covers `Content-Length` at
  10 MiB, one byte above the limit, and a decimal value too large for native
  integer arithmetic.
- After changes: `http/server.vri --check`, `http/app.vri --check`, and
  `cmd/server.vri --check` succeeded with zero diagnostics. The raw CLI 413
  response's `Content-Length` was checked against its 29-byte body.
- After changes: InterVir `tests/unit/test_protocol_json.vri`,
  `tests/unit/test_json_slice_edge_cases.vri`, and new
  `tests/unit/test_http_json_body.vri` compiled and their binaries exited 0.
  The adapter test covers valid JSON, malformed JSON, and an incomplete body.
  `http/app.vri --check` and `cmd/server.vri --check` also pass.
- After changes: `rg` found no `JsonWriter`, `json_writer`, `json_parse_int`,
  `json_parse_bool`, or `json_unescape_string` in the targeted slice module and
  its tests. `git diff --check` passed for changed JSON-related files in both
  repositories.
- `git diff --check` for the JSON, LSP, OAuth2, and fixture files passed.
- RFC corpus, fuzzing, full collection-operation tests, and performance
  benchmarks were not run or added. There are no before/after benchmark data.

## Remaining limitations

- The stdlib has no verified checked floating-point parse API: `core.types`
  currently exposes a placeholder `parse_float` returning `int`, while the
  runtime helper delegates to an unchecked native conversion. `asFloat` was
  therefore not added; exact input remains available through `asNumber`.
- Fractional and exponent tokens are preserved and stringify exactly, but
  `asInt` does not attempt mathematical normalization such as `1e3` → `1000`.
- Object and array iteration callbacks and a deep (recursive) merge are not
  implemented here. `contains` currently compares primitive values and uses
  identity for nested collection storage. Cycle detection and configurable
  encode errors are also unresolved.
- InterVir does not decode chunked request bodies. The HTTP app reads complete
  bodies only when Content-Length is present; chunked requests are marked
  incomplete and `json_body()` rejects them. Chunked decoding and size
  enforcement remain to be implemented.
- The body-buffer path is verified by compilation and adapter unit tests, but
  there is no end-to-end socket test for fragmented request delivery.
- No compatibility corpus, fuzz target, or before/after benchmark currently
  supports the corresponding requested completion criteria.
- The current `virc` CLI locates `stdlib/stdlib.vri` relative to the source or
  working directory. For this external InterVir checkout, compile with
  `/Users/gengyang/Vir-3.0/bin/virc` from `/Users/gengyang/Vir-3.0`; invoking
  it from the InterVir directory does not find the stdlib registry.
- The required baseline commit was not created: both checkouts already contain
  extensive unrelated edits, including edits to InterVir files directly named
  in the task. The existing Git HEADs were preserved as rollback points rather
  than committing pending user changes.

## Files changed in this work

- `stdlib/vir/data/json.vri`
- `stdlib/vir/json/json.vri`
- `stdlib/vir/auth/oauth2.vri`
- `stdlib/vir/lsp/lsp.vri`
- `stdlib/vir/test/json_matrix_vtest.vri`
- `docs/JSON_SUBSYSTEM_REPORT.md`
- `stdlib/vir/protocol/http1_parser.vri`
- `/Users/gengyang/Desktop/Repo/intervir/tests/unit/test_protocol_http1_parser.vri`
- `/Users/gengyang/Desktop/Repo/intervir/http/server.vri`
- `/Users/gengyang/Desktop/Repo/intervir/http/app.vri`
- `/Users/gengyang/Desktop/Repo/intervir/cmd/server.vri`
- `stdlib/vir/data/json_slice.vri` (moved from InterVir)
- `/Users/gengyang/Desktop/Repo/intervir/http/context.vri`
- `stdlib/vir/log/json_writer.vri` (moved from InterVir)
- `/Users/gengyang/Desktop/Repo/intervir/observability/logger.vri`
- `/Users/gengyang/Desktop/Repo/intervir/tests/unit/test_http_json_body.vri`
- `/Users/gengyang/Desktop/Repo/intervir/tests/unit/test_protocol_json.vri`
- `/Users/gengyang/Desktop/Repo/intervir/tests/unit/test_json_slice_edge_cases.vri`
- `/Users/gengyang/Desktop/Repo/intervir/tests/unit/test_observability_json_writer.vri`
- `/Users/gengyang/Desktop/Repo/intervir/module.list`
