import * as vscode from "vscode";
import { registerSemanticTokens } from "./semanticTokens";
import { restartVirLanguageClient, startVirLanguageClient, stopVirLanguageClient } from "./lspClient";
import { LifetimeDecorationController } from "./lifetimeDecorations";
import { fetchIdeSnapshot } from "./virIdeSemantic";

const fallbackKeywords = [
  "entity",
  "func",
  "enum",
  "import",
  "export",
  "get",
  "end",
  "in",
  "ref",
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
];

const bitwiseOps = new Set([
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

function registerFallbackCompletion(context: Pick<vscode.ExtensionContext, "subscriptions">): void {
  const provider = vscode.languages.registerCompletionItemProvider(
    { language: "vir", scheme: "file" },
    {
      provideCompletionItems() {
        return fallbackKeywords.map((k) => {
          const item = new vscode.CompletionItem(k, vscode.CompletionItemKind.Keyword);
          if (["matmul", "grad", "embed", "train"].includes(k)) {
            item.detail = "Vir AI op";
          }
          if (bitwiseOps.has(k)) {
            item.detail = "Vir bitwise / word operator";
          }
          return item;
        });
      }
    }
  );
  context.subscriptions.push(provider);
}

function registerFallbackHover(context: Pick<vscode.ExtensionContext, "subscriptions">): void {
  const docs = new Map<string, string>([
    ["matmul", "`matmul(a, b)` multiplies matrix/tensor values."],
    ["grad", "`grad(x)` computes gradient representation for training/backprop."],
    ["embed", "`embed(x)` projects symbols/tokens into embedding space."],
    ["train", "`train(params, grads)` applies a training/update step."],
    ["Matrix", "`Matrix<rows, cols>` tensor type with static shape metadata."],
    ["Vector", "`Vector<n>` one-dimensional tensor type."],
    ["and", "`a and b` — bitwise AND (Vir keyword; not C `&&`)."],
    ["or", "`a or b` — bitwise OR (Vir keyword; not C `|` alone for this form)."],
    ["xor", "`a xor b` — bitwise XOR."],
    ["not", "`not a` — bitwise NOT."],
    ["shl", "`a shl n` — shift left. Prefer keyword over `<<`."],
    ["shr", "`a shr n` — shift right. **`>>` is type cast**, not shift."],
    ["mod", "`a mod b` — integer remainder."],
    ["bit_and", "`bit_and` — alias of bitwise `and`."],
    ["bit_or", "`bit_or` — alias of bitwise `or`."],
    ["bit_xor", "`bit_xor` — alias of bitwise `xor`."],
    ["bit_shl", "`bit_shl` — alias of `shl`."],
    ["bit_shr", "`bit_shr` — alias of `shr`."],
    ["in", "`in` — Parameter modifier / section header for by-value input parameters (read-only or moved/consumed)."],
    ["ref", "`ref` — Parameter modifier / section header for mutable borrowed reference parameters (`&mut`), must be initialized before call."],
    ["out", "`out` — Function return statement (`out expr`) or output parameter modifier / section header (caller passes uninitialized/destination binding, callee must assign before exit)."]
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

function registerFallbackDiagnostics(context: Pick<vscode.ExtensionContext, "subscriptions">): void {
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

function registerLifetimeHover(context: Pick<vscode.ExtensionContext, "subscriptions">): void {
  const provider = vscode.languages.registerHoverProvider({ language: "vir", scheme: "file" }, {
    async provideHover(document, position) {
      const snap = await fetchIdeSnapshot(document);
      if (!snap) {
        return undefined;
      }
      const line = position.line + 1;
      const col = position.character + 1;
      const occ = snap.occurrences.find(
        (o) => o.kind === 0 && o.line === line && col >= o.col && col <= o.endCol
      );
      const parts: string[] = [];
      if (occ) {
        const state =
          occ.state & 16
            ? "invalid"
            : occ.state & 8
              ? "out"
              : occ.state & 4
                ? "moved"
                : occ.state & 1
                  ? "declared"
                  : "alive";
        parts.push(`**variable** · \`${state}\` · symbol #${occ.symbolId}`);
      }
      const mod = snap.modules.find((m) => m.line === line);
      if (mod) {
        parts.push(`**module** \`${mod.name}\` · \`${mod.state}\``);
      }
      const fn = snap.functions?.find((f) => f.line === line && col >= f.col && col <= f.endCol);
      if (fn) {
        parts.push(`**function** \`${fn.name}\` · \`${fn.state}\` · symbol #${fn.symbolId}`);
      }
      if (parts.length === 0) {
        return undefined;
      }
      return new vscode.Hover(new vscode.MarkdownString(parts.join("\n\n")));
    }
  });
  context.subscriptions.push(provider);
}

/** Other installed extensions that also claim the `vir` language / `source.vri` grammar. */
const CONFLICTING_EXTENSION_IDS = ["virgori.virgori-core"];

function warnAboutConflictingExtensions(context: vscode.ExtensionContext): void {
  const found = CONFLICTING_EXTENSION_IDS.filter((id) => vscode.extensions.getExtension(id));
  if (found.length === 0) {
    return;
  }
  const key = "vir.conflictWarned";
  if (context.globalState.get<string>(key) === found.join(",")) {
    return;
  }
  void vscode.window
    .showWarningMessage(
      `Vir-lang: ${found.join(", ")} also provides Vir highlighting (grammar, semantic tokens, same theme names). ` +
        "Two providers overlap and split tokens such as `->` into two colors. Disable or uninstall it.",
      "Show Extension",
      "Don't Warn Again"
    )
    .then((choice) => {
      if (choice === "Show Extension") {
        void vscode.commands.executeCommand("workbench.extensions.search", `@installed ${found[0]}`);
      } else if (choice === "Don't Warn Again") {
        void context.globalState.update(key, found.join(","));
      }
    });
}

export async function activate(context: vscode.ExtensionContext): Promise<void> {
  warnAboutConflictingExtensions(context);
  const fallbackContext = { subscriptions: [] as vscode.Disposable[] };
  const clearFallback = () => {
    for (const disposable of fallbackContext.subscriptions.splice(0)) disposable.dispose();
  };
  context.subscriptions.push({ dispose: clearFallback });
  const connect = async (restart: boolean) => {
    clearFallback();
    const cfg = vscode.workspace.getConfiguration("vir");
    const activeClient = restart ? await restartVirLanguageClient(context) : await startVirLanguageClient(context);
    if (activeClient) return;
    if (cfg.get<boolean>("semantic.enableEnhanced", true)) registerSemanticTokens(fallbackContext);
    if (cfg.get<boolean>("semantic.lifetime.enabled", true)) {
      const lifetime = new LifetimeDecorationController();
      fallbackContext.subscriptions.push(lifetime);
      registerLifetimeHover(fallbackContext);
      for (const document of vscode.workspace.textDocuments)
        if (document.languageId === "vir") void lifetime.refresh(document);
    }
    if (cfg.get<boolean>("ide.enableFallbackIntellisense", true)) {
      registerFallbackCompletion(fallbackContext);
      registerFallbackHover(fallbackContext);
      registerFallbackDiagnostics(fallbackContext);
      vscode.window.setStatusBarMessage("Virgori: fallback IDE providers active; configure vir.lsp.serverPath for LSP", 5000);
    }
  };
  context.subscriptions.push(vscode.commands.registerCommand("vir.restartLanguageServer", async () => {
    await connect(true);
    vscode.window.showInformationMessage("Virgori language server restarted.");
  }));
  await connect(false);
}

export async function deactivate(): Promise<void> {
  await stopVirLanguageClient();
}
