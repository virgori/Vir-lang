/** Versioned compiler facts only. This module does no name or source analysis. */
export const SEMANTIC_SCHEMA_VERSION = 1;
export const MAX_SNAPSHOT_RECORDS = 200_000;
export const VIR_MODIFIERS = ["virAlive", "virMoved", "virOut", "virInvalid", "virInactive", "virUnresolved", "virLastUse", "virBorrowed", "virMaybeMoved"];

export interface Position { line: number; character: number }
export interface Range { start: Position; end: Position }
export interface Occurrence {
  symbolId: string;
  uri?: string;
  range: Range;
  kind: string;
  states: string[];
  role?: string;
  flags?: string[];
  [field: string]: unknown;
}
export interface SemanticSnapshot {
  schemaVersion: number;
  uri: string;
  documentVersion: number;
  analysisId: string;
  complete: boolean;
  unavailableReason?: unknown;
  occurrences: Occurrence[];
  functions: Array<{ symbolId: string; uri?: string; declarationRange: Range; activity: string }>;
  modules: Array<{ uri?: string; includeRange: Range; activity: string; canonicalName?: string }>;
  focus?: { symbolId: string; path: Occurrence[] };
  documents?: Array<{ uri: string; version?: number | null; documentVersion?: number | null; fingerprint?: string }>;
  [field: string]: unknown;
}
export interface VirCapabilities {
  schemaVersion: number;
  semanticSnapshot: boolean;
  diagnosticSnapshot: boolean;
  focusLifetime: boolean;
  semanticTokenModifiers: string[];
}
export interface DocumentView {
  uri: string;
  version: number;
  lines: readonly string[];
}
const record = (v: unknown): v is Record<string, unknown> => !!v && typeof v === "object" && !Array.isArray(v);
const integer = (v: unknown): v is number => Number.isSafeInteger(v) && (v as number) >= 0;
const opaqueId = (v: unknown): v is string => typeof v === "string" && v.length > 0 && v.length <= 1024;
const strings = (v: unknown): v is string[] => Array.isArray(v) && v.length < 128 && v.every(s => typeof s === "string" && s.length <= 256);

export function canonicalFileUri(value: unknown): string | undefined {
  if (typeof value !== "string" || value.length > 32_768) return undefined;
  try {
    const uri = new URL(value);
    if (uri.protocol !== "file:" || uri.search || uri.hash || uri.username || uri.password) return undefined;
    const decoded = decodeURIComponent(uri.pathname);
    if (/[\x00-\x1f]/.test(decoded) || decoded.split("/").includes("..")) return undefined;
    return uri.href;
  } catch { return undefined; }
}

export function negotiateVirCapabilities(capabilities: unknown): VirCapabilities | undefined {
  if (!record(capabilities) || !record(capabilities.experimental) || !record(capabilities.experimental.vir)) return undefined;
  const vir = capabilities.experimental.vir;
  if (vir.schemaVersion !== SEMANTIC_SCHEMA_VERSION || vir.semanticSnapshot !== true ||
      typeof vir.diagnosticSnapshot !== "boolean" || typeof vir.focusLifetime !== "boolean" ||
      !strings(vir.semanticTokenModifiers) || !VIR_MODIFIERS.every(m => (vir.semanticTokenModifiers as string[]).includes(m))) return undefined;
  if (capabilities.positionEncoding !== undefined && capabilities.positionEncoding !== "utf-16") return undefined;
  return vir as unknown as VirCapabilities;
}

function compare(a: Position, b: Position): number { return a.line - b.line || a.character - b.character; }
function boundary(line: string, column: number): boolean {
  if (column > line.length) return false;
  const previous = line.charCodeAt(column - 1), next = line.charCodeAt(column);
  return !(previous >= 0xd800 && previous <= 0xdbff && next >= 0xdc00 && next <= 0xdfff);
}
export function validRange(value: unknown, lines?: readonly string[]): value is Range {
  if (!record(value) || !record(value.start) || !record(value.end)) return false;
  const a = value.start, b = value.end;
  if (!integer(a.line) || !integer(a.character) || !integer(b.line) || !integer(b.character)) return false;
  if (compare(a as unknown as Position, b as unknown as Position) >= 0) return false;
  return !lines || (a.line < lines.length && b.line < lines.length && boundary(lines[a.line], a.character) && boundary(lines[b.line], b.character));
}
export function contains(range: Range, position: Position): boolean {
  return compare(range.start, position) <= 0 && compare(position, range.end) < 0;
}

export function validateSnapshot(value: unknown, document: DocumentView, openDocuments: readonly DocumentView[] = []): SemanticSnapshot | undefined {
  if (!record(value) || value.schemaVersion !== SEMANTIC_SCHEMA_VERSION ||
      canonicalFileUri(value.uri) !== canonicalFileUri(document.uri) || !canonicalFileUri(document.uri) ||
      value.documentVersion !== document.version || !opaqueId(value.analysisId) || typeof value.complete !== "boolean") return undefined;
  if (!value.complete && value.unavailableReason === undefined) return undefined;
  const lists = [value.occurrences, value.functions, value.modules];
  if (lists.some(a => !Array.isArray(a)) || lists.reduce<number>((n, a) => n + (a as unknown[]).length, 0) > MAX_SNAPSHOT_RECORDS) return undefined;
  const docs = new Map(openDocuments.map(d => [canonicalFileUri(d.uri), d]));
  docs.set(canonicalFileUri(document.uri), document);
  const checkRange = (range: unknown, uri: unknown): boolean => {
    const canonical = canonicalFileUri(uri ?? value.uri);
    return !!canonical && validRange(range, docs.get(canonical)?.lines);
  };
  const occurrence = (o: unknown): boolean => record(o) && opaqueId(o.symbolId) &&
    typeof o.kind === "string" && strings(o.states) && (o.flags === undefined || strings(o.flags)) && checkRange(o.range, o.uri);
  if (!(value.occurrences as unknown[]).every(occurrence)) return undefined;
  if (!(value.functions as unknown[]).every(f => record(f) && opaqueId(f.symbolId) &&
      ["active", "inactive", "unknown"].includes(f.activity as string) && checkRange(f.declarationRange, f.uri))) return undefined;
  if (!(value.modules as unknown[]).every(m => record(m) &&
      ["active", "inactive", "unknown", "unresolved"].includes(m.activity as string) && checkRange(m.includeRange, m.uri))) return undefined;
  if (value.focus !== undefined && (!record(value.focus) || !opaqueId(value.focus.symbolId) ||
      !Array.isArray(value.focus.path) || value.focus.path.length > MAX_SNAPSHOT_RECORDS ||
      !value.focus.path.every(o => occurrence(o) && (o as Occurrence).symbolId === (value.focus as Record<string, unknown>).symbolId))) return undefined;
  for (const field of ["documents", "dependencies"]) {
    const dependencies = value[field];
    if (dependencies === undefined) continue;
    if (!Array.isArray(dependencies) || dependencies.length > 10_000) return undefined;
    for (const d of dependencies) {
      if (!record(d) || !canonicalFileUri(d.uri)) return undefined;
      const version = d.documentVersion ?? d.version;
      if (version !== null && version !== undefined && !integer(version)) return undefined;
      const open = docs.get(canonicalFileUri(d.uri));
      if (open && version !== open.version) return undefined;
    }
  }
  return value as unknown as SemanticSnapshot;
}

/** An explicit focus uses IDs, including "0", and never joins names. */
export function focusRanges(snapshot: SemanticSnapshot, symbolId: string): Range[] {
  if (!snapshot.complete || snapshot.focus?.symbolId !== symbolId) return [];
  return snapshot.focus.path.filter(o => canonicalFileUri(o.uri ?? snapshot.uri) === canonicalFileUri(snapshot.uri)).map(o => o.range);
}
