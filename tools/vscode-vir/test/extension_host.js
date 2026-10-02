// Run with the installed VS Code extension host and the native LSP binary.
const assert = require('assert');
const vscode = require('vscode');
const fs = require('fs');
async function runContract() {
  const extension = vscode.extensions.getExtension('VirgoriLabs.vir-lang');
  assert(extension, 'Vir extension was not loaded');
  const serverPath = vscode.workspace.getConfiguration('vir').get('lsp.serverPath');
  assert.strictEqual(serverPath, process.env.VIR_LSP || '/tmp/vir-lsp-final', 'isolated test server configuration');
  await extension.activate();
  const folder = vscode.workspace.workspaceFolders[0].uri;
  const uri = vscode.Uri.joinPath(folder, 'host-contract.vri');
  const document = await vscode.workspace.openTextDocument(uri);
  assert.strictEqual(document.languageId, 'vir');
  const editor = await vscode.window.showTextDocument(document);
  const hover = await vscode.commands.executeCommand('vscode.executeHoverProvider', uri, new vscode.Position(1, 9));
  assert.strictEqual(hover.length, 1, 'native and fallback hover providers overlap');
  assert(hover[0].contents.some(content => content.value?.includes('Compiler resolver/type snapshot')), JSON.stringify(hover.map(h => ({ ...h, contents: h.contents.map(c => ({ names: Object.getOwnPropertyNames(c), type: typeof c, value: String(c.value), text: String(c) })) }))));
  const definitions = await vscode.commands.executeCommand('vscode.executeDefinitionProvider', uri, new vscode.Position(6, 11));
  assert.strictEqual(definitions.length, 1);
  assert.strictEqual((definitions[0].range ?? definitions[0].targetRange).start.line, 5);
  const rename = await vscode.commands.executeCommand('vscode.executeDocumentRenameProvider', uri, new vscode.Position(1, 9), 'firstValue');
  const edits = rename.get(uri);
  assert.deepStrictEqual(edits.map(edit => edit.range.start.line), [1, 2]);
  editor.selection = new vscode.Selection(2, 11, 2, 11);
  await vscode.commands.executeCommand('vir.showVariableLifetime');
  const change = new vscode.WorkspaceEdit();
  change.replace(uri, new vscode.Range(1, 16, 1, 17), '1.5');
  assert(await vscode.workspace.applyEdit(change));
  const unsaved = await vscode.commands.executeCommand('vscode.executeHoverProvider', uri, new vscode.Position(1, 9));
  assert.strictEqual(unsaved.length, 1);
  assert(unsaved[0].contents.some(content => content.value?.includes('`float`')), 'unsaved buffer type was not analyzed');
  await vscode.commands.executeCommand('vir.restartLanguageServer');
  const restarted = await vscode.commands.executeCommand('vscode.executeHoverProvider', uri, new vscode.Position(1, 9));
  assert.strictEqual(restarted.length, 1, 'providers overlap after restart');
  assert(restarted[0].contents.some(content => content.value?.includes('`float`')));
  await vscode.commands.executeCommand('vir.showVariableLifetime');
  await vscode.commands.executeCommand('workbench.action.files.revert');
  await vscode.commands.executeCommand('workbench.action.closeActiveEditor');
  console.log('PASS: real VS Code native hover/definition/rename, explicit focus, unsaved type, restart and provider isolation');
};

exports.run = async function () {
  const result = process.env.VIR_VSCODE_RESULT || '/tmp/vir-vscode-extension-host-result.json';
  try {
    await runContract();
    fs.writeFileSync(result, JSON.stringify({ passed: true }));
  } catch (error) {
    fs.writeFileSync(result, JSON.stringify({ passed: false, error: String(error), stack: error.stack }));
    throw error;
  }
};
