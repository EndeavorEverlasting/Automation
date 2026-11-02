"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const os = require("node:os");
const { spawnBackground, decision, CONTRACT } = require("../adapters/node/silent_background.cjs");

function temporary(fn) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "silent-background-"));
  try { return fn(dir); } finally { fs.rmSync(dir, { recursive: true, force: true }); }
}
test("Node adapter defers browsers/installers and never starts a child", () => temporary((dir) => {
  for (const exe of ["chrome.exe", "winget.exe", "msiexec.exe", "cmd.exe"]) {
    const result = spawnBackground(exe, ["--any"], { jobId: "test", receiptDir: dir });
    assert.equal(result.status, "DEFERRED_INTERACTION");
    assert.equal(result.child, null);
    assert.equal(JSON.parse(fs.readFileSync(result.receiptPath)).status, "DEFERRED_INTERACTION");
  }
}));
test("Node adapter refuses shell:true and unknown executables", () => temporary((dir) => {
  assert.throws(() => spawnBackground("node", [], { jobId: "test", receiptDir: dir, shell: true }), /shell/);
  const x = spawnBackground("unknown.exe", [], { jobId: "test", receiptDir: dir });
  assert.equal(x.status, "DEFERRED_INTERACTION");
  assert.equal(decision("unknown.exe", [], []), "EXECUTABLE_NOT_ADMITTED");
}));
test("Node spawn writes lifecycle receipts separately from silence certification", async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "silent-background-"));
  try {
    const x = spawnBackground(process.execPath, ["-e", "process.exit(2)"],
       { jobId: "tick", receiptDir: dir });
    assert.equal(x.status, "SPAWNED_NOT_CERTIFIED");
    assert.ok(x.child);
    await new Promise((resolve, reject) => {
      x.child.once("exit", resolve);
      x.child.once("error", reject);
    });
    const receipt = JSON.parse(fs.readFileSync(x.receiptPath, "utf8"));
    assert.equal(receipt.schema, CONTRACT);
    assert.equal(receipt.status, "NONZERO");
    assert.equal(receipt.returncode, 2);
    assert.match(receipt.proof_ceiling, /NOT_DESCENDANT_OR_FULLSCREEN_CERTIFIED/);
    assert.equal(receipt.mutated_scheduler, false);
  } finally { fs.rmSync(dir, { recursive: true, force: true }); }
});
test("Node adapter requires safe identifiers", () => temporary((dir) => {
  assert.throws(() => spawnBackground("node", [], { jobId: "../escape", receiptDir: dir }), /jobId/);
}));
test("Node Powershell policy requires noninteractive mode", () => {
  assert.equal(decision("pwsh.exe", ["-File", "tick.ps1"]), "POWERSHELL_REQUIRES_NONINTERACTIVE");
  assert.equal(decision("pwsh.exe", ["-NonInteractive", "-NoProfile", "-Command", "Read-Host"]), "POWERSHELL_INTERACTIVE_ACTION");
  assert.equal(decision("pwsh.exe", ["-NonInteractive", "-NoProfile", "-File", "tick.ps1"]), null);
});


test("Node receipt path failure blocks unattended launch before spawning", () => temporary((dir) => {
  const notDirectory = path.join(dir, "regular-file");
  fs.writeFileSync(notDirectory, "not-a-directory");
  assert.throws(() => spawnBackground(process.execPath, ["-e", "process.exit(0)"],
    { jobId: "tick", receiptDir: notDirectory }), /ENOTDIR|EEXIST/);
}));
test("Intentional interactive launch keeps inherited stdio and does not require receipts", async () => temporary(async (dir) => {
  const notDirectory = path.join(dir, "regular-file");
  fs.writeFileSync(notDirectory, "not-a-directory");
  const p = spawnBackground(process.execPath, ["-e", "process.exit(0)"],
    { jobId: "manual", receiptDir: notDirectory, executionClass: "INTERACTIVE" });
  assert.equal(p.receiptPath, null);
  assert.ok(p.child);
  await new Promise((resolve, reject) => {
    p.child.once("exit", resolve);
    p.child.once("error", reject);
  });
}));
