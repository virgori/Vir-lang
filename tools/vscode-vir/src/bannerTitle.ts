/**
 * File banner title detection (pure — no `vscode` import so it is unit-testable).
 *
 * A file banner is the first comment block of a file (optional shebang and blank
 * lines first), delimited by `##` … `##` or `#*#` … `#*#`:
 *
 *     ##
 *      * src/core/sys.vri — Standard Library Syscall & OS Interface
 *      ##
 *
 * The *title* is the first non-empty content line of that block. TextMate cannot
 * express "first content line" (it tokenizes line by line and `\G` matches at
 * every line start), so the semantic layer tags it as `bannerTitle`.
 */

export interface BannerTitleRange {
  line: number;
  start: number;
  length: number;
}

const OPENERS = ["#*#", "##"] as const;

function stripDecoration(text: string): { start: number; end: number } | undefined {
  // Leading whitespace and an optional `*` gutter.
  let start = 0;
  while (start < text.length && (text[start] === " " || text[start] === "\t")) {
    start++;
  }
  if (text[start] === "*") {
    start++;
    while (start < text.length && (text[start] === " " || text[start] === "\t")) {
      start++;
    }
  }
  // Trailing whitespace and an inline closer (`title ##`).
  let end = text.length;
  for (const closer of OPENERS) {
    const idx = text.lastIndexOf(closer);
    if (idx >= start && text.slice(idx + closer.length).trim() === "") {
      end = idx;
      break;
    }
  }
  while (end > start && (text[end - 1] === " " || text[end - 1] === "\t" || text[end - 1] === "\r")) {
    end--;
  }
  return end > start ? { start, end } : undefined;
}

function isDecorativeRule(text: string): boolean {
  return /^[ \t]*(?:\*[ \t]*)?[=\-_~*#+.]{3,}[ \t]*\r?$/.test(text);
}

export function findBannerTitle(lines: readonly string[]): BannerTitleRange | undefined {
  let i = 0;
  if (i < lines.length && lines[i].startsWith("#!")) {
    i++;
  }
  while (i < lines.length && lines[i].trim() === "") {
    i++;
  }
  if (i >= lines.length) {
    return undefined;
  }

  const first = lines[i];
  const trimmed = first.trimStart();
  const opener = OPENERS.find((o) => trimmed.startsWith(o));
  if (!opener) {
    return undefined;
  }
  const openerOffset = first.length - trimmed.length + opener.length;

  // `## Title` — text after the opener on the same line.
  const rest = first.slice(openerOffset);
  if (rest.trim() !== "" && !rest.trim().startsWith(opener)) {
    const span = stripDecoration(rest);
    if (span && !isDecorativeRule(rest)) {
      return { line: i, start: openerOffset + span.start, length: span.end - span.start };
    }
  }

  for (let j = i + 1; j < lines.length; j++) {
    const text = lines[j];
    if (text.trim() === "") {
      continue;
    }
    const t = text.trimStart();
    if (t.startsWith(opener)) {
      return undefined; // closer reached without a title
    }
    if (isDecorativeRule(text)) {
      continue;
    }
    const span = stripDecoration(text);
    if (span) {
      return { line: j, start: span.start, length: span.end - span.start };
    }
  }
  return undefined;
}
