/**
 * Active / inactive symbol state (pure — no `vscode` import).
 *
 * The compiler (`virc --ide-semantic --json`) is the single source of truth: it
 * resolves symbols and builds the reference/dependency graph. This module only
 * translates the compiler's per-symbol answer into semantic-token descriptors.
 * It never inspects source text to decide usage.
 */

export type SymbolKind = "module" | "function" | "type" | "constant" | "import";
export type SymbolState = "active" | "inactive" | "unresolved";

export interface IdeSymbol {
  name: string;
  kind: SymbolKind;
  /** 1-based, as emitted by the compiler. */
  line: number;
  col: number;
  endCol: number;
  state: SymbolState;
}

export interface SymbolTokenSpec {
  /** 0-based */
  line: number;
  start: number;
  length: number;
  /** Semantic token type id (see `SYMBOL_TOKEN_TYPES`). */
  tokenType: string;
  modifier: "active" | "inactive";
}

export const SYMBOL_TOKEN_TYPES: Record<SymbolKind, string> = {
  module: "moduleName",
  function: "function",
  type: "type",
  constant: "constant",
  import: "importedSymbol"
};

const KINDS = new Set<string>(["module", "function", "type", "constant", "import"]);

export function normalizeSymbols(raw: unknown): IdeSymbol[] {
  if (!Array.isArray(raw)) {
    return [];
  }
  const out: IdeSymbol[] = [];
  for (const item of raw) {
    const s = item as Partial<IdeSymbol>;
    if (!s || typeof s.name !== "string" || typeof s.kind !== "string" || !KINDS.has(s.kind)) {
      continue;
    }
    if (typeof s.line !== "number" || s.line < 1) {
      continue;
    }
    // `col` 0 / missing = the parser recorded no column; the name is located on `line`.
    const col = typeof s.col === "number" && s.col > 0 ? s.col : 0;
    const state: SymbolState = s.state === "active" || s.state === "unresolved" ? s.state : "inactive";
    const endCol = typeof s.endCol === "number" && s.endCol > col ? s.endCol : col + s.name.length;
    out.push({ name: s.name, kind: s.kind as SymbolKind, line: s.line, col, endCol, state });
  }
  return out;
}

/**
 * Convert legacy `modules` / `functions` arrays (older compilers without the
 * unified `symbols` list) into symbols. Pure shape conversion, no analysis.
 */
export function symbolsFromLegacy(
  modules: ReadonlyArray<{ name: string; line: number; col: number; state: SymbolState }>,
  functions: ReadonlyArray<{ name: string; line: number; col: number; endCol: number; state: SymbolState }>,
  moduleColumn: (m: { name: string; line: number; col: number }) => { col: number; endCol: number }
): IdeSymbol[] {
  const out: IdeSymbol[] = [];
  for (const m of modules) {
    const c = moduleColumn(m);
    out.push({ name: m.name, kind: "module", line: m.line, col: c.col, endCol: c.endCol, state: m.state });
  }
  for (const f of functions) {
    out.push({ name: f.name, kind: "function", line: f.line, col: f.col, endCol: f.endCol, state: f.state });
  }
  return out;
}

const isIdentChar = (c: string | undefined): boolean => c !== undefined && /[A-Za-z0-9_]/.test(c);

/**
 * Find the compiler-reported symbol on its reported line. This is *positioning only*:
 * the compiler already decided which symbol it is and what state it is in; the parser
 * just does not record every column. `maskedLine` must have comments/strings blanked.
 *
 * - exact hit at the reported column wins;
 * - otherwise the whole-word occurrence closest to the hint (or the first one);
 * - member access (`x.name`) is never a declaration/import site, except inside dotted
 *   module names, which are matched as a whole.
 */
export function locateSymbol(
  maskedLine: string,
  sym: Pick<IdeSymbol, "name" | "kind" | "col">
): { start: number; length: number } | undefined {
  const name = sym.name;
  if (!name) {
    return undefined;
  }
  const isModule = sym.kind === "module";
  const okAt = (at: number): boolean => {
    if (maskedLine.substr(at, name.length) !== name) {
      return false;
    }
    const prev = maskedLine[at - 1];
    const next = maskedLine[at + name.length];
    if (isIdentChar(prev) || isIdentChar(next)) {
      return false;
    }
    if (prev === "." || (isModule && next === ".")) {
      return false;
    }
    return true;
  };

  const hint = sym.col > 0 ? sym.col - 1 : -1;
  if (hint >= 0 && okAt(hint)) {
    return { start: hint, length: name.length };
  }
  let best = -1;
  for (let at = maskedLine.indexOf(name); at >= 0; at = maskedLine.indexOf(name, at + 1)) {
    if (!okAt(at)) {
      continue;
    }
    if (hint < 0) {
      best = at;
      break;
    }
    if (best < 0 || Math.abs(at - hint) < Math.abs(best - hint)) {
      best = at;
    }
  }
  return best >= 0 ? { start: best, length: name.length } : undefined;
}

/**
 * Tokens for resolved symbols only. `unresolved` symbols are deliberately
 * skipped: they must never receive the inactive colour and keep whatever
 * diagnostics/colouring they already have. `getMaskedLine` returns the 0-based
 * line with comments and strings blanked (undefined when out of range).
 */
export function symbolTokenSpecs(
  symbols: readonly IdeSymbol[],
  getMaskedLine: (line0: number) => string | undefined
): SymbolTokenSpec[] {
  const specs: SymbolTokenSpec[] = [];
  const claimed = new Set<string>();
  for (const s of symbols) {
    if (s.state === "unresolved" || s.line < 1) {
      continue;
    }
    const text = getMaskedLine(s.line - 1);
    if (text === undefined) {
      continue;
    }
    const loc = locateSymbol(text, s);
    if (!loc) {
      continue;
    }
    const key = `${s.line}:${loc.start}`;
    if (claimed.has(key)) {
      continue;
    }
    claimed.add(key);
    specs.push({
      line: s.line - 1,
      start: loc.start,
      length: loc.length,
      tokenType: SYMBOL_TOKEN_TYPES[s.kind],
      modifier: s.state
    });
  }
  return specs;
}
