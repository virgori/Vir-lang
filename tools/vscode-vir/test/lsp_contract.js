// Integration test between VS Code extension snapshotContract and native vir-lsp daemon.
const cp = require("child_process");
const path = require("path");
const assert = require("assert");
const { negotiateVirCapabilities, validateSnapshot } = require("../out/snapshotContract");

const repo = path.resolve(__dirname, "..", "..", "..");
const virLsp = process.env.VIR_LSP || path.join(repo, "bin", "vir-lsp");

function send(proc, payload) {
  const body = Buffer.from(JSON.stringify(payload), "utf8");
  const header = Buffer.from(`Content-Length: ${body.length}\r\n\r\n`, "ascii");
  proc.stdin.write(Buffer.concat([header, body]));
}

function createReader(proc) {
  let buf = Buffer.alloc(0);
  return function readNext() {
    return new Promise((resolve, reject) => {
      function pump() {
        const idx = buf.indexOf("\r\n\r\n");
        if (idx >= 0) {
          const header = buf.slice(0, idx).toString("ascii");
          let match = header.match(/content-length:\s*(\d+)/i);
          if (!match) return reject(new Error("No content-length in header: " + header));
          const len = parseInt(match[1], 10);
          const bodyStart = idx + 4;
          if (buf.length >= bodyStart + len) {
            const body = buf.slice(bodyStart, bodyStart + len);
            buf = buf.slice(bodyStart + len);
            return resolve(JSON.parse(body.toString("utf8")));
          }
        }
        const chunk = proc.stdout.read();
        if (chunk) {
          buf = Buffer.concat([buf, chunk]);
          pump();
        } else {
          proc.stdout.once("readable", pump);
        }
      }
      pump();
    });
  };
}

async function testLspContract() {
  const proc = cp.spawn(virLsp, ["--stdio"], { cwd: repo });
  const read = createReader(proc);

  try {
    // 1. initialize
    send(proc, {
      jsonrpc: "2.0",
      id: 1,
      method: "initialize",
      params: { processId: process.pid, rootUri: `file://${repo}`, capabilities: {} }
    });

    const initResp = await read();
    assert.strictEqual(initResp.id, 1);
    const caps = initResp.result.capabilities;

    // Negotiate capabilities using production VS Code contract
    const negotiated = negotiateVirCapabilities(caps);
    assert.ok(negotiated, "negotiateVirCapabilities failed to negotiate vir-lsp capabilities");
    assert.strictEqual(negotiated.schemaVersion, 1);
    assert.strictEqual(negotiated.semanticSnapshot, true);
    assert.strictEqual(negotiated.diagnosticSnapshot, true);
    assert.strictEqual(negotiated.focusLifetime, true);
    console.log("ok   negotiateVirCapabilities passed with 4.0.0 server");

    // 2. initialized
    send(proc, { jsonrpc: "2.0", method: "initialized", params: {} });

    // 3. didOpen
    const docUri = `file://${repo}/tests/contract_sample.vri`;
    const lines = [
      "func add(a: int, b: int) -> int:",
      "    out a + b",
      "end.",
      "",
      "func main():",
      "    let x = add(1, 2)",
      "end."
    ];
    const docText = lines.join("\n") + "\n";
    send(proc, {
      jsonrpc: "2.0",
      method: "textDocument/didOpen",
      params: {
        textDocument: { uri: docUri, languageId: "vir", version: 1, text: docText }
      }
    });

    // 4. vir/semanticSnapshot
    send(proc, {
      jsonrpc: "2.0",
      id: 2,
      method: "vir/semanticSnapshot",
      params: { textDocument: { uri: docUri } }
    });

    let snapResp = await read();
    while (snapResp && !snapResp.id) {
      // Skip notifications like publishDiagnostics
      snapResp = await read();
    }

    assert.strictEqual(snapResp.id, 2);
    const snap = snapResp.result;

    const docView = {
      uri: docUri,
      version: 1,
      lines: lines
    };

    const validated = validateSnapshot(snap, docView);
    assert.ok(validated, "validateSnapshot failed to validate vir-lsp semanticSnapshot");
    assert.strictEqual(validated.schemaVersion, 1);
    assert.strictEqual(validated.complete, true);
    assert.ok(validated.occurrences.length >= 2);
    assert.ok(validated.functions.length >= 2);
    console.log(`ok   validateSnapshot passed: ${validated.occurrences.length} occurrences, ${validated.functions.length} functions`);

    // 5. shutdown & exit
    send(proc, { jsonrpc: "2.0", id: 3, method: "shutdown", params: {} });
    const shutResp = await read();
    assert.strictEqual(shutResp.id, 3);

    send(proc, { jsonrpc: "2.0", method: "exit", params: {} });
    await new Promise((resolve) => proc.on("exit", resolve));
    assert.strictEqual(proc.exitCode, 0);
    console.log("ok   clean shutdown & exit (code 0)");
  } finally {
    if (proc.exitCode === null) {
      proc.kill();
    }
  }
}

testLspContract()
  .then(() => {
    console.log("\nAll LSP <-> VS Code contract tests passed!");
    process.exit(0);
  })
  .catch((err) => {
    console.error("FAIL:", err);
    process.exit(1);
  });
