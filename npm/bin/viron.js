#!/usr/bin/env node
/**
 * viron — Launcher for the Vir language server (viron).
 *
 * Priority:
 *   1. Python-based CLI (pip-installed vir-lang)
 *   2. Direct python3 module invocation
 */

"use strict";

const { execFileSync } = require("child_process");
const args = process.argv.slice(2);

function run() {
  for (const py of ["python3", "python"]) {
    try {
      execFileSync(py, ["-m", "src.viron.cli", ...args], {
        stdio: "inherit",
        env: process.env,
      });
      return true;
    } catch (err) {
      if (err.status !== undefined) {
        process.exit(err.status);
      }
    }
  }
  return false;
}

if (!run()) {
  console.error(
    "Error: Could not find Viron server.\n" +
      "Install via pip: pip install vir-lang"
  );
  process.exit(1);
}
