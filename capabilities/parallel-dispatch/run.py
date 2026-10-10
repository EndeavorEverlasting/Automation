#!/usr/bin/env python3
"""AUTO-PD1: bounded argv fan-out with measured overlap, not an agent scheduler.

This is an execution adapter primitive for *already authorized* local packets.
It cannot allocate agents, attest Git worktrees, validate provider credentials,
derive judgment authority, or guarantee distributed exactly-once execution.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
from typing import Any

SCHEMA = "automation.parallel-dispatch-manifest/v1"
RECEIPT_SCHEMA = "automation.parallel-dispatch-receipt/v1"
ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,79}$")
MAX_ITEMS = 1000
MAX_CONCURRENCY = 100
SAFE_ENV = {"PATH", "SystemRoot", "SYSTEMROOT", "TEMP", "TMP", "TMPDIR", "HOME",
            "USERPROFILE", "WINDIR", "PYTHONPATH", "LANG", "LC_ALL"}
OUTCOMES = {"SUCCEEDED", "FAILED", "TIMED_OUT", "SPAWN_FAILED", "BLOCKED_DEPENDENCY"}


class DispatchAdmissionError(ValueError):
    pass


def fingerprint(value: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def _words(obj: Any, label: str, *, require: bool = False) -> list[str]:
    if not isinstance(obj, list) or (require and not obj):
        raise DispatchAdmissionError(f"{label}: expected list")
    if any(not isinstance(x, str) or not x or any(ord(ch) < 32 for ch in x)
           or len(x) > 2048 for x in obj):
        raise DispatchAdmissionError(f"{label}: invalid token")
    return obj


def validate(packet: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(packet, dict) or packet.get("schema") != SCHEMA:
        raise DispatchAdmissionError("schema mismatch")
    if set(packet) != {"schema", "max_concurrent", "lanes"}:
        raise DispatchAdmissionError("unknown or missing manifest fields")
    cap = packet["max_concurrent"]
    if type(cap) is not int or not (1 <= cap <= MAX_CONCURRENCY):
        raise DispatchAdmissionError("invalid bounded concurrency cap")
    raw = packet["lanes"]
    if not isinstance(raw, list) or not (1 <= len(raw) <= MAX_ITEMS):
        raise DispatchAdmissionError("invalid bounded lane count")
    names: set[str] = set()
    lanes: dict[str, dict[str, Any]] = {}
    for item in raw:
        if not isinstance(item, dict) or set(item) != {
            "id", "argv", "depends_on", "exclusive_resources", "timeout_seconds"
        }:
            raise DispatchAdmissionError("invalid lane structure")
        lane_id = item["id"]
        if not isinstance(lane_id, str) or not ID.fullmatch(lane_id) or lane_id in names:
            raise DispatchAdmissionError("invalid or duplicate lane id")
        names.add(lane_id)
        cmd = _words(item["argv"], "argv", require=True)
        # Explicit argv, no shell string expansion; callers must still verify
        # the executable and the mutation envelope before authorizing --execute.
        if cmd[0].lower() in {"sh", "bash", "cmd", "cmd.exe", "powershell",
                              "powershell.exe", "pwsh"}:
            raise DispatchAdmissionError("shell entrypoints require a separate trusted adapter")
        deps = _words(item["depends_on"], "depends_on")
        resources = _words(item["exclusive_resources"], "exclusive_resources")
        if any(not ID.fullmatch(v) for v in deps + resources):
            raise DispatchAdmissionError("invalid dependency/resource identity")
        if len(set(deps)) != len(deps) or len(set(resources)) != len(resources):
            raise DispatchAdmissionError("duplicate dependency/resource identity")
        timeout = item["timeout_seconds"]
        if type(timeout) is not int or not (1 <= timeout <= 3600):
            raise DispatchAdmissionError("invalid per-task timeout")
        lanes[lane_id] = item
    for lane_id, item in lanes.items():
        if lane_id in item["depends_on"] or any(dep not in names for dep in item["depends_on"]):
            raise DispatchAdmissionError("self/missing dependency")
    # DAG detection is independent of declared input ordering.
    visiting: set[str] = set()
    complete: set[str] = set()
    def visit(lane_id: str) -> None:
        if lane_id in visiting:
            raise DispatchAdmissionError("dependency cycle")
        if lane_id in complete:
            return
        visiting.add(lane_id)
        for dep in lanes[lane_id]["depends_on"]:
            visit(dep)
        visiting.remove(lane_id)
        complete.add(lane_id)
    for name in names:
        visit(name)
    return {"schema": RECEIPT_SCHEMA, "manifest_sha256": fingerprint(packet),
            "lane_count": len(lanes), "max_concurrent": cap,
            "admission": "VALIDATED_NOT_DISPATCHED"}


def _execute_lane(item: dict[str, Any]) -> dict[str, Any]:
    started = time.monotonic_ns()
    safe_env = {k: v for k, v in os.environ.items() if k in SAFE_ENV}
    try:
        outcome = subprocess.run(item["argv"], shell=False, stdin=subprocess.DEVNULL,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 env=safe_env, timeout=item["timeout_seconds"],
                                 check=False)
        state = "SUCCEEDED" if outcome.returncode == 0 else "FAILED"
        code = outcome.returncode
    except subprocess.TimeoutExpired:
        state, code = "TIMED_OUT", None
    except (OSError, ValueError):
        state, code = "SPAWN_FAILED", None
    ended = time.monotonic_ns()
    return {"id": item["id"], "state": state, "exit_code": code,
            "start_ns": started, "end_ns": ended,
            "elapsed_ms": round((ended - started) / 1e6, 2)}


def _peak_overlap(results: list[dict[str, Any]]) -> int:
    events = []
    for r in results:
        if r["state"] == "BLOCKED_DEPENDENCY":
            continue
        # For equal timestamps, exit precedes start so a tie doesn't imply overlap.
        events.extend([(r["start_ns"], 1), (r["end_ns"], -1)])
    events.sort(key=lambda v: (v[0], v[1]))
    n = high = 0
    for _, change in events:
        n += change
        high = max(high, n)
    return high


def run(packet: dict[str, Any], *, execute: bool = False) -> dict[str, Any]:
    receipt = validate(packet)
    if not execute:
        return receipt
    # One explicit invocation, one bounded process pool. No persistent scheduler,
    # implicit auth, cloud credentials, model/API calls, or silent retries.
    indexed = {item["id"]: item for item in packet["lanes"]}
    pending = dict(indexed)
    results: dict[str, dict[str, Any]] = {}
    in_flight: dict[Any, str] = {}
    claimed_resources: set[str] = set()
    with ThreadPoolExecutor(max_workers=packet["max_concurrent"]) as executor:
        while pending or in_flight:
            changed = False
            for lane_id, item in list(pending.items()):
                if any(dep in results and results[dep]["state"] != "SUCCEEDED"
                       for dep in item["depends_on"]):
                    results[lane_id] = {"id": lane_id, "state": "BLOCKED_DEPENDENCY",
                                        "exit_code": None, "elapsed_ms": 0.0}
                    del pending[lane_id]
                    changed = True
                    continue
                if len(in_flight) >= packet["max_concurrent"]:
                    break
                if any(dep not in results for dep in item["depends_on"]):
                    continue
                resources = set(item["exclusive_resources"])
                if resources & claimed_resources:
                    continue
                claimed_resources.update(resources)
                future = executor.submit(_execute_lane, item)
                in_flight[future] = lane_id
                del pending[lane_id]
                changed = True
            if in_flight:
                done, _ = wait(tuple(in_flight), return_when=FIRST_COMPLETED)
                for future in done:
                    lane_id = in_flight.pop(future)
                    results[lane_id] = future.result()
                    claimed_resources.difference_update(indexed[lane_id]["exclusive_resources"])
            elif not changed:
                raise DispatchAdmissionError("scheduler stalled unexpectedly")
    items = [results[item["id"]] for item in packet["lanes"]]
    peak = _peak_overlap(items)
    outcomes = {name: sum(x["state"] == name for x in items) for name in OUTCOMES}
    receipt.update({
        "admission": "EXECUTED_BY_LOCAL_ARGV_ADAPTER",
        "counts": outcomes,
        "started_count": len(items) - outcomes["BLOCKED_DEPENDENCY"],
        "observed_peak_overlapping_processes": peak,
        "observed_parallelism": peak >= 2,
        "all_succeeded": outcomes["SUCCEEDED"] == len(items),
        "proof_ceiling": "Actual local argv process overlap; NOT 100 LLM agents, host authority, validated worktree isolation, model authentication, distributed lease or user outcome",
        "lanes": [{"id": x["id"], "state": x["state"], "elapsed_ms": x["elapsed_ms"]}
                  for x in items],
    })
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--execute", action="store_true")
    options = parser.parse_args()
    try:
        task = json.loads(options.manifest.read_text(encoding="utf-8"))
        summary = run(task, execute=options.execute)
    except (OSError, json.JSONDecodeError, DispatchAdmissionError) as exc:
        parser.error(str(exc))
    if options.receipt:
        options.receipt.parent.mkdir(parents=True, exist_ok=True)
        options.receipt.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, sort_keys=True))
    return 0 if not options.execute or summary["all_succeeded"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
