import * as vscode from "vscode";
import { collectDocumentShapeSpans, maskCommentAndString } from "./shapeDimensionSpans";
import { findBannerTitle } from "./bannerTitle";
import { symbolsFromLegacy, symbolTokenSpecs, type IdeSymbol } from "./symbolState";
import { fetchIdeSnapshot, type IdeSnapshot } from "./virIdeSemantic";

const tokenTypes = [
  "keyword",
  "importKeyword",
  "terminatorKeyword",
  "function",
  "functionCall",
  "parameter",
  "variable",
  "object",
  "objectProperty",
  "type",
  "number",
  "string",
  "operator",
  "aiOp",
  "systemOp",
  "tensorType",
  "shape",
  "shapeDimension",
  "returnArrow",
  "bannerTitle",
  "moduleName",
  "importedSymbol",
  "constant"
];

/** Bit 0 = active, bit 1 = inactive (see `contributes.semanticTokenModifiers`). */
const tokenModifiers: string[] = ["active", "inactive"];
const MOD_ACTIVE = 1 << 0;
const MOD_INACTIVE = 1 << 1;

const legend = new vscode.SemanticTokensLegend(tokenTypes, tokenModifiers);

const keywordSet = new Set(["entity", "func", "enum", "if", "elif", "else", "for", "while", "return", "in", "ref", "out", "var"]);
const importKeywordSet = new Set(["import", "export", "get"]);
const terminatorKeywordSet = new Set(["end"]);
const aiOps = new Set(["matmul", "grad", "embed", "train"]);
/** Bitwise / word operators (Vir keywords — not C `<<`/`>>`; `>>` is cast). */
const systemOps = new Set([
  "and",
  "or",
  "xor",
  "not",
  "shl",
  "shr",
  "mod",
  "bit_and",
  "bit_or",
  "bit_xor",
  "bit_shl",
  "bit_shr"
]);
const tensorTypes = new Set(["Matrix", "Vector", "tensor", "Tensor", "flux"]);
const scalarTypes = new Set([
  "int",
  "float",
  "bool",
  "string",
  "i64",
  "i32",
  "i16",
  "i8",
  "u64",
  "u32",
  "u16",
  "u8",
  "f32",
  "f64",
  "void",
  "none"
]);

const typePattern =
  /\b(Matrix|Vector|tensor|Tensor|flux|Option|Result|Vec|Map|int|float|bool|string|i64|i32|i16|i8|u64|u32|u16|u8|f32|f64|void|none)\b/g;
const ufcsCallPattern = /\.([A-Za-z_][A-Za-z0-9_]*)\s*(?=\()/g;
const functionDeclPattern = /\bfunc\s+([A-Za-z_][A-Za-z0-9_]*)\b/g;
const functionCallPattern = /\b([A-Za-z_][A-Za-z0-9_]*)\s*(?=\()/g;
const parameterPattern = /\b(?:in|ref|out)\s+([A-Za-z_][A-Za-z0-9_]*)\b/g;
const variableDeclPattern = /\bvar\s+([A-Za-z_][A-Za-z0-9_]*)\b/g;
const variableAssignPattern = /\b([A-Za-z_][A-Za-z0-9_]*)\b(?=\s*=(?!=))/g;
const forVariablePattern = /\bfor\s+([A-Za-z_][A-Za-z0-9_]*)\b/g;
const objectPropertyPattern = /\b([A-Za-z_][A-Za-z0-9_]*)\b\s*(?=:)/g;
const objectDelimiterPattern = /[{}]/g;

interface PendingToken {
  line: number;
  start: number;
  length: number;
  type: number;
  modifiers: number;
  order: number;
}

/**
 * SemanticTokensBuilder requires strictly ascending positions, but the scanners
 * below run pattern-by-pattern. Collect first, then emit sorted; earlier pushes
 * win when ranges overlap.
 */
class TokenSink {
  private readonly tokens: PendingToken[] = [];
  private order = 0;

  push(line: number, start: number, length: number, type: number, modifiers = 0): void {
    if (type < 0 || length <= 0) {
      return;
    }
    this.tokens.push({ line, start, length, type, modifiers, order: this.order++ });
  }

  build(): vscode.SemanticTokens {
    this.tokens.sort((a, b) =>
      a.line !== b.line ? a.line - b.line : a.start !== b.start ? a.start - b.start : a.order - b.order
    );

    const builder = new vscode.SemanticTokensBuilder(legend);
    let lastLine = -1;
    let lastEnd = 0;
    for (const t of this.tokens) {
      if (t.line === lastLine && t.start < lastEnd) {
        continue;
      }
      builder.push(t.line, t.start, t.length, t.type, t.modifiers);
      lastLine = t.line;
      lastEnd = t.start + t.length;
    }
    return builder.build();
  }
}

function pushMatches(
  builder: TokenSink,
  line: number,
  source: string,
  pattern: RegExp,
  tokenType: string
): void {
  pattern.lastIndex = 0;
  for (;;) {
    const m = pattern.exec(source);
    if (!m) {
      break;
    }
    builder.push(line, m.index, m[0].length, tokenTypes.indexOf(tokenType));
  }
}

function pushCaptureMatches(
  builder: TokenSink,
  line: number,
  source: string,
  pattern: RegExp,
  tokenType: string,
  captureIndex = 1
): void {
  pattern.lastIndex = 0;
  for (;;) {
    const m = pattern.exec(source);
    if (!m) {
      break;
    }
    const tokenText = m[captureIndex];
    if (!tokenText) {
      continue;
    }
    const full = m[0];
    const captureOffset = full.indexOf(tokenText);
    if (captureOffset < 0) {
      continue;
    }
    builder.push(line, m.index + captureOffset, tokenText.length, tokenTypes.indexOf(tokenType));
  }
}

/** Compiler symbols, or (older compiler) the legacy modules/functions lists reshaped. */
function collectSymbols(document: vscode.TextDocument, ide: IdeSnapshot): IdeSymbol[] {
  if (ide.symbols) {
    return ide.symbols;
  }
  return symbolsFromLegacy(ide.modules, ide.functions, (m) => {
    const lineText = document.lineAt(Math.max(0, Math.min(document.lineCount - 1, m.line - 1))).text;
    const inc = lineText.match(/\binclude\s+([A-Za-z_][A-Za-z0-9_.]*)/);
    if (inc && inc.index !== undefined) {
      const start = inc.index + inc[0].indexOf(inc[1]);
      return { col: start + 1, endCol: start + 1 + inc[1].length };
    }
    return { col: m.col, endCol: m.col + m.name.length };
  });
}

function buildSemanticTokens(document: vscode.TextDocument, ide?: IdeSnapshot): vscode.SemanticTokens {
  const builder = new TokenSink();
  const cfg = vscode.workspace.getConfiguration("vir");
  const compilerShape = cfg.get<boolean>("semantic.shape.compilerBacked", true);
  const symbolStateOn = cfg.get<boolean>("semantic.symbolState.enabled", true);

  const ideDims =
    compilerShape && ide && ide.shapeDimensions.length > 0 ? ide.shapeDimensions : undefined;
  const shapeSpans = collectDocumentShapeSpans(document, ideDims);
  const shapeDimType = tokenTypes.indexOf("shapeDimension");

  // File banner title: the first content line of the leading `##` / `#*#` block.
  const bannerLines: string[] = [];
  const scanLimit = Math.min(document.lineCount, 64);
  for (let i = 0; i < scanLimit; i++) {
    bannerLines.push(document.lineAt(i).text);
  }
  const title = findBannerTitle(bannerLines);
  if (title) {
    builder.push(title.line, title.start, title.length, tokenTypes.indexOf("bannerTitle"));
  }

  // Active/inactive symbol state: compiler-resolved, pushed before every heuristic
  // token so it wins on overlap. `unresolved` symbols get no token at all.
  if (symbolStateOn && ide) {
    const symbols = collectSymbols(document, ide);
    const maskedLineAt = (l: number): string | undefined =>
      l >= 0 && l < document.lineCount ? maskCommentAndString(document.lineAt(l).text) : undefined;
    for (const spec of symbolTokenSpecs(symbols, maskedLineAt)) {
      builder.push(
        spec.line,
        spec.start,
        spec.length,
        tokenTypes.indexOf(spec.tokenType),
        spec.modifier === "active" ? MOD_ACTIVE : MOD_INACTIVE
      );
    }
  }

  for (let lineNo = 0; lineNo < document.lineCount; lineNo++) {
    const raw = document.lineAt(lineNo).text;
    const line = maskCommentAndString(raw);

    // Strings, numbers, operators and `->` are left to the TextMate grammar on purpose:
    // it already tokenizes them as single units, and a second semantic layer over the
    // same characters is what used to split `->` into two colors.
    for (const sp of shapeSpans) {
      if (sp.line === lineNo) {
        builder.push(lineNo, sp.start, sp.length, shapeDimType);
      }
    }

    pushCaptureMatches(builder, lineNo, line, ufcsCallPattern, "functionCall");

    typePattern.lastIndex = 0;
    for (;;) {
      const m = typePattern.exec(line);
      if (!m) {
        break;
      }
      const ty = m[1];
      const token = tensorTypes.has(ty) ? "tensorType" : "type";
      builder.push(lineNo, m.index, ty.length, tokenTypes.indexOf(token));
    }

    functionDeclPattern.lastIndex = 0;
    for (;;) {
      const m = functionDeclPattern.exec(line);
      if (!m) {
        break;
      }
      const fnName = m[1];
      const start = m.index + m[0].length - fnName.length;
      builder.push(lineNo, start, fnName.length, tokenTypes.indexOf("function"));
    }

    functionCallPattern.lastIndex = 0;
    for (;;) {
      const m = functionCallPattern.exec(line);
      if (!m) {
        break;
      }
      const fnName = m[1];
      const start = m.index;
      const before = line.slice(0, start);
      if (/\bfunc\s+$/.test(before)) {
        continue;
      }
      if (
        keywordSet.has(fnName) ||
        importKeywordSet.has(fnName) ||
        terminatorKeywordSet.has(fnName) ||
        tensorTypes.has(fnName) ||
        scalarTypes.has(fnName) ||
        systemOps.has(fnName) ||
        aiOps.has(fnName)
      ) {
        continue;
      }
      builder.push(lineNo, start, fnName.length, tokenTypes.indexOf("functionCall"));
    }

    pushCaptureMatches(builder, lineNo, line, parameterPattern, "parameter");
    pushCaptureMatches(builder, lineNo, line, variableDeclPattern, "variable");
    pushCaptureMatches(builder, lineNo, line, variableAssignPattern, "variable");
    pushCaptureMatches(builder, lineNo, line, forVariablePattern, "variable");
    // `name: type` in declarations is a type annotation, not an object key.
    if (line.includes("{")) {
      pushCaptureMatches(builder, lineNo, line, objectPropertyPattern, "objectProperty");
    }
    pushMatches(builder, lineNo, line, objectDelimiterPattern, "object");

    for (const word of keywordSet) {
      pushMatches(builder, lineNo, line, new RegExp(`\\b${word}\\b`, "g"), "keyword");
    }
    for (const word of importKeywordSet) {
      pushMatches(builder, lineNo, line, new RegExp(`\\b${word}\\b`, "g"), "importKeyword");
    }
    for (const word of terminatorKeywordSet) {
      pushMatches(builder, lineNo, line, new RegExp(`\\b${word}\\b`, "g"), "terminatorKeyword");
    }
    for (const word of aiOps) {
      pushMatches(builder, lineNo, line, new RegExp(`\\b${word}\\b`, "g"), "aiOp");
    }
    for (const word of systemOps) {
      pushMatches(builder, lineNo, line, new RegExp(`\\b${word}\\b`, "g"), "systemOp");
    }
  }

  return builder.build();
}

export function registerSemanticTokens(context: Pick<vscode.ExtensionContext, "subscriptions">): vscode.Disposable {
  const provider: vscode.DocumentSemanticTokensProvider = {
    provideDocumentSemanticTokens(
      document: vscode.TextDocument,
      token: vscode.CancellationToken
    ): vscode.ProviderResult<vscode.SemanticTokens> {
      const cfg = vscode.workspace.getConfiguration("vir");
      const needIde =
        cfg.get<boolean>("semantic.lifetime.enabled", true) ||
        cfg.get<boolean>("semantic.symbolState.enabled", true) ||
        (cfg.get<boolean>("semantic.shape.compilerBacked", true) &&
          cfg.get<boolean>("semantic.enableEnhanced", true));

      if (!needIde) {
        return buildSemanticTokens(document);
      }

      return fetchIdeSnapshot(document, { token }).then((snap) => {
        if (token.isCancellationRequested) {
          return undefined;
        }
        return buildSemanticTokens(document, snap);
      });
    }
  };

  const selector: vscode.DocumentSelector = [{ language: "vir", scheme: "file" }];
  const disposable = vscode.languages.registerDocumentSemanticTokensProvider(selector, provider, legend);
  context.subscriptions.push(disposable);
  return disposable;
}
