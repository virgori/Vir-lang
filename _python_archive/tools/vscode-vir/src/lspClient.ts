import * as vscode from "vscode";
import { LanguageClient, LanguageClientOptions, ServerOptions, TransportKind } from "vscode-languageclient/node";

let client: LanguageClient | undefined;

export async function startVirLanguageClient(context: vscode.ExtensionContext): Promise<LanguageClient | undefined> {
  const cfg = vscode.workspace.getConfiguration("vir");
  const serverPath = cfg.get<string>("lsp.serverPath", "").trim();
  const serverArgs = cfg.get<string[]>("lsp.serverArgs", []);

  if (!serverPath) {
    return undefined;
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
