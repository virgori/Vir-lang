import * as vscode from "vscode";
import * as fs from "fs";
import * as path from "path";
import { LanguageClient, LanguageClientOptions, ServerOptions, TransportKind } from "vscode-languageclient/node";

let client: LanguageClient | undefined;

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
  const serverArgs = cfg.get<string[]>("lsp.serverArgs", []);

  if (!serverPath) {
    return undefined;
  }

  const serverOptions: ServerOptions = {
    command: serverPath,
    args: serverArgs.length > 0 ? serverArgs : ["--stdio"],
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
  await client.start();
  return client;
}

export async function restartVirLanguageClient(context: vscode.ExtensionContext): Promise<void> {
  if (client) {
    await client.stop();
    client = undefined;
  }
  await startVirLanguageClient(context);
}

export async function stopVirLanguageClient(): Promise<void> {
  if (client) {
    await client.stop();
    client = undefined;
  }
}
