# Report — Data formats / encoding

**Registry:** none for most (except Unicode [`../encode.md`](../encode.md) clash)  
**Status:** compile smoke **strong**; SSOT **missing**

## Scope

| Module | Source | Compile | Notes |
|---|---|---|---|
| `base64` | `encoding/base64.vri` (+ `encode/encode.vri`) | **OK** | Dual paths |
| `hex` | `encoding/hex.vri` (+ encode) | **OK** | Dual paths |
| `csv` | `data/csv.vri` | **OK** | Q7 next wave |
| `toml` | `data/toml.vri` | **OK** | |
| `xml` | `data/xml.vri` | **OK** | |
| `yaml` | `data/yaml.vri` | **OK** | parse always Err (stub) |
| `ini` | `data/ini.vri` | **OK** | |
| `url` | `net/url.vri` | **OK** | |
| flat `encode` | `encode/encode.vri` | FAIL via string | Wire codecs; ≠ Unicode encode.md |

## Naming (target when registries land)

```text
base64.encode / hex.decode / csv.parse / toml.parse
xml.parse / ini.get / url.parse
```

Encoding is **not** crypto. YAML remains fail-closed / unimplemented content.

## Verdict

Best compile health outside core option/result/vec/fs/char/math/regex. Priority: write registry SSOT files + resolve base64/hex/encode duplication before API freeze.
