# Report — path + encode wave

**Updated:** 2026-09-30 — runtime hardening pass

## path (`vir/path/path.vri`)

| Registry | Delivered |
|---|---|
| `path.new` … `path.string` | `PathNamespace` / `var path` |
| `path.extension` | (not `ext`) |
| `path.isAbsolute` / `isRelative` | lexical `/` prefix |
| `path_exists` / `path_is_*` | **removed** from path |

Lexical ops use C-string scan (`as ptr` + `native_read_u8`), not fat `string` fields.

Migration wrappers (`path_new`, `path_join`, `path_to_string`, `path_name`) remain
available while the current native compiler still mis-lowers some `path.*`
namespace calls. `build/build.vri` uses these wrappers.

Runtime smoke covers join and basename. String separators are passed as literals:
the current native compiler does not reliably materialize module-level string
constants when they are passed as values.

## fs (`vir/fs/fs.vri`)

| Registry | Delivered |
|---|---|
| `fs.isFile` / `fs.isDir` | `Path` arg + `sys_open` / `sys_fstat` mode checks |

`fs.exists` unchanged (string path today; Path overload later per F3).

## Unicode encode (`str/encode.vri`, module `str.encode`)

| Registry | Delivered |
|---|---|
| `encode.utf8ToUtf16` … `asciiLossy` | `EncodeNamespace` on **`include str.encode`** |
| Wire | UTF-16/32 **LE** in `Buffer`; bridges return `Result of (Buffer)` |

Removed public `Utf8Result` / `Utf16Result` bags from return paths.
`Buffer` constructors and direct Buffer-returning bridge helpers now carry
explicit return types, which is required by the native aggregate-return ABI.

`encode.utf8ToUtf16` is runtime-tested. `asciiLossy` is tested through its
snake-case migration helper because the current compiler corrupts a three-word
`Buffer` returned directly from a namespace method.

## Wire codec (`encode/encode.vri`, module `encode`)

| API | Delivered |
|---|---|
| `encode.base64Encode` / `hexEncode` / `urlEncode` … | `EncodeNamespace` camelCase |
| Snake `base64_encode` … | still exported for migration |

**Name note:** two modules both export `var encode` — never `include` both in one unit; use `str.encode` vs `encode` per [`encode.md`](../encode.md) / [`data.md`](data.md).

Codec lookup tables use explicit soft-string byte reads. Native string indexing
still assumes the old fat-string layout and produced incorrect hex/base64 bytes.

## Verification

```bash
bin/virc stdlib/vir/test/path_encode_vtest.vri -o /tmp/path_encode_test
/tmp/path_encode_test

bin/virc stdlib/vir/test/unicode_encode_vtest.vri -o /tmp/unicode_encode_test
/tmp/unicode_encode_test

bin/virc stdlib/vir/test/parse_fmt_vtest.vri -o /tmp/parse_fmt_test
/tmp/parse_fmt_test
```

All three tests compile and return `0`.

The earlier transitive string `E3008` and namespace-variable `E5013` blockers
are cleared for these units. Remaining namespace aggregate-return limitations
are documented above and covered by migration wrappers.
