# Vir binaries (`darwin-arm64`)

| Binary | Role |
|--------|------|
| `virc` | Native self-hosted compiler (Mach-O, v2.2.0) |
| `virc.soft-wrapper.bak` | Previous soft/C-VM shell driver (kept for reference) |
| `vir-core` | C-VM engine |
| `vir` / `viron` / `vir-lsp` / `vir-todo` | Companion tools |

After clone on Apple Silicon:

```bash
codesign -f -s - -i virc-bootstrap ./bin/virc
./bin/virc your.vri -o out
```
