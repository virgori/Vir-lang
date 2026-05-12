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
exports.startVirLanguageClient = startVirLanguageClient;
exports.restartVirLanguageClient = restartVirLanguageClient;
exports.stopVirLanguageClient = stopVirLanguageClient;
const vscode = __importStar(require("vscode"));
const node_1 = require("vscode-languageclient/node");
let client;
async function startVirLanguageClient(context) {
    const cfg = vscode.workspace.getConfiguration("vir");
    const serverPath = cfg.get("lsp.serverPath", "").trim();
    const serverArgs = cfg.get("lsp.serverArgs", []);
    if (!serverPath) {
        return undefined;
    }
    const serverOptions = {
        command: serverPath,
        args: serverArgs,
        transport: node_1.TransportKind.stdio
    };
    const clientOptions = {
        documentSelector: [{ language: "vir", scheme: "file" }],
        synchronize: {
            fileEvents: vscode.workspace.createFileSystemWatcher("**/*.vri")
        },
        outputChannelName: "Vir Language Server"
    };
    client = new node_1.LanguageClient("vir-lsp", "Vir Language Server", serverOptions, clientOptions);
    await client.start();
    return client;
}
async function restartVirLanguageClient(context) {
    if (client) {
        await client.stop();
        client = undefined;
    }
    await startVirLanguageClient(context);
}
async function stopVirLanguageClient() {
    if (client) {
        await client.stop();
        client = undefined;
    }
}
//# sourceMappingURL=lspClient.js.map