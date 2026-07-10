#!/usr/bin/env node
"use strict";

const fs = require("fs");
const os = require("os");
const path = require("path");
const { spawnSync } = require("child_process");

const root = path.resolve(__dirname, "..");
const skillName = "what-just-launched";
const skillSource = path.join(root, "skills", skillName);

function usage() {
  console.log(`What Just Launched

Usage:
  what-just-launched install [--agent codex|claude-code|cursor|opencode|shared|all]
  what-just-launched run <query> [script options...]
  what-just-launched doctor
  what-just-launched help

Examples:
  npx what-just-launched install
  npx what-just-launched install --agent claude-code
  npx what-just-launched run "new AI products" --mode discovery --days 7
`);
}

function parseOption(args, name, fallback) {
  const exact = `--${name}`;
  const prefix = `${exact}=`;
  for (let i = 0; i < args.length; i += 1) {
    const arg = args[i];
    if (arg === exact) return args[i + 1] || fallback;
    if (arg.startsWith(prefix)) return arg.slice(prefix.length);
  }
  return fallback;
}

function homePath(...parts) {
  return path.join(os.homedir(), ...parts);
}

function targetFor(agent) {
  const map = {
    codex: homePath(".codex", "skills"),
    "claude-code": homePath(".claude", "skills"),
    cursor: homePath(".cursor", "skills"),
    opencode: homePath(".opencode", "skills"),
    shared: homePath(".agents", "skills")
  };
  return map[agent];
}

function ensureInsideKnownTarget(target) {
  const allowed = [
    homePath(".codex", "skills"),
    homePath(".claude", "skills"),
    homePath(".cursor", "skills"),
    homePath(".opencode", "skills"),
    homePath(".agents", "skills")
  ].map((p) => path.resolve(p).toLowerCase());
  const resolved = path.resolve(target).toLowerCase();
  if (!allowed.includes(resolved)) {
    throw new Error(`Refusing to install outside known skill directories: ${target}`);
  }
}

function copyDir(src, dest) {
  if (!fs.existsSync(src)) {
    throw new Error(`Missing bundled skill directory: ${src}`);
  }
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  fs.rmSync(dest, { recursive: true, force: true });
  fs.cpSync(src, dest, { recursive: true });
}

function install(args) {
  const selected = parseOption(args, "agent", "codex");
  const agents = selected === "all"
    ? ["codex", "claude-code", "cursor", "opencode", "shared"]
    : selected.split(",").map((item) => item.trim()).filter(Boolean);

  for (const agent of agents) {
    const targetRoot = targetFor(agent);
    if (!targetRoot) {
      throw new Error(`Unknown agent "${agent}". Use codex, claude-code, cursor, opencode, shared, or all.`);
    }
    ensureInsideKnownTarget(targetRoot);
    const target = path.join(targetRoot, skillName);
    copyDir(skillSource, target);
    console.log(`Installed ${skillName} for ${agent}: ${target}`);
  }
}

function runPython(args) {
  const script = path.join(skillSource, "scripts", "just-launched.py");
  const candidates = process.platform === "win32" ? ["py", "python"] : ["python3", "python"];
  for (const exe of candidates) {
    const finalArgs = exe === "py" ? ["-3", script, ...args] : [script, ...args];
    const result = spawnSync(exe, finalArgs, { stdio: "inherit" });
    if (!result.error || result.error.code !== "ENOENT") {
      process.exit(result.status === null ? 1 : result.status);
    }
  }
  throw new Error("Python 3 was not found. Install Python 3 and try again.");
}

function main() {
  const [command = "help", ...args] = process.argv.slice(2);
  if (command === "help" || command === "--help" || command === "-h") {
    usage();
    return;
  }
  if (command === "install") {
    install(args);
    return;
  }
  if (command === "run") {
    runPython(args);
    return;
  }
  if (command === "doctor" || command === "diagnose") {
    runPython(["--diagnose"]);
    return;
  }
  throw new Error(`Unknown command "${command}". Run "what-just-launched help".`);
}

try {
  main();
} catch (error) {
  console.error(`Error: ${error.message}`);
  process.exit(1);
}
