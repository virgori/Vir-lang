import * as vscode from "vscode";
import type { IdeShapeDimension } from "./virIdeSemantic";

export interface ShapeSpan {
  line: number;
  start: number;
  length: number;
}

export function maskCommentAndString(line: string): string {
  if (/^\s*(?:#\*#|##|#)/.test(line)) {
    return " ".repeat(line.length);
  }
  let out = line;
  const slashComment = out.indexOf("//");
  if (slashComment >= 0) {
    out = out.slice(0, slashComment);
  }
  const hashTail = out.search(/\s#(?![*#])/);
  if (hashTail >= 0) {
    out = out.slice(0, hashTail);
  }
  out = out.replace(/\"(?:\\.|[^\"\\])*\"/g, (s) => " ".repeat(s.length));
  return out;
}

/** TextMate-aligned literals inside static shape annotations (fallback when IDE has no spans). */
export function collectHeuristicShapeLiterals(line: string, lineNo: number): ShapeSpan[] {
  const masked = maskCommentAndString(line);
  const out: ShapeSpan[] = [];

  for (const m of masked.matchAll(/\b(?:Matrix|Vector)\s*<([^>]*)>/g)) {
    if (m.index === undefined) {
      continue;
    }
    const inner = m[1];
    const lt = m[0].indexOf("<");
    if (lt < 0) {
      continue;
    }
    const innerStart = m.index + lt + 1;
    let searchFrom = 0;
    for (const part of inner.split(",")) {
      const t = part.trim();
      if (!/^\d+$/.test(t)) {
        continue;
      }
      const rel = inner.indexOf(t, searchFrom);
      if (rel < 0) {
        continue;
      }
      out.push({ line: lineNo, start: innerStart + rel, length: t.length });
      searchFrom = rel + t.length;
    }
  }

  for (const m of masked.matchAll(/\btensor\s*\[[^\]]*;([^\]]*)\]/gi)) {
    if (m.index === undefined) {
      continue;
    }
    const semiPart = m[1];
    const semiStart = m[0].indexOf(";");
    if (semiStart < 0) {
      continue;
    }
    const innerStart = m.index + semiStart + 1;
    let searchFrom = 0;
    for (const part of semiPart.split(",")) {
      const t = part.trim();
      if (!/^\d+$/.test(t)) {
        continue;
      }
      const rel = semiPart.indexOf(t, searchFrom);
      if (rel < 0) {
        continue;
      }
      out.push({ line: lineNo, start: innerStart + rel, length: t.length });
      searchFrom = rel + t.length;
    }
  }

  return out;
}

function spanKey(s: ShapeSpan): string {
  return `${s.line}:${s.start}:${s.length}`;
}

/** Map compiler-known dimension values to source columns (1-based line in IDE JSON). */
export function resolveShapeSpansFromIde(
  document: vscode.TextDocument,
  dims: IdeShapeDimension[]
): ShapeSpan[] {
  const byLine = new Map<number, IdeShapeDimension[]>();
  for (const d of dims) {
    const line0 = Math.max(0, d.line - 1);
    const list = byLine.get(line0) ?? [];
    list.push(d);
    byLine.set(line0, list);
  }

  const resolved: ShapeSpan[] = [];
  const used = new Set<string>();

  for (const [line0, list] of byLine) {
    const raw = document.lineAt(line0).text;
    const candidates = collectHeuristicShapeLiterals(raw, line0);
    let candIdx = 0;

    for (const d of list) {
      const col = d.col ?? 0;
      const endCol = d.endCol ?? 0;
      if (col > 0 && endCol > col) {
        const start = col - 1;
        const length = endCol - col;
        const sp: ShapeSpan = { line: line0, start, length };
        const key = spanKey(sp);
        if (!used.has(key)) {
          used.add(key);
          resolved.push(sp);
        }
        continue;
      }

      while (candIdx < candidates.length) {
        const c = candidates[candIdx];
        candIdx += 1;
        const slice = raw.slice(c.start, c.start + c.length);
        if (parseInt(slice, 10) === d.value) {
          const key = spanKey(c);
          if (!used.has(key)) {
            used.add(key);
            resolved.push(c);
          }
          break;
        }
      }
    }
  }

  return resolved;
}

export function mergeShapeSpans(compiler: ShapeSpan[], heuristic: ShapeSpan[]): ShapeSpan[] {
  const out: ShapeSpan[] = [];
  const used = new Set<string>();
  for (const s of compiler) {
    const key = spanKey(s);
    if (!used.has(key)) {
      used.add(key);
      out.push(s);
    }
  }
  for (const s of heuristic) {
    const key = spanKey(s);
    if (!used.has(key)) {
      used.add(key);
      out.push(s);
    }
  }
  return out;
}

export function collectDocumentShapeSpans(
  document: vscode.TextDocument,
  ideDims?: IdeShapeDimension[]
): ShapeSpan[] {
  const heuristic: ShapeSpan[] = [];
  for (let lineNo = 0; lineNo < document.lineCount; lineNo++) {
    heuristic.push(...collectHeuristicShapeLiterals(document.lineAt(lineNo).text, lineNo));
  }

  if (ideDims && ideDims.length > 0) {
    const fromIde = resolveShapeSpansFromIde(document, ideDims);
    if (fromIde.length > 0) {
      return mergeShapeSpans(fromIde, heuristic);
    }
  }

  return heuristic;
}

export function spanCovers(spans: ShapeSpan[], line: number, start: number, length: number): boolean {
  const end = start + length;
  for (const s of spans) {
    if (s.line !== line) {
      continue;
    }
    const sEnd = s.start + s.length;
    if (start >= s.start && end <= sEnd) {
      return true;
    }
  }
  return false;
}
