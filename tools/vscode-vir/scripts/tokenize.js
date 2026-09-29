const fs = require("fs");
const path = require("path");
const oniguruma = require("vscode-oniguruma");
const textmate = require("vscode-textmate");

const root = path.join(__dirname, "..");
const wasmBin = fs.readFileSync(require.resolve("vscode-oniguruma/release/onig.wasm")).buffer;

const vscodeOnigurumaLib = oniguruma.loadWASM(wasmBin).then(() => ({
  createOnigScanner: (patterns) => new oniguruma.OnigScanner(patterns),
  createOnigString: (s) => new oniguruma.OnigString(s)
}));

const registry = new textmate.Registry({
  onigLib: vscodeOnigurumaLib,
  loadGrammar: () => {
    const raw = fs.readFileSync(process.env.GRAMMAR || path.join(root, "syntaxes", "vir.tmLanguage.json"), "utf8");
    return Promise.resolve(textmate.parseRawGrammar(raw, "vir.tmLanguage.json"));
  }
});

const sample = fs.readFileSync(process.argv[2], "utf8");

registry.loadGrammar("source.vri").then((grammar) => {
  let ruleStack = textmate.INITIAL;
  sample.split("\n").forEach((line, i) => {
    const res = grammar.tokenizeLine(line, ruleStack);
    console.log(`\n${String(i + 1).padStart(3)} | ${line}`);
    for (const t of res.tokens) {
      const text = line.substring(t.startIndex, t.endIndex);
      if (!text.trim()) continue;
      console.log(`      ${JSON.stringify(text).padEnd(14)} ${t.scopes.join(" ")}`);
    }
    ruleStack = res.ruleStack;
  });
});
