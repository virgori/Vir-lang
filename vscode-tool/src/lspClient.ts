import * as vscode from "vscode";
import * as fs from "fs";
import * as path from "path";
import { LanguageClient, LanguageClientOptions, ServerOptions, TransportKind } from "vscode-languageclient/node";

import { NativeLifetimeRenderer } from "./nativeLifetimeRenderer";

let client: LanguageClient | undefined;
let renderer: NativeLifetimeRenderer | undefined;

function resolveServerPath(configuredPath: string): string | undefined {
  if (configuredPath && configuredPath.trim().length > 0) {
    return configuredPath.trim();
  }

  const workspaceFolders = vscode.workspace.workspaceFolders;
  if (workspaceFolders) {
    for (const folder of workspaceFolders) {
      const candidate = path.join(folder.uri.fsPath, "bin", "vir-lsp");
      if (fs.existsSync(candidate)) {
        return candidate;
      }
    }
  }

  return undefined;
}

export async function startVirLanguageClient(context: vscode.ExtensionContext): Promise<LanguageClient | undefined> {
  const cfg = vscode.workspace.getConfiguration("vir");
  const rawPath = cfg.get<string>("lsp.serverPath", "").trim();
  const serverPath = resolveServerPath(rawPath);
  const configuredArgs = cfg.get<string[]>("lsp.serverArgs", []);
  const serverArgs = configuredArgs.length > 0 ? [...configuredArgs] : ["--stdio"];

  if (!serverPath) {
    return undefined;
  }

  if (!serverArgs.includes("--stdlib-registry")) {
    const roots = [path.dirname(serverPath), ...(vscode.workspace.workspaceFolders ?? []).map(folder => folder.uri.fsPath)];
    let registry: string | undefined;
    for (const root of roots) {
      let directory = path.resolve(root);
      while (true) {
        const candidate = path.join(directory, "stdlib", "stdlib.vri");
        if (fs.existsSync(candidate)) { registry = candidate; break; }
        const parent = path.dirname(directory);
        if (parent === directory) break;
        directory = parent;
      }
      if (registry) break;
    }
    if (registry) serverArgs.push("--stdlib-registry", registry);
  }
  const serverOptions: ServerOptions = {
    command: serverPath,
    args: serverArgs,
    transport: TransportKind.stdio
  };

  const clientOptions: LanguageClientOptions = {
    documentSelector: [{ language: "vir", scheme: "file" }],
    synchronize: {
      fileEvents: vscode.workspace.createFileSystemWatcher("**/*.vri")
    },
    outputChannelName: "Vir Language Server"
  };

  client = new LanguageClient("vir-lsp", "Vir Language Server", serverOptions, clientOptions);
  try {
    await client.start();
  } catch (error) {
    const failedClient = client;
    client = undefined;
    try { await failedClient.dispose(); } catch { /* Startup already failed. */ }
    void vscode.window.showWarningMessage(`Vir language server could not start: ${String(error)}`);
    return undefined;
  }
  if (NativeLifetimeRenderer.supported(client) && cfg.get<boolean>("semantic.lifetime.enabled", true)) {
    renderer = new NativeLifetimeRenderer(client);
    context.subscriptions.push(renderer);
  }
  return client;
}

export async function restartVirLanguageClient(context: vscode.ExtensionContext): Promise<LanguageClient | undefined> {
  renderer?.dispose();
  renderer = undefined;
  if (client) {
    await client.stop();
    client = undefined;
  }
  return await startVirLanguageClient(context);
}

export async function stopVirLanguageClient(): Promise<void> {
  renderer?.dispose();
  renderer = undefined;
  if (client) {
    await client.stop();
    client = undefined;
  }
}
