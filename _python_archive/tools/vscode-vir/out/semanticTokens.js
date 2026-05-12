"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.registerSemanticTokens = registerSemanticTokens;
const vscode = __importStar(require("vscode"));
const tokenTypes = [
    "keyword",
    "importKeyword",
    "terminatorKeyword",
    "function",
    "functionCall",
    "functionUnused",
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
    "shape"
];
const tokenModifiers = [];
const legend = new vscode.SemanticTokensLegend(tokenTypes, tokenModifiers);
const keywordSet = new Set(["entity", "func", "enum", "if", "elif", "else", "for", "while", "return", "in", "out", "var"]);
const importKeywordSet = new Set(["import", "export", "get"]);
const terminatorKeywordSet = new Set(["end"]);
const aiOps = new Set(["matmul", "grad", "embed", "train"]);
const systemOps = new Set(["xor", "shr", "shl"]);
const tensorTypes = new Set(["Matrix", "Vector"]);
const scalarTypes = new Set(["int", "float", "bool", "string"]);
const typePattern = /\b(Matrix|Vector|int|float|bool|string)\b/g;
const numberPattern = /\b(?:\d+\.\d+|\d+)(?:[eE][+-]?\d+)?\b/g;
const functionDeclPattern = /\bfunc\s+([A-Za-z_][A-Za-z0-9_]*)\b/g;
const functionCallPattern = /\b([A-Za-z_][A-Za-z0-9_]*)\s*(?=\()/g;
const parameterPattern = /\b(?:in|out)\s+([A-Za-z_][A-Za-z0-9_]*)\b/g;
const variableDeclPattern = /\bvar\s+([A-Za-z_][A-Za-z0-9_]*)\b/g;
const variableAssignPattern = /\b([A-Za-z_][A-Za-z0-9_]*)\b(?=\s*=(?!=))/g;
const forVariablePattern = /\bfor\s+([A-Za-z_][A-Za-z0-9_]*)\b/g;
const objectPropertyPattern = /\b([A-Za-z_][A-Za-z0-9_]*)\b\s*(?=:)/g;
const objectDelimiterPattern = /[{}]/g;
function pushMatches(builder, line, source, pattern, tokenType) {
    pattern.lastIndex = 0;
    for (;;) {
        const m = pattern.exec(source);
        if (!m) {
            break;
        }
        builder.push(line, m.index, m[0].length, tokenTypes.indexOf(tokenType), 0);
    }
}
function pushCaptureMatches(builder, line, source, pattern, tokenType, captureIndex = 1) {
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
        builder.push(line, m.index + captureOffset, tokenText.length, tokenTypes.indexOf(tokenType), 0);
    }
}
function collectFunctionUsage(document) {
    const declared = new Set();
    const called = new Set();
    for (let lineNo = 0; lineNo < document.lineCount; lineNo++) {
        const raw = document.lineAt(lineNo).text;
        const line = maskCommentAndString(raw);
        functionDeclPattern.lastIndex = 0;
        for (;;) {
            const m = functionDeclPattern.exec(line);
            if (!m) {
                break;
            }
            declared.add(m[1]);
        }
        functionCallPattern.lastIndex = 0;
        for (;;) {
            const m = functionCallPattern.exec(line);
            if (!m) {
                break;
            }
            const name = m[1];
            const before = line.slice(0, m.index);
            if (/\bfunc\s+$/.test(before)) {
                continue;
            }
            if (keywordSet.has(name) || importKeywordSet.has(name) || terminatorKeywordSet.has(name) || tensorTypes.has(name) || scalarTypes.has(name)) {
                continue;
            }
            called.add(name);
        }
    }
    return { declared, called };
}
function maskCommentAndString(line) {
    let out = line;
    const commentIndex = out.indexOf("//");
    if (commentIndex >= 0) {
        out = out.slice(0, commentIndex);
    }
    out = out.replace(/\"(?:\\.|[^\"\\])*\"/g, (s) => " ".repeat(s.length));
    return out;
}
function registerSemanticTokens(context) {
    const provider = {
        provideDocumentSemanticTokens(document) {
            const builder = new vscode.SemanticTokensBuilder(legend);
            const usage = collectFunctionUsage(document);
            for (let lineNo = 0; lineNo < document.lineCount; lineNo++) {
                const raw = document.lineAt(lineNo).text;
                const line = maskCommentAndString(raw);
                pushMatches(builder, lineNo, raw, /\"(?:\\.|[^\"\\])*\"/g, "string");
                pushMatches(builder, lineNo, line, numberPattern, "number");
                // Highlight shape metadata block inside Matrix<...> and Vector<...>.
                for (const match of line.matchAll(/\b(?:Matrix|Vector)\s*<[^>]*>/g)) {
                    if (match.index !== undefined) {
                        builder.push(lineNo, match.index, match[0].length, tokenTypes.indexOf("shape"), 0);
                    }
                }
                // General operators and special operators.
                pushMatches(builder, lineNo, line, /->|\^|>>|\$|\+|-|\*|\/|==|!=|<=|>=|<|>|=/g, "operator");
                typePattern.lastIndex = 0;
                for (;;) {
                    const m = typePattern.exec(line);
                    if (!m) {
                        break;
                    }
                    const ty = m[1];
                    const token = tensorTypes.has(ty) ? "tensorType" : "type";
                    builder.push(lineNo, m.index, ty.length, tokenTypes.indexOf(token), 0);
                }
                functionDeclPattern.lastIndex = 0;
                for (;;) {
                    const m = functionDeclPattern.exec(line);
                    if (!m) {
                        break;
                    }
                    const fnName = m[1];
                    const start = m.index + m[0].indexOf(fnName);
                    const calledToken = usage.called.has(fnName) ? "function" : "functionUnused";
                    builder.push(lineNo, start, fnName.length, tokenTypes.indexOf(calledToken), 0);
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
                    if (keywordSet.has(fnName) || importKeywordSet.has(fnName) || terminatorKeywordSet.has(fnName) || tensorTypes.has(fnName) || scalarTypes.has(fnName)) {
                        continue;
                    }
                    builder.push(lineNo, start, fnName.length, tokenTypes.indexOf("functionCall"), 0);
                }
                pushCaptureMatches(builder, lineNo, line, parameterPattern, "parameter");
                pushCaptureMatches(builder, lineNo, line, variableDeclPattern, "variable");
                pushCaptureMatches(builder, lineNo, line, variableAssignPattern, "variable");
                pushCaptureMatches(builder, lineNo, line, forVariablePattern, "variable");
                pushCaptureMatches(builder, lineNo, line, objectPropertyPattern, "objectProperty");
                pushMatches(builder, lineNo, line, objectDelimiterPattern, "object");
                for (const word of keywordSet) {
                    const p = new RegExp(`\\b${word}\\b`, "g");
                    pushMatches(builder, lineNo, line, p, "keyword");
                }
                for (const word of importKeywordSet) {
                    const p = new RegExp(`\\b${word}\\b`, "g");
                    pushMatches(builder, lineNo, line, p, "importKeyword");
                }
                for (const word of terminatorKeywordSet) {
                    const p = new RegExp(`\\b${word}\\b`, "g");
                    pushMatches(builder, lineNo, line, p, "terminatorKeyword");
                }
                for (const word of aiOps) {
                    const p = new RegExp(`\\b${word}\\b`, "g");
                    pushMatches(builder, lineNo, line, p, "aiOp");
                }
                for (const word of systemOps) {
                    const p = new RegExp(`\\b${word}\\b`, "g");
                    pushMatches(builder, lineNo, line, p, "systemOp");
                }
            }
            return builder.build();
        }
    };
    const selector = [{ language: "vir", scheme: "file" }];
    const disposable = vscode.languages.registerDocumentSemanticTokensProvider(selector, provider, legend);
    context.subscriptions.push(disposable);
    return disposable;
}
//# sourceMappingURL=semanticTokens.js.map