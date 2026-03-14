#!/usr/bin/env node
/**
 * vir — Launcher for the Vir programming language CLI.
 *
 * Priority:
 *   1. Native binary (downloaded by postinstall)
 *   2. Python-based CLI (pip-installed vir-lang)
 */

"use strict";

const { execFileSync, execSync } = require("child_process");
const path = require("path");
const fs = require("fs");
const os = require("os");

const NATIVE_DIR = path.join(__dirname, "native");
const isWin = os.platform() === "win32";
const nativeBin = path.join(NATIVE_DIR, isWin ? "vir.exe" : "vir");
const args = process.argv.slice(2);

function runNative() {
  if (fs.existsSync(nativeBin)) {
    try {
      const result = execFileSync(nativeBin, args, {
        stdio: "inherit",
        env: process.env,
      });
      return true;
    } catch (err) {
      process.exit(err.status || 1);
    }
  }
  return false;
}

function runPython() {
  // Try python3 first, then python
  for (const py of ["python3", "python"]) {
    try {
      execFileSync(py, ["-m", "src.runtime.lifecycle", ...args], {
        stdio: "inherit",
        env: process.env,
      });
      return true;
    } catch (err) {
      if (err.status !== undefined) {
        // Command ran but exited with error
        process.exit(err.status);
      }
      // Command not found — try next
    }
  }
  return false;
}

if (!runNative() && !runPython()) {
  console.error(
    "Error: Could not find Vir runtime.\n" +
      "Install the native binary: npm rebuild vir-lang\n" +
      "Or install via pip:        pip install vir-lang"
  );
  process.exit(1);
}
