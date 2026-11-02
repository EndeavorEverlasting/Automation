"use strict";
/** Opt-in Node adapter for automation.silent-background/v1.
 *  Task Scheduler / timers remain consumer-owned. No GUI suppression is promised
 *  for grandchildren that bypass this API; launch receipt != live certification.
 */
const { spawn } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");
const os = require("node:os");
const crypto = require("node:crypto");

const CONTRACT = "automation.silent-background/v1";
const ALLOWED = new Set(["node.exe", "node", "pythonw.exe", "python.exe", "python", "git.exe", "git", "rg.exe", "rg", "schtasks.exe", "schtasks", "pwsh.exe", "pwsh", "powershell.exe", "powershell"]);
const BLOCKED = new Set(["explorer.exe", "explorer", "msiexec.exe", "msiexec", "winget.exe", "winget", "chrome.exe", "chrome", "msedge.exe", "firefox.exe", "cmd.exe", "cmd", "runas.exe", "runas", "rundll32.exe"]);
const exeName = (exe) => path.win32.basename(exe).toLowerCase();
const digest = (exe, args) => crypto.createHash("sha256").update(JSON.stringify([exe, ...args])).digest("hex").slice(0, 16);
const safeId = (value) => typeof value === "string" && /^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/.test(value);

function receiptPath(jobId, dir) {
  const base = dir || path.join(process.env.LOCALAPPDATA || path.join(os.homedir(), ".local", "state"), "Automation", "SilentBackground", "receipts");
  return path.join(base, jobId + ".receipt.json");
}
function writeReceipt(location, packet) {
  fs.mkdirSync(path.dirname(location), { recursive: true });
  const tmp = location + "." + process.pid + "." + crypto.randomBytes(4).toString("hex") + ".tmp";
  try {
    fs.writeFileSync(tmp, JSON.stringify(packet, null, 2) + "\n", { encoding: "utf8", flag: "wx" });
    fs.renameSync(tmp, location);
  } finally {
    if (fs.existsSync(tmp)) fs.unlinkSync(tmp);
  }
}
function decision(executable, args, approvedTools) {
  const exe = exeName(executable);
  if (BLOCKED.has(exe) || /\.(cmd|bat|ps1)$/.test(exe)) return "INTERACTIVE_OR_SHELL_LAUNCHER";
  if (!ALLOWED.has(exe) && !(approvedTools || []).some((x) => exeName(x) === exe)) return "EXECUTABLE_NOT_ADMITTED";
  if (["pwsh.exe", "pwsh", "powershell.exe", "powershell"].includes(exe)) {
    const lower = args.map((x) => x.toLowerCase());
    if (!lower.includes("-noninteractive") && !lower.includes("-noni")) return "POWERSHELL_REQUIRES_NONINTERACTIVE";
    if (!lower.includes("-noprofile") && !lower.includes("-nop")) return "POWERSHELL_REQUIRES_NOPROFILE";
    if (lower.some((x) => /read-host|get-credential|start-process|runas|-\s*verb/i.test(x))) return "POWERSHELL_INTERACTIVE_ACTION";
  }
  return null;
}

function spawnBackground(executable, args = [], options = {}) {
  if (typeof executable !== "string" || !executable.trim() ||
      !Array.isArray(args) || args.some((x) => typeof x !== "string")) {
    throw new TypeError("executable and argv must be explicit strings");
  }
  const jobId = options.jobId;
  if (!safeId(jobId)) throw new TypeError("jobId must be a safe stable identifier");
  const executionClass = options.executionClass || "SILENT_BACKGROUND";
  if (!["SILENT_BACKGROUND", "INTERACTIVE"].includes(executionClass)) throw new TypeError("unknown execution class");
  if (options.shell === true) throw new TypeError("shell:true is not permitted");
  const location = receiptPath(jobId, options.receiptDir);
  const reason = executionClass === "SILENT_BACKGROUND" ? decision(executable, args, options.approvedTools) : null;
  const packet = {
    schema: CONTRACT,
    timestamp_utc: new Date().toISOString(), job_id: jobId,
    execution_class: executionClass, executable: exeName(executable),
    command_digest: digest(executable, args),
    status: reason ? "DEFERRED_INTERACTION" : "PENDING",
    reason_code: reason, mutated_scheduler: false,
    proof_ceiling: "LAUNCH_POLICY_ONLY_NOT_DESCENDANT_OR_FULLSCREEN_CERTIFIED"
  };
  if (reason) {
    writeReceipt(location, packet);
    return { status: packet.status, receiptPath: location, child: null };
  }
  // Fail closed before scheduled execution when private diagnostics are
  // unavailable. Do not make intentional app launches depend on this store.
  if (executionClass === "SILENT_BACKGROUND") writeReceipt(location, packet);
  // stdio ignore avoids display and surprise input; existing consumer-owned
  // writers should retain detailed private output logs independently.
  const child = spawn(executable, args, {
    cwd: options.cwd, env: options.env,
    windowsHide: executionClass === "SILENT_BACKGROUND",
    shell: false, stdio: executionClass === "SILENT_BACKGROUND" ? "ignore" : "inherit"
  });
  packet.status = "SPAWNED_NOT_CERTIFIED";
  packet.pid = child.pid == null ? null : child.pid;
  if (executionClass === "SILENT_BACKGROUND") writeReceipt(location, packet);
  child.on("error", (err) => {
    packet.status = "LAUNCH_FAILED";
    packet.reason_code = err.code || err.name || "CHILD_ERROR";
    if (executionClass === "SILENT_BACKGROUND") writeReceipt(location, packet);
  });
  child.on("exit", (code, signal) => {
    if (packet.status === "LAUNCH_FAILED") return;
    packet.status = signal ? "TERMINATED" : (code === 0 ? "SUCCEEDED" : "NONZERO");
    packet.returncode = code;
    if (signal) packet.signal = signal;
    if (executionClass === "SILENT_BACKGROUND") writeReceipt(location, packet);
  });
  return { status: packet.status, receiptPath: executionClass === "SILENT_BACKGROUND" ? location : null, child };
}
module.exports = { CONTRACT, decision, spawnBackground };
