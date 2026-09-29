// Unit tests for the pure (vscode-free) modules. Run after `npm run compile`.
const assert = require("assert");
const fs = require("fs");
const path = require("path");
const { findBannerTitle } = require("../out/bannerTitle");
const { locateSymbol, normalizeSymbols, symbolTokenSpecs } = require("../out/symbolState");

let failures = 0;
function test(name, fn) {
  try {
    fn();
    console.log(`ok   ${name}`);
  } catch (e) {
    failures++;
    console.log(`FAIL ${name}\n     ${e.message}`);
  }
}

// ── banner title ────────────────────────────────────────────────
test("banner: title after leading blank line (sys.vri layout)", () => {
  const lines = ["", "##", " * src/core/sys.vri — Standard Library Syscall & OS Interface", " ##", "", "module x"];
  const t = findBannerTitle(lines);
  assert.deepStrictEqual(t, { line: 2, start: 3, length: "src/core/sys.vri — Standard Library Syscall & OS Interface".length });
});
test("banner: skips decorative rule lines", () => {
  const t = findBannerTitle(["##", " * ======", " * Title here", " ##"]);
  assert.strictEqual(t.line, 2);
});
test("banner: shebang then banner", () => {
  const t = findBannerTitle(["#!/usr/bin/env vir", "#*#", " * T", "#*#"]);
  assert.strictEqual(t.line, 2);
});
test("banner: inline title on opener line", () => {
  const t = findBannerTitle(["## My title", " * body", " ##"]);
  assert.deepStrictEqual(t, { line: 0, start: 3, length: "My title".length });
});
test("banner: no banner when code comes first", () => {
  assert.strictEqual(findBannerTitle(["var x: int", "##", " * T", "##"]), undefined);
});

// ── symbol location ─────────────────────────────────────────────
test("locate: import list picks the right name", () => {
  const line = "import sys_read, sys_write from core.sys";
  assert.deepStrictEqual(locateSymbol(line, { name: "sys_write", kind: "import", col: 0 }), { start: 17, length: 9 });
  assert.deepStrictEqual(locateSymbol(line, { name: "sys_read", kind: "import", col: 0 }), { start: 7, length: 8 });
});
test("locate: whole words only", () => {
  assert.strictEqual(locateSymbol("import sys_reader from x", { name: "sys_read", kind: "import", col: 0 }), undefined);
});
test("locate: function declaration, not `func` keyword or member access", () => {
  assert.deepStrictEqual(locateSymbol("func foo(a: int)", { name: "foo", kind: "function", col: 1 }), { start: 5, length: 3 });
  assert.strictEqual(locateSymbol("x = obj.foo()", { name: "foo", kind: "function", col: 0 }), undefined);
});
test("locate: dotted module name as a whole", () => {
  assert.deepStrictEqual(locateSymbol("include compiler.ide_semantic", { name: "compiler.ide_semantic", kind: "module", col: 0 }), {
    start: 8,
    length: 21
  });
});

// ── state → token mapping ───────────────────────────────────────
const maskedOf = (src) => (l) => src.split("\n")[l];
const SRC = "include math\nimport abs, max from math\nfunc main:";
test("state: unresolved symbols get NO token (never the inactive colour)", () => {
  const syms = normalizeSymbols([
    { name: "abs", kind: "import", line: 2, col: 0, state: "active" },
    { name: "max", kind: "import", line: 2, col: 0, state: "unresolved" }
  ]);
  const specs = symbolTokenSpecs(syms, maskedOf(SRC));
  assert.strictEqual(specs.length, 1);
  assert.strictEqual(specs[0].modifier, "active");
});
test("state: per-symbol state inside one import line", () => {
  const syms = normalizeSymbols([
    { name: "abs", kind: "import", line: 2, col: 0, state: "active" },
    { name: "max", kind: "import", line: 2, col: 0, state: "inactive" }
  ]);
  const specs = symbolTokenSpecs(syms, maskedOf(SRC));
  assert.deepStrictEqual(
    specs.map((s) => [s.start, s.length, s.tokenType, s.modifier]),
    [
      [7, 3, "importedSymbol", "active"],
      [12, 3, "importedSymbol", "inactive"]
    ]
  );
});
test("state: include/import/from keywords are never covered by a symbol token", () => {
  const syms = normalizeSymbols([
    { name: "math", kind: "module", line: 1, col: 0, state: "inactive" },
    { name: "abs", kind: "import", line: 2, col: 0, state: "active" }
  ]);
  const specs = symbolTokenSpecs(syms, maskedOf(SRC));
  for (const s of specs) {
    const text = SRC.split("\n")[s.line].substr(s.start, s.length);
    assert.ok(!["include", "import", "from"].includes(text), text);
  }
});
test("state: acceptance — deleting the last call flips active -> inactive and back", () => {
  const before = symbolTokenSpecs(normalizeSymbols([{ name: "sys_read", kind: "import", line: 1, col: 0, state: "active" }]), () => "import sys_read from core.sys");
  const after = symbolTokenSpecs(normalizeSymbols([{ name: "sys_read", kind: "import", line: 1, col: 0, state: "inactive" }]), () => "import sys_read from core.sys");
  const restored = symbolTokenSpecs(normalizeSymbols([{ name: "sys_read", kind: "import", line: 1, col: 0, state: "active" }]), () => "import sys_read from core.sys");
  assert.deepStrictEqual([before[0].modifier, after[0].modifier, restored[0].modifier], ["active", "inactive", "active"]);
});
test("state: malformed compiler entries are ignored, not guessed", () => {
  assert.deepStrictEqual(normalizeSymbols([{ name: 1 }, null, { name: "x", kind: "nope", line: 1 }, { name: "y", kind: "type" }]), []);
});

// ── theme colours ───────────────────────────────────────────────
const root = path.join(__dirname, "..");
const themeOf = (n) => JSON.parse(fs.readFileSync(path.join(root, "themes", `vir-${n}-color-theme.json`), "utf8"));
test("theme: dark themes use #FFB454 (active) / #92745F (inactive) for all five symbol kinds", () => {
  for (const n of ["quantum-dark", "matrix-neon", "forge-dark"]) {
    const sem = themeOf(n).semanticTokenColors;
    for (const kind of ["moduleName", "function", "type", "constant", "importedSymbol"]) {
      assert.strictEqual(sem[`${kind}.active`].toUpperCase(), "#FFB454", `${n} ${kind}.active`);
      assert.strictEqual(sem[`${kind}.inactive`].toUpperCase(), "#92745F", `${n} ${kind}.inactive`);
    }
  }
});
test("theme: `->` is Lime #BEF264 (dark) via both TextMate and semantic layers", () => {
  for (const n of ["quantum-dark", "matrix-neon", "forge-dark"]) {
    const t = themeOf(n);
    const rule = t.tokenColors.find((r) => [].concat(r.scope).includes("keyword.operator.arrow.vri"));
    assert.strictEqual(rule.settings.foreground.toUpperCase(), "#BEF264", n);
    const sem = t.semanticTokenColors.returnArrow;
    assert.strictEqual((sem.foreground || sem).toUpperCase(), "#BEF264", n);
  }
});
test("theme: banner palette #B5EDFF text / #67E8F9 decoration / #D6F6FF title", () => {
  for (const n of ["quantum-dark", "matrix-neon", "forge-dark"]) {
    const t = themeOf(n);
    const fg = (scope) => t.tokenColors.filter((r) => [].concat(r.scope).includes(scope)).pop().settings.foreground.toUpperCase();
    assert.strictEqual(fg("comment.block.banner.content.vri"), "#B5EDFF", n);
    assert.strictEqual(fg("punctuation.definition.comment.banner.vri"), "#67E8F9", n);
    assert.strictEqual(fg("comment.block.banner.rule.vri"), "#67E8F9", n);
    assert.strictEqual(t.semanticTokenColors.bannerTitle.foreground.toUpperCase(), "#D6F6FF", n);
  }
});
test("theme: keyword colours (include/import/from) are untouched by symbol state", () => {
  for (const n of ["quantum-dark", "matrix-neon", "forge-dark", "quantum-light"]) {
    const sem = themeOf(n).semanticTokenColors;
    for (const k of Object.keys(sem)) {
      assert.ok(!/^(importKeyword|includeKeyword|keyword)\.(active|inactive)$/.test(k), `${n}: ${k}`);
    }
  }
});

if (failures) {
  console.log(`\n${failures} test(s) failed`);
  process.exit(1);
}
console.log("\nall unit tests passed");
