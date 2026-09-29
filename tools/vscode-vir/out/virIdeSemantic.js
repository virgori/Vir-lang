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
exports.IDE_STATE_OUT = exports.IDE_STATE_INVALID = exports.IDE_STATE_MOVED = exports.IDE_STATE_ALIVE = exports.IDE_STATE_DECLARED = void 0;
exports.fetchIdeSnapshot = fetchIdeSnapshot;
exports.invalidateIdeSnapshot = invalidateIdeSnapshot;
const vscode = __importStar(require("vscode"));
const cp = __importStar(require("child_process"));
const fs = __importStar(require("fs"));
const path = __importStar(require("path"));
const util_1 = require("util");
const symbolState_1 = require("./symbolState");
const execFile = (0, util_1.promisify)(cp.execFile);
exports.IDE_STATE_DECLARED = 1;
exports.IDE_STATE_ALIVE = 2;
exports.IDE_STATE_MOVED = 4;
exports.IDE_STATE_INVALID = 16;
exports.IDE_STATE_OUT = 8;
function resolveVirc() {
    const cfg = vscode.workspace.getConfiguration("vir");
    const configured = cfg.get("compiler.path", "").trim();
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
function parseJsonLine(stdout) {
    const lines = stdout.split("\n").map((l) => l.trim()).filter(Boolean);
    for (let i = lines.length - 1; i >= 0; i--) {
        const line = lines[i];
        if (!line.startsWith("{")) {
            continue;
        }
        try {
            const root = JSON.parse(line);
            if (!root.ide) {
                return undefined;
            }
            const modules = (root.ide.modules ?? []).map((m) => ({
                name: m.name,
                line: m.line,
                col: m.col,
                state: m.state === "active" || m.state === "unresolved" ? m.state : "inactive"
            }));
            const functions = (root.ide.functions ?? []).map((f) => ({
                name: f.name,
                line: f.line,
                col: f.col,
                endCol: f.endCol,
                symbolId: f.symbolId,
                state: f.state === "active" ? "active" : "inactive"
            }));
            const shapeDimensions = (root.ide.shapeDimensions ?? []).map((s) => ({
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
                symbols: root.ide.symbols === undefined ? undefined : (0, symbolState_1.normalizeSymbols)(root.ide.symbols)
            };
        }
        catch {
            continue;
        }
    }
    return undefined;
}
/** One entry per document: snapshots are cached by document version. */
const cache = new Map();
function wantsSnapshot(force) {
    const cfg = vscode.workspace.getConfiguration("vir");
    const wantLifetime = cfg.get("semantic.lifetime.enabled", true);
    const wantSymbols = cfg.get("semantic.symbolState.enabled", true);
    const wantShape = cfg.get("semantic.shape.compilerBacked", true) &&
        cfg.get("semantic.enableEnhanced", true);
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
async function fetchIdeSnapshot(document, options) {
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
    const pending = (async () => {
        let stdout = "";
        try {
            const result = await execFile(virc, ["--ide-semantic", "--json", document.uri.fsPath], {
                cwd: path.dirname(document.uri.fsPath),
                maxBuffer: 16 * 1024 * 1024,
                timeout: 120_000,
                signal: abort.signal
            });
            stdout = result.stdout;
        }
        catch (err) {
            const e = err;
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
    const mine = { version, pending, abort };
    cache.set(key, mine);
    void pending.then((snapshot) => {
        // Only publish if nothing newer replaced this entry meanwhile.
        if (cache.get(key) === mine && !abort.signal.aborted) {
            cache.set(key, { version, snapshot });
        }
    });
    return raceCancellation(pending, options?.token);
}
function raceCancellation(promise, token) {
    if (!token) {
        return promise;
    }
    if (token.isCancellationRequested) {
        return Promise.resolve(undefined);
    }
    return new Promise((resolve, reject) => {
        const sub = token.onCancellationRequested(() => {
            sub.dispose();
            resolve(undefined);
        });
        promise.then((v) => {
            sub.dispose();
            resolve(v);
        }, (e) => {
            sub.dispose();
            reject(e);
        });
    });
}
function invalidateIdeSnapshot(uri) {
    const key = uri.toString();
    cache.get(key)?.abort?.abort();
    cache.delete(key);
}
//# sourceMappingURL=virIdeSemantic.js.map