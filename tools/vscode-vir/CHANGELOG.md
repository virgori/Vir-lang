# Changelog

All notable changes to the Vir Language Support extension will be documented in this file.

## [4.7.0]

### Changed
- `->` is Lime `#BEF264` in the dark themes (darker lime `#4D7C0F` in Quantum Light so it stays readable on white), in both the TextMate and semantic layers.
- Banner palette: text `#B5EDFF`, decoration (`##` / `#*#` frame and `====` rules) `#67E8F9`, title (first content line) `#D6F6FF` bold. Quantum Light uses darker cyans of the same hue.

### Fixed
- File banners were not recognised when the file starts with a blank line (e.g. `src/core/sys.vri`): TextMate tokenizes line by line, so `\A(?:[ \t]*\n)*` could never match. Leading blank lines / shebang are now a small wrapper state around the banner.

### Added
- **Active / inactive symbol highlighting.** Module names, functions, types, constants and imported symbols are coloured Active `#FFB454` / Inactive `#92745F` (light theme: `#B45309` / `#7A5C48`, since `#FFB454` is 1.8:1 on white). State is per symbol, including each name inside `import a, b from mod`. `include` / `import` / `from` keep their colours; the line is never dimmed; no warning or error is produced for inactive symbols; unresolved symbols are never painted inactive.
  - The compiler is the single source of truth: `virc --ide-semantic --json` emits `ide.symbols` (`name`, `kind`, `line`, `state`) from its declaration table and reference graph (calls, callbacks passed as values, type uses, constants; roots are `main`, top-level code and `export`s; transitive). The extension does no usage analysis of its own; it only locates the reported name on the reported line.
  - New semantic modifiers `active` / `inactive`, new token types `moduleName`, `importedSymbol`, `constant`, `bannerTitle`, new setting `vir.semantic.symbolState.enabled`.
  - Snapshots are cached by document version; a request for a newer version aborts the stale compiler process; a cancelled semantic-token request stops waiting.
- `npm test`: unit tests (banner title, symbol location/state mapping, theme colours) and compiler-backed fixtures for direct call, indirect call, callback, unused import, unresolved symbol and cross-module dependency (`test/fixtures`, skipped until the compiler emits `ide.symbols`).

### Removed
- The regex-based `functionUnused` semantic token (name matching in the document) and the opacity/italic decorations for module/function active/inactive state.

## [4.6.10]

### Fixed
- Root cause of the two-tone `->`: `language-configuration.json` declared `<` `>` as a bracket pair, so VS Code's bracket pair colorization painted the `>` of `->` (and every comparison `<` / `>`) with a nesting color while `-` kept its token color. `<` `>` are no longer brackets; only `{}` `[]` `()` are colorized.

## [4.6.9]

### Fixed
- Semantic tokens no longer emit strings, numbers, operators or `->`; these are owned solely by the TextMate grammar, so no second layer can split `->` into two colors.
- Function names were tagged at the wrong column when the name occurred inside `func` (e.g. `func f`).
- Parameter and constant names before `:` were mis-tagged as object keys; only inside `{ ... }` now.

## [4.6.8]

### Added
- Warn when `virgori.virgori-core` is installed alongside this extension. It registers the same `source.vri` grammar, its own semantic-token provider (which paints `->`, `-` and `>` as overlapping operators), and themes with identical names, so `->` renders in two colors regardless of this extension's grammar.

## [4.6.7]

### Fixed
- Tensor shape grammar never matched: the `:` type-annotation rule always won the leftmost-match race, so `tensor[i32; 12, 13]` fell back to generic brackets and plain integers. Shape rules now absorb the leading `:`, `var`/`let`/`const`, or `->`.
- Semantic tokens were pushed out of positional order, which made VS Code drop or mis-render overlapping ranges (the two-tone `->`). Tokens are now collected, sorted, and de-overlapped before emission.
- `-1` and other negative literals tokenize as a single number instead of a stray operator plus digit.

### Changed
- AI/ML shape scopes get an exclusive palette (tensor type, shape delimiters, element type, dimensions). UFCS moved off teal so the tensor family owns it; tensor types no longer share the scalar-type color.

## [4.6.6]

### Fixed
- `->`: dedicated `#returnArrow` grammar + semantic `returnArrow`; operators no longer tokenize lone `-` / `>` (fixes two-color arrow).
- Unary `-` on literals no longer styled as binary operator.

### Added
- `tensor[elem; dims]` / `Matrix<>` shape scopes (violet delimiters, amber element type, teal dimensions) — distinct from operators, keywords, and plain integers.

## [4.6.5]

### Added
- Semantic token `shapeDimension` for static shape literals (`tensor[…; …]`, `Matrix<…>`, `Vector<…>`), driven by `virc --ide-semantic` JSON `shapeDimensions` when available; fallback heuristics when not.
- Setting `vir.semantic.shape.compilerBacked` (default on). Maps to TextMate scope `constant.numeric.dimension.vri` — themes choose whether to color distinctly.

### Compiler
- `ide_semantic` / `sem_pass_ide` collect shape dimension values from resolved type annotations.

## [4.6.4]

### Changed
- Theme: file banner colors +30% brightness; `#*#` / `##` block comments +16% (all Vir themes).

## [4.6.3]

### Fixed
- `->` highlighted as one token (`keyword.operator.vri`); avoid splitting `-` / `>` via separate operator alternates and conflicting theme rules for `keyword.operator.arrow.vri`.

## [4.6.2]

### Added
- File header banner highlighting: first `#*#` / `##` block at BOF (after shebang/blank lines) uses scopes `comment.block.banner.vri` and `comment.block.banner.content.vri`
- Theme colors for banner in Quantum / Matrix / Forge dark themes and **Vir Quantum Light** fallback theme
- npm script `vsix` → packages `vir-lang-<version>.vsix` (use instead of `compile` alone)

### Note
- `npm run compile` only emits TypeScript to `out/`; run `npm run vsix` or `npm run package` to build the installable extension.

## [4.6.0]

### Added
- Compiler-backed IDE semantic: `virc --ide-semantic --json` (variable lifetime + module include activity)
- Extension decorations, focus lifetime on cursor, hover, command `Vir: Show Variable Lifetime`
- Settings: `vir.semantic.lifetime.*`, `vir.compiler.path`

## [4.5.8]

### Added
- TextMate: generic `of (...)`, UFCS `.method()`, `->` arrow scope, module namespace paths, `tensor`/`flux`/generic container types
- Distinct `#*#` / `##` block comment body and delimiter colors (Vir themes)
- Language `vir-modulereg` for `stdlib.vri` and `module.list` (comments, module keys, paths)

## [4.5.7] - 2026-09-04

### Fixed

- Semantic tokens, completion, and hover cover full bitwise / word operators:
  `and` `or` `xor` `not` `shl` `shr` `mod` and `bit_*` aliases.
- Hover notes that **`>>` is type cast**, not shift (`shr`).

## [4.5.6] - 2026-09-01

### Fixed

- File icon theme maps **only** `.vri` / `.sri` / `.sci` / `.svi` / `.vsib` (no longer overrides every file).
- Enable: Command Palette → `Preferences: File Icon Theme` → **Vir-lang File Icons**.

## [4.5.5] - 2026-09-01

### Fixed

- Extension / file logo: remove white corner background (RGBA transparent outside rounded square).

## [4.5.4] - 2026-09-01

### Fixed

- File explorer icons for `.vri` / `.sri` / `.sci` / `.svi` / `.vsib`:
  - language icons resized to 32×32 (large PNGs showed blank in sidebar)
  - added **Vir-lang File Icons** theme (`contributes.iconThemes`)
- After install: Command Palette → `Preferences: File Icon Theme` → **Vir-lang File Icons**

## [4.5.3] - 2026-09-01

### Changed

- Extension Marketplace id `name` → `vir-lang` (displayName **Vir-lang**) under publisher `VirgoriLabs`.
- Avoids conflict with existing Marketplace extension `virgori-core`.

## [4.5.2] - 2026-09-01

### Fixed

- Removed broken imports of missing modules (`smartBar`, `blockDiagnostics`, `blockCommentValidation`) that prevented extension activation.
- Slimmed VSIX assets to logo + file icon only.
- Publisher remains `VirgoriLabs`.

## [4.5.1] - 2026-09-01

### Changed

- Extension marketplace icon → Virgori compass logo (`assets/virgori-logo-128.png`).
- File icons for `.vri` / `.sri` / `.sci` / `.svi` / `.vsib` → same logo (`assets/virgori-file-icon.png`).

## [4.5.0] - 2026-09-01

### Changed

- Bumped extension version to `4.5.0`.
- Palette refresh from 3.1.4 (import/include/declaration/AI/async/operator/comment scopes).

## [3.1.4] - 2026-09-01

### Changed

- `import` / `export` / `get` / `from` → cam đậm (`#EA580C`).
- `include` → đỏ đậm (`#B91C1C`), scope riêng `keyword.control.include.vri`.
- Keyword khai báo (`func`/`entity`/`enum`/`var`/…) → xanh dương (`#3B82F6`).
- Toán tử AI (`matmul`/`grad`/`embed`/`train`) → đỏ cam (`#F97316`).
- Comment → xanh lá (`#22C55E`); nhận diện block `#*# … #*#` và `## … ##`.
- Keyword bất đồng bộ (`async`/`await`/`send`/`recv`/…) → tím (`#A855F7`).
- Keyword toán tử (`and`/`or`/`xor`/`shl`/`bit_*`/…) cùng màu toán tử ký hiệu.
- Bumped extension version to `3.1.4`.

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
