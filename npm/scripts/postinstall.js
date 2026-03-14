#!/usr/bin/env node
/**
 * postinstall.js — Download the correct Vir native binary for this platform.
 *
 * Fetches the prebuilt binary from the GitHub release matching this npm
 * package version, extracts it, and places it next to the bin/ wrappers.
 */

"use strict";

const https = require("https");
const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");
const os = require("os");
const zlib = require("zlib");

const VERSION = require("../package.json").version;
const REPO = "virgori/vir";
const BIN_DIR = path.join(__dirname, "..", "bin");

/** Map Node.js platform/arch to the release artifact name. */
function getArtifactName() {
  const platform = os.platform();
  const arch = os.arch();

  const map = {
    "darwin-arm64": "vir-macos-arm64",
    "darwin-x64": "vir-macos-x86_64",
    "linux-x64": "vir-linux-x86_64",
    "linux-arm64": "vir-linux-arm64",
    "win32-x64": "vir-windows-x86_64",
    "win32-arm64": "vir-windows-arm64",
  };

  const key = `${platform}-${arch}`;
  const artifact = map[key];
  if (!artifact) {
    console.warn(
      `[vir-lang] No prebuilt binary for ${key}. Falling back to Python package.`
    );
    return null;
  }
  return artifact;
}

/** Follow redirects and return a Buffer. */
function download(url) {
  return new Promise((resolve, reject) => {
    const get = (u) => {
      https
        .get(u, { headers: { "User-Agent": "vir-lang-npm" } }, (res) => {
          if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
            get(res.headers.location);
            return;
          }
          if (res.statusCode !== 200) {
            reject(new Error(`HTTP ${res.statusCode} for ${u}`));
            return;
          }
          const chunks = [];
          res.on("data", (d) => chunks.push(d));
          res.on("end", () => resolve(Buffer.concat(chunks)));
          res.on("error", reject);
        })
        .on("error", reject);
    };
    get(url);
  });
}

/** Extract a .tar.gz buffer into targetDir. */
function extractTarGz(buffer, targetDir) {
  const tmpTar = path.join(os.tmpdir(), `vir-${Date.now()}.tar.gz`);
  fs.writeFileSync(tmpTar, buffer);
  fs.mkdirSync(targetDir, { recursive: true });
  try {
    execSync(`tar xzf "${tmpTar}" -C "${targetDir}"`, { stdio: "pipe" });
  } finally {
    fs.unlinkSync(tmpTar);
  }
}

async function main() {
  const artifact = getArtifactName();
  if (!artifact) {
    console.log("[vir-lang] Skipping binary download — use pip install vir-lang instead.");
    return;
  }

  const tag = `v${VERSION}`;
  const url = `https://github.com/${REPO}/releases/download/${tag}/${artifact}.tar.gz`;

  console.log(`[vir-lang] Downloading ${artifact} (${tag})...`);

  try {
    const buffer = await download(url);
    const nativeDir = path.join(BIN_DIR, "native");
    extractTarGz(buffer, nativeDir);

    // Make binary executable
    const virBin = path.join(nativeDir, os.platform() === "win32" ? "vir.exe" : "vir");
    if (fs.existsSync(virBin)) {
      fs.chmodSync(virBin, 0o755);
    }

    console.log(`[vir-lang] Installed native binary to ${nativeDir}`);
  } catch (err) {
    console.warn(`[vir-lang] Could not download binary: ${err.message}`);
    console.warn("[vir-lang] Falling back to Python-based CLI (requires python3 + pip install vir-lang).");
  }
}

main().catch((err) => {
  // Non-fatal — don't break npm install
  console.warn(`[vir-lang] postinstall warning: ${err.message}`);
  process.exit(0);
});
