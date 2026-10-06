import * as vscode from "vscode";
import * as cp from "child_process";
import * as fs from "fs";
import * as path from "path";
import { promisify } from "util";
import { normalizeSymbols, type IdeSymbol } from "./symbolState";

const execFile = promisify(cp.execFile);

export const IDE_STATE_DECLARED = 1;
export const IDE_STATE_ALIVE = 2;
export const IDE_STATE_MOVED = 4;
export const IDE_STATE_INVALID = 16;
export const IDE_STATE_OUT = 8;

export interface IdeOccurrence {
  symbolId: number;
  line: number;
  col: number;
  endLine: number;
  endCol: number;
  kind: number;
  state: number;
}

export interface IdeModuleState {
  name: string;
  line: number;
  col: number;
  state: "active" | "inactive" | "unresolved";
}

export interface IdeFunctionState {
  name: string;
  line: number;
  col: number;
  endCol: number;
  symbolId: number;
  state: "active" | "inactive";
}

export interface IdeShapeDimension {
  line: number;
  value: number;
  state: number;
  col?: number;
  endCol?: number;
}

export interface IdeSnapshot {
  schemaVersion: number;
  occurrences: IdeOccurrence[];
  modules: IdeModuleState[];
  functions: IdeFunctionState[];
  shapeDimensions: IdeShapeDimension[];
  /** Unified compiler-resolved symbol states; undefined for compilers that predate it. */
  symbols?: IdeSymbol[];
}

function resolveVirc(): string | undefined {
  const cfg = vscode.workspace.getConfiguration("vir");
  const configured = cfg.get<string>("compiler.path", "").trim();
  if (configured && fs.existsSync(configured)) {
    return configured;
  }
  const folders = vscode.workspace.workspaceFolders;
  if (folders) {
    for (const f of folders) {
      const candidate = path.join(f.uri.fsPath, "bin", "virc");
      if (fs.existsSync(candidate)) {
        return candidate;
      }
    }
  }
  return undefined;
}

function parseJsonLine(stdout: string): IdeSnapshot | undefined {
  const lines = stdout.split("\n").map((l) => l.trim()).filter(Boolean);
  for (let i = lines.length - 1; i >= 0; i--) {
    const line = lines[i];
    if (!line.startsWith("{")) {
      continue;
    }
    try {
      const root = JSON.parse(line) as {
        schema_version?: number;
        ide?: {
          occurrences?: IdeOccurrence[];
          modules?: Array<{ name: string; line: number; col: number; state: string }>;
          functions?: Array<{
            name: string;
            line: number;
            col: number;
            endCol: number;
            symbolId: number;
            state: string;
          }>;
          shapeDimensions?: Array<{
            line: number;
            value: number;
            state: number;
            col?: number;
            endCol?: number;
          }>;
          symbols?: unknown;
        };
      };
      if (!root.ide) {
        return undefined;
      }
      const modules: IdeModuleState[] = (root.ide.modules ?? []).map((m) => ({
        name: m.name,
        line: m.line,
        col: m.col,
        state: m.state === "active" || m.state === "unresolved" ? m.state : "inactive"
      }));
      const functions: IdeFunctionState[] = (root.ide.functions ?? []).map((f) => ({
        name: f.name,
        line: f.line,
        col: f.col,
        endCol: f.endCol,
        symbolId: f.symbolId,
        state: f.state === "active" ? "active" : "inactive"
      }));
      const shapeDimensions: IdeShapeDimension[] = (root.ide.shapeDimensions ?? []).map((s) => ({
        line: s.line,
        value: s.value,
        state: s.state ?? 0,
        col: s.col,
        endCol: s.endCol
      }));
      return {
        schemaVersion: root.schema_version ?? 1,
        occurrences: root.ide.occurrences ?? [],
        modules,
        functions,
        shapeDimensions,
        symbols: root.ide.symbols === undefined ? undefined : normalizeSymbols(root.ide.symbols)
      };
    } catch {
      continue;
    }
  }
  return undefined;
}

interface CacheEntry {
  version: number;
  snapshot?: IdeSnapshot;
  pending?: Promise<IdeSnapshot | undefined>;
  abort?: AbortController;
}

/** One entry per document: snapshots are cached by document version. */
const cache = new Map<string, CacheEntry>();

function wantsSnapshot(force?: boolean): boolean {
  const cfg = vscode.workspace.getConfiguration("vir");
  const wantLifetime = cfg.get<boolean>("semantic.lifetime.enabled", true);
  const wantSymbols = cfg.get<boolean>("semantic.symbolState.enabled", true);
  const wantShape =
    cfg.get<boolean>("semantic.shape.compilerBacked", true) &&
    cfg.get<boolean>("semantic.enableEnhanced", true);
  return Boolean(force) || wantLifetime || wantSymbols || wantShape;
}

/**
 * Fetch the compiler's IDE snapshot for a document.
 *
 * - Cached by document version; concurrent callers for the same version share one process.
 * - A request for a newer version aborts the stale compiler process.
 * - A cancelled *caller* (token) stops waiting; the shared request keeps going only if it
 *   is still for the current version, so the result is ready for the next request.
 */
export async function fetchIdeSnapshot(
  document: vscode.TextDocument,
  options?: { force?: boolean; token?: vscode.CancellationToken }
): Promise<IdeSnapshot | undefined> {
  if (!wantsSnapshot(options?.force)) {
    return undefined;
  }
  const virc = resolveVirc();
  if (!virc) {
    return undefined;
  }

  const key = document.uri.toString();
  const version = document.version;
  const entry = cache.get(key);

  if (!options?.force && entry && entry.version === version) {
    if (entry.snapshot) {
      return entry.snapshot;
    }
    if (entry.pending) {
      return raceCancellation(entry.pending, options?.token);
    }
  }

  // Stale in-flight request for an older version: abort its compiler process.
  entry?.abort?.abort();

  const abort = new AbortController();
  const pending = (async (): Promise<IdeSnapshot | undefined> => {
    let stdout = "";
    try {
      const result = await execFile(virc, ["--ide-semantic", "--json", document.uri.fsPath], {
        cwd: path.dirname(document.uri.fsPath),
        maxBuffer: 16 * 1024 * 1024,
        timeout: 120_000,
        signal: abort.signal
      });
      stdout = result.stdout;
    } catch (err: unknown) {
      const e = err as { stdout?: string; name?: string; code?: string };
      if (e.name === "AbortError" || e.code === "ABORT_ERR" || abort.signal.aborted) {
        return undefined;
      }
      if (!e.stdout) {
        return undefined;
      }
      stdout = e.stdout;
    }
    if (abort.signal.aborted) {
      return undefined;
    }
    return parseJsonLine(stdout);
  })();

  const mine: CacheEntry = { version, pending, abort };
  cache.set(key, mine);
  void pending.then((snapshot) => {
    // Only publish if nothing newer replaced this entry meanwhile.
    if (cache.get(key) === mine && !abort.signal.aborted) {
      cache.set(key, { version, snapshot });
    }
  });
  return raceCancellation(pending, options?.token);
}

function raceCancellation<T>(promise: Promise<T>, token?: vscode.CancellationToken): Promise<T | undefined> {
  if (!token) {
    return promise;
  }
  if (token.isCancellationRequested) {
    return Promise.resolve(undefined);
  }
  return new Promise<T | undefined>((resolve, reject) => {
    const sub = token.onCancellationRequested(() => {
      sub.dispose();
      resolve(undefined);
    });
    promise.then(
      (v) => {
        sub.dispose();
        resolve(v);
      },
      (e) => {
        sub.dispose();
        reject(e);
      }
    );
  });
}

export function invalidateIdeSnapshot(uri: vscode.Uri): void {
  const key = uri.toString();
  cache.get(key)?.abort?.abort();
  cache.delete(key);
}
