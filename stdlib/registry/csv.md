---
module: csv
title: Csv
summary: RFC 4180 CSV parse and stringify — namespace csv.*; CsvDocument / CsvRow.
source:
  - name: csv
    path: vir/csv.vri
  - name: data.csv
    path: vir/data/csv.vri
    notes: implementation; public contract is csv.*
status: stable
---

# Csv

Structured CSV documents under namespace **`csv`**. Physical entry is `include csv`
(`vir/csv.vri` re-exports `vir/data/csv.vri`).

```vir
let r = csv.parse(text)                    # Result of (CsvDocument)
let s = csv.stringify(doc)
let d = csv.parseDelim(text, 59)           # custom delimiter (e.g. ';')
```

## Boundary

| In `csv` | Not in `csv` |
|---|---|
| Parse / stringify (comma or delimiter) | Streaming row iterators |
| `CsvDocument` / `CsvRow` types | SQL / spreadsheet formats |
| Strict RFC 4180 errors | Silent repair of malformed input |

## Migration map

| Current | Public | Action |
|---|---|---|
| `csv.read` | `csv.parse` | **remove alias** |
| `csv.write` | `csv.stringify` | **remove alias** |
| `csv.readDelim` / `read_delim` / `parse_delim` | `csv.parseDelim` | **remove alias** |
| `csv.writeDelim` / `write_delim` | `csv.stringifyDelim` | **remove alias** |
| `csv.size` / `get` / `push` (doc) | `csv.count` / `csv.at` / `csv.add` | **remove alias** |
| `csv.row_count` / `row_at` / `row_add` / `rowPush` | `csv.rowCount` / `csv.rowAt` / `csv.rowAdd` | **remove alias** |
| `doc.count()` / `row.at()` (entity UFCS) | `csv.count(doc)` / `csv.rowAt(row, i)` | **migrate callers** |

## API

| ID | Symbol | Signature | Status |
|---|---|---|---|
| `csv.CsvRow` | `csv.CsvRow` | entity | draft |
| `csv.CsvDocument` | `csv.CsvDocument` | entity | draft |
| `csv.parse` | `csv.parse` | `csv.parse(text: string) -> Result of (csv.CsvDocument)` | draft |
| `csv.stringify` | `csv.stringify` | `csv.stringify(doc: csv.CsvDocument) -> string` | draft |
| `csv.parseDelim` | `csv.parseDelim` | `csv.parseDelim(text: string, delim: int) -> Result of (csv.CsvDocument)` | draft |
| `csv.stringifyDelim` | `csv.stringifyDelim` | `csv.stringifyDelim(doc: csv.CsvDocument, delim: int) -> string` | draft |
| `csv.doc` | `csv.doc` | `csv.doc() -> csv.CsvDocument` | draft |
| `csv.row` | `csv.row` | `csv.row() -> csv.CsvRow` | draft |
| `csv.count` | `csv.count` | `csv.count(doc: csv.CsvDocument) -> int` | draft |
| `csv.at` | `csv.at` | `csv.at(doc: csv.CsvDocument, idx: int) -> csv.CsvRow` | draft |
| `csv.add` | `csv.add` | `csv.add(ref doc: csv.CsvDocument, row: csv.CsvRow)` | draft |
| `csv.rowCount` | `csv.rowCount` | `csv.rowCount(row: csv.CsvRow) -> int` | draft |
| `csv.rowAt` | `csv.rowAt` | `csv.rowAt(row: csv.CsvRow, idx: int) -> string` | draft |
| `csv.rowAdd` | `csv.rowAdd` | `csv.rowAdd(ref row: csv.CsvRow, field: string)` | draft |

---

## `csv.parse`

`csv.parse(text: string) -> Result of (CsvDocument)`

Comma delimiter (RFC 4180). Parse failure → `Err` with invalid-data semantics.

---

## `csv.stringify`

`csv.stringify(doc: CsvDocument) -> string`

Round-trip compatible with `csv.parse` for documents produced by this module.

---

## `csv.parseDelim`

`csv.parseDelim(text: string, delim: int) -> Result of (CsvDocument)`

Same parser as `csv.parse` with a single-byte field delimiter.

---

## `csv.stringifyDelim`

`csv.stringifyDelim(doc: CsvDocument, delim: int) -> string`

---

## `csv.doc` / `csv.row`

Empty document / row constructors.

---

## `csv.count` / `csv.at` / `csv.add`

Row-level operations on `CsvDocument`.

---

## `csv.rowCount` / `csv.rowAt` / `csv.rowAdd`

Field-level operations on `CsvRow`.
