# Changelog

All notable changes to the Vir Language Support extension will be documented in this file.

## [3.1.2] - 2026-03-10

### Changed

- Added SVG version of `A978be7097ebe4d28be13c1296a30ffd9E.png` at `assets/A978be7097ebe4d28be13c1296a30ffd9E.svg`.
- Updated language file icon mapping to use the new SVG asset.
- Bumped extension version to `3.1.2`.

## [3.1.1] - 2026-03-10

### Changed

- Removed redundant explicit `activationEvents` entries and relied on contribution-based activation.
- Bumped extension version to `3.1.1`.

## [3.1.0] - 2026-03-10

### Changed

- Rebranded editor-facing naming to **Virgori (VIR)** and updated homepage to `https://dev.virgori.com`.
- Added canonical file extensions: `.vri`, `.sri`, `.sci`, `.vsib`.
- Kept compatibility extensions: `.vri`, `.svi`.
- Upgraded semantic highlighting to distinguish function declarations, function calls, and currently unused functions.
- Added dedicated semantic colors for variables and object-like data keys.
- Updated file icon to richer SVG style for Virgori files.
- Added `IANA_MIME_REGISTRATION.md` with MIME registration template and mappings.
- Bumped extension version to `3.1.0`.

## [3.0.4] - 2026-03-09

### Changed

- Removed path-based command examples from Marketplace README details.
- Bumped extension version to `3.0.4`.

## [3.0.3] - 2026-03-09

### Changed

- Bumped extension version to `3.0.3`.

## [3.0.2] - 2026-03-09

### Changed

- Rewrote Marketplace README content for cleaner and more natural product copy.
- Bumped extension version to `3.0.2`.

## [3.0.1] - 2026-03-09

### Changed

- Updated `.vri` file icon to use transparent-background SVG (`assets/vir-file-icon.svg`).
- Bumped extension version to `3.0.1`.

## [3.0.0] - 2026-03-09

### Changed

- Major version bump to `3.0.0`.

## [0.2.1] - 2026-03-09

### Changed

- Bumped extension version to `0.2.1` to force Marketplace/client update visibility.
- Updated `.vri` file icon to `assets/A978be7097ebe4d28be13c1296a30ffd9E.png`.
- Updated extension marketplace logo to `assets/Ae4356cf756194929a3164d887ce43092n.png`.
- Added keyword coloring for `import`, `export`, and `get` with dedicated red scope `keyword.control.import.vri`.
- Added dedicated `end` scope `keyword.control.terminator.vri` with darker, bold styling than `in`/`out`.
- Marked `enum` as declaration keyword (`keyword.declaration.vri`).
- Unified `->` as standard operator color via `keyword.operator.vri`.

## [0.2.0] - 2026-03-09

### Added

- New theme: `Vir Matrix Neon`
- New theme: `Vir Forge Dark`
- Semantic token provider for Vir keywords, AI/system ops, tensor/scalar types, shape, operators, and declarations
- LSP client framework with configurable `vir.lsp.serverPath` and `vir.lsp.serverArgs`
- Command: `Vir: Restart Language Server`
- Fallback IDE providers (completion, hover, diagnostics) when LSP is not configured
- Marketplace and packaging configuration (`scripts`, `files`, metadata)
- New extension icon in `assets/vir-icon.svg`
- `LICENSE` (MIT)

### Changed

- Extended README with development, packaging, and publish steps

## [0.1.0] - 2026-03-09

### Added

- Vir v1.2 language registration (`.vri`)
- TextMate grammar and snippets
- Theme: `Vir Quantum Dark`
