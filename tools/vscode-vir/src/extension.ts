import * as vscode from "vscode";
import { registerSemanticTokens } from "./semanticTokens";
import { restartVirLanguageClient, startVirLanguageClient, stopVirLanguageClient } from "./lspClient";

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

function registerFallbackCompletion(context: vscode.ExtensionContext): void {
  const provider = vscode.languages.registerCompletionItemProvider(
    { language: "vir", scheme: "file" },
    {
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
    }
  );
  context.subscriptions.push(provider);
}

function registerFallbackHover(context: vscode.ExtensionContext): void {
  const docs = new Map<string, string>([
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

function registerFallbackDiagnostics(context: vscode.ExtensionContext): void {
  const collection = vscode.languages.createDiagnosticCollection("vir");
  context.subscriptions.push(collection);

  const validate = (doc: vscode.TextDocument): void => {
    if (doc.languageId !== "vir") {
      return;
    }

    const diagnostics: vscode.Diagnostic[] = [];

    for (let i = 0; i < doc.lineCount; i++) {
      const line = doc.lineAt(i).text;

      for (const m of line.matchAll(/\bMatrix\s*<([^>]*)>/g)) {
        const params = m[1].split(",").map((s) => s.trim()).filter(Boolean);
        if (params.length !== 2) {
          const start = m.index ?? 0;
          diagnostics.push(new vscode.Diagnostic(
            new vscode.Range(i, start, i, start + m[0].length),
            "Matrix shape must have exactly 2 dimensions: Matrix<rows, cols>.",
            vscode.DiagnosticSeverity.Error
          ));
          continue;
        }
        for (const p of params) {
          if (!/^\d+$/.test(p)) {
            const start = m.index ?? 0;
            diagnostics.push(new vscode.Diagnostic(
              new vscode.Range(i, start, i, start + m[0].length),
              "Matrix dimensions must be positive integer literals.",
              vscode.DiagnosticSeverity.Warning
            ));
            break;
          }
        }
      }

      for (const m of line.matchAll(/\bVector\s*<([^>]*)>/g)) {
        const params = m[1].split(",").map((s) => s.trim()).filter(Boolean);
        if (params.length !== 1 || !/^\d+$/.test(params[0])) {
          const start = m.index ?? 0;
          diagnostics.push(new vscode.Diagnostic(
            new vscode.Range(i, start, i, start + m[0].length),
            "Vector shape must be exactly one positive integer: Vector<n>.",
            vscode.DiagnosticSeverity.Warning
          ));
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

export async function activate(context: vscode.ExtensionContext): Promise<void> {
  const cfg = vscode.workspace.getConfiguration("vir");

  if (cfg.get<boolean>("semantic.enableEnhanced", true)) {
    registerSemanticTokens(context);
  }

  context.subscriptions.push(vscode.commands.registerCommand("vir.restartLanguageServer", async () => {
    await restartVirLanguageClient(context);
    vscode.window.showInformationMessage("Virgori language server restarted.");
  }));

  const lspClient = await startVirLanguageClient(context);
  if (!lspClient && cfg.get<boolean>("ide.enableFallbackIntellisense", true)) {
    registerFallbackCompletion(context);
    registerFallbackHover(context);
    registerFallbackDiagnostics(context);

    vscode.window.setStatusBarMessage("Virgori: running fallback IDE providers (configure vir.lsp.serverPath for full LSP)", 5000);
  }
}

export async function deactivate(): Promise<void> {
  await stopVirLanguageClient();
}
