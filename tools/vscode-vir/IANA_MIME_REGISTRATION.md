# IANA MIME Registration Template for Virgori

This document contains a registration-ready draft for the Virgori language media types.

## Contact

- Name: Virgori Language Team
- Project: Virgori (VIR)
- Website: https://dev.virgori.com
- Email: standards@virgori.com

## 1) Source Code File (`.vri`)

- Type name: `text`
- Subtype name: `vnd.virgori.vri`
- Required parameters: none
- Optional parameters: `charset` (default `UTF-8`)
- Encoding considerations: 8bit / UTF-8 text
- Security considerations: Source code may contain untrusted content and should not be executed without sandboxing.
- Interoperability considerations: Plain text source format.
- Published specification: https://dev.virgori.com/spec
- Applications that use this media type: Virgori compiler, LSP, IDE tooling
- Fragment identifier considerations: none
- Additional information:
  - Magic number(s): none
  - File extension(s): `.vri`
  - Macintosh file type code(s): none
- Person & email address to contact for further information: standards@virgori.com
- Intended usage: COMMON
- Restrictions on usage: none
- Author/Change controller: Virgori Language Team

## 2) Module File (`.sri`)

- Type name: `text`
- Subtype name: `vnd.virgori.sri`
- Required parameters: none
- Optional parameters: `charset` (default `UTF-8`)
- Encoding considerations: 8bit / UTF-8 text
- Security considerations: Module text may import and reference external code.
- Interoperability considerations: Plain text module syntax.
- Published specification: https://dev.virgori.com/spec
- Applications that use this media type: Virgori module resolver, build tools
- Fragment identifier considerations: none
- Additional information:
  - Magic number(s): none
  - File extension(s): `.sri`
  - Macintosh file type code(s): none
- Person & email address to contact for further information: standards@virgori.com
- Intended usage: COMMON
- Restrictions on usage: none
- Author/Change controller: Virgori Language Team

## 3) Configuration File (`.sci`)

- Type name: `application`
- Subtype name: `vnd.virgori.sci+json`
- Required parameters: none
- Optional parameters: `charset` (default `UTF-8`)
- Encoding considerations: binary-safe JSON text
- Security considerations: Configuration values may affect compiler/runtime behavior.
- Interoperability considerations: JSON-compatible configuration schema.
- Published specification: https://dev.virgori.com/spec
- Applications that use this media type: Virgori package/build/config tooling
- Fragment identifier considerations: same as `application/json`
- Additional information:
  - Magic number(s): none
  - File extension(s): `.sci`
  - Macintosh file type code(s): none
- Person & email address to contact for further information: standards@virgori.com
- Intended usage: COMMON
- Restrictions on usage: none
- Author/Change controller: Virgori Language Team

## 4) Binary/Interface Bundle (`.vsib`)

- Type name: `application`
- Subtype name: `vnd.virgori.vsib`
- Required parameters: none
- Optional parameters: `version`
- Encoding considerations: binary
- Security considerations: Binary payload must be validated before loading.
- Interoperability considerations: versioned binary container.
- Published specification: https://dev.virgori.com/spec
- Applications that use this media type: Virgori runtime, linker, package manager
- Fragment identifier considerations: none
- Additional information:
  - Magic number(s): `56 53 49 42` (`VSIB`) recommended
  - File extension(s): `.vsib`
  - Macintosh file type code(s): none
- Person & email address to contact for further information: standards@virgori.com
- Intended usage: COMMON
- Restrictions on usage: none
- Author/Change controller: Virgori Language Team

## Notes for VS Code Ecosystem

Use this mapping in docs/tooling where MIME hints are required:

- `.vri` -> `text/vnd.virgori.vri`
- `.sri` -> `text/vnd.virgori.sri`
- `.sci` -> `application/vnd.virgori.sci+json`
- `.vsib` -> `application/vnd.virgori.vsib`
- Legacy `.vri`/`.svi` files may be treated as `text/vnd.virgori.vri` for backward compatibility.
