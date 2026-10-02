import * as vscode from "vscode";
import { LanguageClient } from "vscode-languageclient/node";
import { contains, DocumentView, negotiateVirCapabilities, SemanticSnapshot, validateSnapshot } from "./snapshotContract";

/** Render compiler ranges and IDs only; this controller performs no source analysis. */
export class NativeLifetimeRenderer implements vscode.Disposable {
  private readonly decorations = {
    moved: vscode.window.createTextEditorDecorationType({ opacity: "0.72", textDecoration: "line-through" }),
    invalid: vscode.window.createTextEditorDecorationType({ textDecoration: "underline wavy" }),
    borrowed: vscode.window.createTextEditorDecorationType({ borderWidth: "0 0 1px 0", borderStyle: "dashed" }),
    lastUse: vscode.window.createTextEditorDecorationType({ borderWidth: "0 0 1px 0", borderStyle: "solid" }),
    focus: vscode.window.createTextEditorDecorationType({ borderWidth: "0 0 2px 0", borderStyle: "solid" })
  };
  private readonly subscriptions: vscode.Disposable[] = [];
  private readonly requests = new Map<string, vscode.CancellationTokenSource>();
  private readonly timers = new Map<string, ReturnType<typeof setTimeout>>();
  private readonly snapshots = new Map<string, SemanticSnapshot>();
  private generation = 0;
  private disposed = false;

  constructor(private readonly client: LanguageClient) {
    this.subscriptions.push(
      vscode.workspace.onDidChangeTextDocument(() => this.invalidate()),
      vscode.workspace.onDidCloseTextDocument(() => this.invalidate()),
      vscode.window.onDidChangeActiveTextEditor(editor => {
        if (editor?.document.languageId === "vir") this.schedule(editor.document);
      }),
      vscode.window.onDidChangeVisibleTextEditors(editors => {
        for (const editor of editors) this.schedule(editor.document);
      }),
      vscode.commands.registerCommand("vir.showVariableLifetime", async () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor || editor.document.languageId !== "vir") return;
        const uri = editor.document.uri.toString();
        if (!this.snapshots.has(uri)) await this.refresh(editor.document);
        const snapshot = this.snapshots.get(uri);
        const position = editor.selection.active;
        const occurrence = snapshot?.occurrences.find(o =>
          (o.uri ?? snapshot.uri) === uri && contains(o.range, position));
        if (snapshot?.complete && occurrence) await this.refresh(editor.document, occurrence.symbolId);
      })
    );
    for (const editor of vscode.window.visibleTextEditors) this.schedule(editor.document);
  }

  static supported(client: LanguageClient): boolean {
    return !!negotiateVirCapabilities(client.initializeResult?.capabilities);
  }

  private view(document: vscode.TextDocument): DocumentView {
    return { uri: document.uri.toString(), version: document.version,
      lines: Array.from({ length: document.lineCount }, (_, line) => document.lineAt(line).text) };
  }

  private clear(): void {
    for (const editor of vscode.window.visibleTextEditors) {
      if (editor.document.languageId !== "vir") continue;
      for (const decoration of Object.values(this.decorations)) editor.setDecorations(decoration, []);
    }
  }

  private invalidate(): void {
    this.generation++;
    for (const request of this.requests.values()) { request.cancel(); request.dispose(); }
    this.requests.clear();
    this.snapshots.clear();
    this.clear();
    for (const editor of vscode.window.visibleTextEditors) this.schedule(editor.document);
  }

  private schedule(document: vscode.TextDocument): void {
    if (this.disposed || document.languageId !== "vir" || document.uri.scheme !== "file") return;
    const uri = document.uri.toString();
    const previous = this.timers.get(uri);
    if (previous) clearTimeout(previous);
    this.timers.set(uri, setTimeout(() => {
      this.timers.delete(uri);
      void this.refresh(document);
    }, vscode.workspace.getConfiguration("vir").get<number>("semantic.lifetime.debounceMs", 400)));
  }

  private async refresh(document: vscode.TextDocument, focusSymbolId?: string): Promise<void> {
    if (this.disposed || document.isClosed) return;
    const uri = document.uri.toString(), version = document.version, generation = this.generation;
    const previous = this.requests.get(uri);
    if (previous) { previous.cancel(); previous.dispose(); }
    const request = new vscode.CancellationTokenSource();
    this.requests.set(uri, request);
    try {
      const value = await this.client.sendRequest<unknown>("vir/semanticSnapshot", {
        uri, textDocument: { uri }, version,
        mode: focusSymbolId === undefined ? "full" : "focus", focusSymbolId
      }, request.token);
      if (this.disposed || request.token.isCancellationRequested || document.isClosed ||
          document.version !== version || this.generation !== generation) return;
      const snapshot = validateSnapshot(value, this.view(document),
        vscode.workspace.textDocuments.filter(d => d.languageId === "vir").map(d => this.view(d)));
      if (!snapshot) { this.clear(); return; }
      this.snapshots.set(uri, snapshot);
      const groups: Record<keyof typeof this.decorations, vscode.Range[]> =
        { moved: [], invalid: [], borrowed: [], lastUse: [], focus: [] };
      for (const occurrence of snapshot.occurrences) {
        if ((occurrence.uri ?? snapshot.uri) !== uri) continue;
        const a = occurrence.range.start, b = occurrence.range.end;
        const range = new vscode.Range(a.line, a.character, b.line, b.character);
        if (occurrence.states.includes("virMoved")) groups.moved.push(range);
        if (occurrence.states.includes("virInvalid")) groups.invalid.push(range);
        if (occurrence.states.includes("virBorrowed")) groups.borrowed.push(range);
        if (occurrence.states.includes("virLastUse")) groups.lastUse.push(range);
      }
      if (snapshot.complete && snapshot.focus && snapshot.focus.symbolId === focusSymbolId) {
        for (const occurrence of snapshot.focus.path) {
          if ((occurrence.uri ?? snapshot.uri) !== uri) continue;
          const a = occurrence.range.start, b = occurrence.range.end;
          groups.focus.push(new vscode.Range(a.line, a.character, b.line, b.character));
        }
      }
      for (const editor of vscode.window.visibleTextEditors) {
        if (editor.document.uri.toString() !== uri) continue;
        for (const key of Object.keys(this.decorations) as Array<keyof typeof this.decorations>)
          editor.setDecorations(this.decorations[key], groups[key]);
      }
    } catch {
      if (this.generation === generation && !request.token.isCancellationRequested) this.clear();
    } finally {
      if (this.requests.get(uri) === request) this.requests.delete(uri);
      request.dispose();
    }
  }

  dispose(): void {
    if (this.disposed) return;
    this.disposed = true;
    this.generation++;
    this.clear();
    for (const timer of this.timers.values()) clearTimeout(timer);
    for (const request of this.requests.values()) { request.cancel(); request.dispose(); }
    for (const subscription of this.subscriptions) subscription.dispose();
    for (const decoration of Object.values(this.decorations)) decoration.dispose();
    this.timers.clear(); this.requests.clear(); this.snapshots.clear();
  }
}
