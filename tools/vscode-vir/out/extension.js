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
exports.activate = activate;
exports.deactivate = deactivate;
const vscode = __importStar(require("vscode"));
const semanticTokens_1 = require("./semanticTokens");
const lspClient_1 = require("./lspClient");
const smartBar_1 = require("./smartBar");
const blockDiagnostics_1 = require("./blockDiagnostics");
const blockCommentValidation_1 = require("./blockCommentValidation");
const fallbackKeywords = [
    "entity",
    "func",
    "enum",
    "import",
    "export",
    "get",
    "end",
    "in",
    "out",
    "var",
    "if",
    "elif",
    "else",
    "for",
    "while",
    "return",
    "Matrix",
    "Vector",
    "int",
    "float",
    "bool",
    "string",
    "matmul",
    "grad",
    "embed",
    "train",
    "xor",
    "shr",
    "shl"
];
function registerFallbackCompletion(context) {
    const provider = vscode.languages.registerCompletionItemProvider({ language: "vir", scheme: "file" }, {
        provideCompletionItems() {
            return fallbackKeywords.map((k) => {
                const item = new vscode.CompletionItem(k, vscode.CompletionItemKind.Keyword);
                if (["matmul", "grad", "embed", "train"].includes(k)) {
                    item.detail = "Vir AI op";
                }
                if (["xor", "shr", "shl"].includes(k)) {
                    item.detail = "Vir system op";
                }
                return item;
            });
        }
    });
    context.subscriptions.push(provider);
}
function registerFallbackHover(context) {
    const docs = new Map([
        ["matmul", "`matmul(a, b)` multiplies matrix/tensor values."],
        ["grad", "`grad(x)` computes gradient representation for training/backprop."],
        ["embed", "`embed(x)` projects symbols/tokens into embedding space."],
        ["train", "`train(params, grads)` applies a training/update step."],
        ["Matrix", "`Matrix<rows, cols>` tensor type with static shape metadata."],
        ["Vector", "`Vector<n>` one-dimensional tensor type."]
    ]);
    const provider = vscode.languages.registerHoverProvider({ language: "vir", scheme: "file" }, {
        provideHover(document, position) {
            const range = document.getWordRangeAtPosition(position);
            if (!range) {
                return undefined;
            }
            const word = document.getText(range);
            const text = docs.get(word);
            return text ? new vscode.Hover(new vscode.MarkdownString(text), range) : undefined;
        }
    });
    context.subscriptions.push(provider);
}
function registerFallbackDiagnostics(context) {
    const collection = vscode.languages.createDiagnosticCollection("vir");
    context.subscriptions.push(collection);
    const validate = (doc) => {
        if (doc.languageId !== "vir") {
            return;
        }
        const diagnostics = [];
        for (let i = 0; i < doc.lineCount; i++) {
            const line = doc.lineAt(i).text;
            for (const m of line.matchAll(/\bMatrix\s*<([^>]*)>/g)) {
                const params = m[1].split(",").map((s) => s.trim()).filter(Boolean);
                if (params.length !== 2) {
                    const start = m.index ?? 0;
                    diagnostics.push(new vscode.Diagnostic(new vscode.Range(i, start, i, start + m[0].length), "Matrix shape must have exactly 2 dimensions: Matrix<rows, cols>.", vscode.DiagnosticSeverity.Error));
                    continue;
                }
                for (const p of params) {
                    if (!/^\d+$/.test(p)) {
                        const start = m.index ?? 0;
                        diagnostics.push(new vscode.Diagnostic(new vscode.Range(i, start, i, start + m[0].length), "Matrix dimensions must be positive integer literals.", vscode.DiagnosticSeverity.Warning));
                        break;
                    }
                }
            }
            for (const m of line.matchAll(/\bVector\s*<([^>]*)>/g)) {
                const params = m[1].split(",").map((s) => s.trim()).filter(Boolean);
                if (params.length !== 1 || !/^\d+$/.test(params[0])) {
                    const start = m.index ?? 0;
                    diagnostics.push(new vscode.Diagnostic(new vscode.Range(i, start, i, start + m[0].length), "Vector shape must be exactly one positive integer: Vector<n>.", vscode.DiagnosticSeverity.Warning));
                }
            }
        }
        collection.set(doc.uri, diagnostics);
    };
    context.subscriptions.push(vscode.workspace.onDidOpenTextDocument(validate));
    context.subscriptions.push(vscode.workspace.onDidChangeTextDocument((e) => validate(e.document)));
    context.subscriptions.push(vscode.workspace.onDidCloseTextDocument((doc) => collection.delete(doc.uri)));
    vscode.workspace.textDocuments.forEach(validate);
}
async function activate(context) {
    const cfg = vscode.workspace.getConfiguration("vir");
    if (cfg.get("semantic.enableEnhanced", true)) {
        (0, semanticTokens_1.registerSemanticTokens)(context);
    }
    // Register Smart Bar features
    (0, smartBar_1.registerSmartBar)(context);
    // Register Block Diagnostics (detect mismatched begin/end)
    (0, blockDiagnostics_1.registerBlockDiagnostics)(context);
    // Register Block Comment Validation (detect unclosed ## comments)
    (0, blockCommentValidation_1.registerBlockCommentValidation)(context);
    context.subscriptions.push(vscode.commands.registerCommand("vir.restartLanguageServer", async () => {
        await (0, lspClient_1.restartVirLanguageClient)(context);
        vscode.window.showInformationMessage("Virgori language server restarted.");
    }));
    const lspClient = await (0, lspClient_1.startVirLanguageClient)(context);
    if (!lspClient && cfg.get("ide.enableFallbackIntellisense", true)) {
        registerFallbackCompletion(context);
        registerFallbackHover(context);
        registerFallbackDiagnostics(context);
        vscode.window.setStatusBarMessage("Virgori: running fallback IDE providers (configure vir.lsp.serverPath for full LSP)", 5000);
    }
}
async function deactivate() {
    await (0, lspClient_1.stopVirLanguageClient)();
}
//# sourceMappingURL=extension.js.map