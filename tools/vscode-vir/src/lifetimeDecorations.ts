import * as vscode from "vscode";
import {
  IDE_STATE_ALIVE,
  IDE_STATE_DECLARED,
  IDE_STATE_INVALID,
  IDE_STATE_MOVED,
  IDE_STATE_OUT,
  IdeOccurrence,
  IdeSnapshot,
  fetchIdeSnapshot,
  invalidateIdeSnapshot
} from "./virIdeSemantic";

function rangeFromOcc(doc: vscode.TextDocument, occ: IdeOccurrence): vscode.Range {
  const start = new vscode.Position(Math.max(0, occ.line - 1), Math.max(0, occ.col - 1));
  const end = new vscode.Position(Math.max(0, occ.endLine - 1), Math.max(0, occ.endCol - 1));
  return new vscode.Range(start, end);
}

export class LifetimeDecorationController implements vscode.Disposable {
  private readonly types = {
    declared: vscode.window.createTextEditorDecorationType({
      opacity: "0.92",
      fontStyle: "italic"
    }),
    alive: vscode.window.createTextEditorDecorationType({}),
    moved: vscode.window.createTextEditorDecorationType({
      opacity: "0.72",
      textDecoration: "line-through"
    }),
    invalid: vscode.window.createTextEditorDecorationType({
      textDecoration: "underline wavy"
    }),
    outEscape: vscode.window.createTextEditorDecorationType({
      borderWidth: "0 0 1px 0",
      borderStyle: "dashed",
      opacity: "0.9"
    }),
    moduleUnresolved: vscode.window.createTextEditorDecorationType({
      textDecoration: "underline dotted"
    }),
    focusDim: vscode.window.createTextEditorDecorationType({
      opacity: "0.35"
    }),
    focusChain: vscode.window.createTextEditorDecorationType({
      borderWidth: "0 0 1px 0",
      borderStyle: "solid"
    })
  };

  private focusSymbolId: number | undefined;
  private debounceTimer: ReturnType<typeof setTimeout> | undefined;
  private disposables: vscode.Disposable[] = [];

  constructor() {
    this.disposables.push(
      vscode.workspace.onDidChangeTextDocument((e) => {
        if (e.document.languageId === "vir") {
          invalidateIdeSnapshot(e.document.uri);
          this.scheduleRefresh(e.document);
        }
      }),
      vscode.window.onDidChangeActiveTextEditor((ed) => {
        if (ed?.document.languageId === "vir") {
          this.scheduleRefresh(ed.document);
        }
      }),
      vscode.window.onDidChangeTextEditorSelection((e) => {
        if (e.textEditor.document.languageId !== "vir") {
          return;
        }
        if (!vscode.workspace.getConfiguration("vir").get<boolean>("semantic.lifetime.focusOnCursor", true)) {
          return;
        }
        this.updateFocusFromCursor(e.textEditor);
      }),
      vscode.commands.registerCommand("vir.showVariableLifetime", () => {
        const ed = vscode.window.activeTextEditor;
        if (ed?.document.languageId === "vir") {
          this.updateFocusFromCursor(ed);
          void this.refresh(ed.document);
        }
      })
    );
  }

  private scheduleRefresh(document: vscode.TextDocument): void {
    if (this.debounceTimer) {
      clearTimeout(this.debounceTimer);
    }
    const delay = vscode.workspace.getConfiguration("vir").get<number>("semantic.lifetime.debounceMs", 400);
    this.debounceTimer = setTimeout(() => {
      void this.refresh(document);
    }, delay);
  }

  private updateFocusFromCursor(editor: vscode.TextEditor): void {
    const pos = editor.selection.active;
    const word = editor.document.getWordRangeAtPosition(pos);
    if (!word) {
      this.focusSymbolId = undefined;
      return;
    }
    const name = editor.document.getText(word);
    const line = pos.line + 1;
    const col = pos.character + 1;
    const snap = this.lastSnapshot;
    if (!snap) {
      this.focusSymbolId = undefined;
      return;
    }
    const hit = snap.occurrences.find(
      (o) =>
        o.kind === 0 &&
        o.line === line &&
        col >= o.col &&
        col <= o.endCol &&
        editor.document.getText(rangeFromOcc(editor.document, o)) === name
    );
    this.focusSymbolId = hit?.symbolId && hit.symbolId > 0 ? hit.symbolId : undefined;
  }

  private lastSnapshot?: IdeSnapshot;

  async refresh(document: vscode.TextDocument): Promise<void> {
    const editor = vscode.window.visibleTextEditors.find((e) => e.document.uri.toString() === document.uri.toString());
    if (!editor || document.languageId !== "vir") {
      return;
    }

    const snapshot = await fetchIdeSnapshot(document);
    this.lastSnapshot = snapshot;
    if (!snapshot) {
      this.clear(editor);
      return;
    }

    const declared: vscode.DecorationOptions[] = [];
    const alive: vscode.DecorationOptions[] = [];
    const moved: vscode.DecorationOptions[] = [];
    const invalid: vscode.DecorationOptions[] = [];
    const outEscape: vscode.DecorationOptions[] = [];
    const focusDim: vscode.DecorationOptions[] = [];
    const focusChain: vscode.DecorationOptions[] = [];

    const focusId = this.focusSymbolId;
    const focusMode = focusId !== undefined && focusId > 0;

    for (const occ of snapshot.occurrences) {
      if (occ.kind !== 0) {
        continue;
      }
      const range = rangeFromOcc(document, occ);
      const opt: vscode.DecorationOptions = { range };
      if (focusMode) {
        if (occ.symbolId !== focusId) {
          focusDim.push(opt);
          continue;
        }
        focusChain.push(opt);
      }
      if (occ.state & IDE_STATE_INVALID) {
        invalid.push(opt);
      } else if (occ.state & IDE_STATE_OUT) {
        outEscape.push(opt);
      } else if (occ.state & IDE_STATE_MOVED) {
        moved.push(opt);
      } else if (occ.state & IDE_STATE_DECLARED) {
        declared.push(opt);
      } else if (occ.state & IDE_STATE_ALIVE) {
        alive.push(opt);
      }
    }

    // Active/inactive state of modules, functions, types, constants and imported symbols is
    // rendered as semantic-token colours (see semanticTokens.ts). Only unresolved modules keep
    // a decoration here, so the inactive colour is never applied to them.
    const moduleUnresolved: vscode.DecorationOptions[] = [];
    for (const mod of snapshot.symbols
      ? snapshot.symbols.filter((sy) => sy.kind === "module" && sy.state === "unresolved")
      : snapshot.modules.filter((m) => m.state === "unresolved")) {
      const line = Math.max(0, mod.line - 1);
      if (line >= document.lineCount) {
        continue;
      }
      const lineText = document.lineAt(line).text;
      const inc = lineText.match(/\binclude\s+([A-Za-z_][A-Za-z0-9_.]*)/);
      const startCol = inc?.index !== undefined ? inc.index + inc[0].indexOf(inc[1]) : Math.max(0, mod.col - 1);
      const endCol = inc ? startCol + inc[1].length : lineText.length;
      moduleUnresolved.push({ range: new vscode.Range(line, startCol, line, endCol) });
    }

    editor.setDecorations(this.types.declared, declared);
    editor.setDecorations(this.types.alive, alive);
    editor.setDecorations(this.types.moved, moved);
    editor.setDecorations(this.types.invalid, invalid);
    editor.setDecorations(this.types.outEscape, outEscape);
    editor.setDecorations(this.types.moduleUnresolved, moduleUnresolved);
    editor.setDecorations(this.types.focusDim, focusDim);
    editor.setDecorations(this.types.focusChain, focusChain);
  }

  private clear(editor: vscode.TextEditor): void {
    for (const t of Object.values(this.types)) {
      editor.setDecorations(t, []);
    }
  }

  dispose(): void {
    if (this.debounceTimer) {
      clearTimeout(this.debounceTimer);
    }
    for (const t of Object.values(this.types)) {
      t.dispose();
    }
    for (const d of this.disposables) {
      d.dispose();
    }
  }
}
