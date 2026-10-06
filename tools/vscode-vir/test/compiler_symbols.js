// Compiler-backed tests: run `virc --ide-semantic --json` on each fixture and check the
// per-symbol state against the `# expect <kind> <name> <state>` header lines.
//
//   node test/compiler_symbols.js [--strict]
//
// VIRC=/path/to/virc overrides the compiler. Without --strict, a compiler that predates
// `--ide-semantic` (or `ide.symbols`) is reported as SKIP instead of failing.
const cp = require("child_process");
const fs = require("fs");
const path = require("path");

const strict = process.argv.includes("--strict");
const repo = path.resolve(__dirname, "..", "..", "..");
const virc = process.env.VIRC || [path.join(repo, "dist", "virc-next"), path.join(repo, "bin", "virc")].find((p) => fs.existsSync(p));
const dir = path.join(__dirname, "fixtures");

if (!virc) {
  console.log("SKIP no virc binary found");
  process.exit(strict ? 1 : 0);
}

function snapshot(file) {
  const r = cp.spawnSync(virc, ["--ide-semantic", "--json", file], { cwd: repo, encoding: "utf8", timeout: 120000, maxBuffer: 64 << 20 });
  const lines = (r.stdout || "").split("\n").map((l) => l.trim()).filter((l) => l.startsWith("{"));
  for (let i = lines.length - 1; i >= 0; i--) {
    try {
      const j = JSON.parse(lines[i]);
      if (j.ide) return j.ide;
    } catch {}
  }
  return undefined;
}

let failed = 0;
let skipped = 0;
for (const f of fs.readdirSync(dir).filter((n) => n.endsWith(".vri")).sort()) {
  const file = path.join(dir, f);
  const expects = fs
    .readFileSync(file, "utf8")
    .split("\n")
    .map((l) => l.match(/^#\s*expect\s+(\w+)\s+(\S+)\s+(active|inactive|unresolved)\s*$/))
    .filter(Boolean)
    .map((m) => ({ kind: m[1], name: m[2], state: m[3] }));
  const ide = snapshot(file);
  if (!ide || !Array.isArray(ide.symbols)) {
    skipped++;
    console.log(`SKIP ${f}: compiler emitted no ide.symbols (${virc})`);
    continue;
  }
  for (const e of expects) {
    const hit = ide.symbols.find((s) => s.kind === e.kind && s.name === e.name);
    const got = hit ? hit.state : "(missing)";
    const ok = got === e.state;
    if (!ok) failed++;
    console.log(`${ok ? "ok  " : "FAIL"} ${f}: ${e.kind} ${e.name} expected ${e.state}, got ${got}`);
  }
}
if (failed || (strict && skipped)) {
  process.exit(1);
}
console.log(skipped ? `\n${skipped} fixture(s) skipped (compiler has no ide.symbols yet)` : "\nall compiler symbol tests passed");
