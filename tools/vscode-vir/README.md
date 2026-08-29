# Virgori Core for VS Code

Virgori Core adds first-class editing support for the **Virgori (VIR)** language in VS Code.

## What you get

- Language support for Virgori source/module/config/binary descriptors:
  - `.vri` (canonical source)
  - `.sri` (module)
  - `.sci` (config)
  - `.vsib` (binary/interface bundle)
- Compatibility support kept for existing files: `.vri`, `.svi`
- Grammar + semantic highlighting that separates keywords, types, function declarations, function calls, unused functions, variables, object keys, and operators
- Dedicated coloring for `import` / `export` / `get`, `enum`, and `end`
- LSP client integration (configurable server path and arguments)
- Fallback editor features when no LSP is configured:
  - completion
  - hover
  - lightweight diagnostics for malformed tensor shape annotations
- Three bundled themes:
  - `Vir Quantum Dark`
  - `Vir Matrix Neon`
  - `Vir Forge Dark`

## Virgori language coverage

- Declarations: `entity`, `func`, `enum`
- Control flow: `if`, `elif`, `else`, `for`, `while`, `return`, `end`
- Import/module terms: `import`, `export`, `get`
- Parameters/locals: `in`, `out`, `var`
- Tensor types: `Matrix`, `Vector`
- Scalar types: `int`, `float`, `bool`, `string`
- AI ops: `matmul`, `grad`, `embed`, `train`
- System ops: `xor`, `shr`, `shl`
- Operators including `->`, `^`, `>>`, `$`

## Settings

- `vir.semantic.enableEnhanced` (default: `true`)
  Enables enhanced semantic token highlighting.
- `vir.lsp.serverPath`
  Absolute path to your Vir language server executable.
- `vir.lsp.serverArgs`
  Extra arguments passed to the language server.
- `vir.ide.enableFallbackIntellisense` (default: `true`)
  Enables built-in completion, hover, and diagnostics when LSP is unavailable.

Command:

- `Virgori: Restart Language Server`

## MIME registration (IANA submission draft)

See `IANA_MIME_REGISTRATION.md` in this extension folder for a ready-to-submit MIME template.

Proposed MIME types:

- `text/vnd.virgori.vri`
- `text/vnd.virgori.sri`
- `application/vnd.virgori.sci+json`
- `application/vnd.virgori.vsib`

Official project website: `https://dev.virgori.com`

## Local development

```bash
npm install
npm run compile
```

Run the commands from the extension project directory.

Press `F5` in VS Code to open an Extension Development Host.

## Build and publish

```bash
npm run package
npm run publish
```

## License

MIT (`LICENSE`)
