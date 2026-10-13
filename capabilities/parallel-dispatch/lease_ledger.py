"""Single-host SQLite claim ledger for a separately authorized agent executor.

This module NEVER launches a model or process and does not certify model auth,
host fencing of side effects, or accepted outcomes. Only a trusted runner may
consume its leases and a separately trusted verifier may approve reports.
"""
from __future__ import annotations

from contextlib import contextmanager
import importlib.util
import json
from pathlib import Path
import re
import sqlite3
import time
from typing import Callable

SCHEMA = "automation.parallel-dispatch-lease-ledger/v1"
IDENTIFIER = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,79}$")
DIGEST = re.compile(r"^[0-9a-f]{64}$")
MAX_ATTEMPTS = 2


def _manifest_module():
    path = Path(__file__).with_name("run.py")
    spec = importlib.util.spec_from_file_location("automation_parallel_dispatch_run", path)
    if spec is None or spec.loader is None:
        raise ValueError("canonical dispatch validator missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AdmissionError(ValueError):
    """Fail-closed admission/ownership transition."""


class LeaseLedger:
    def __init__(self, path: Path, *, clock: Callable[[], float] = time.time):
        self.path = Path(path)
        self.clock = clock

    @contextmanager
    def _connection(self):
        cx = sqlite3.connect(self.path, timeout=10)
        try:
            cx.row_factory = sqlite3.Row
            cx.execute("PRAGMA busy_timeout=10000")
            with cx:
                yield cx
        finally:
            cx.close()

    def install(self, manifest: dict) -> dict:
        # Reuse exact manifest admission; argv is never persisted here.
        adapter = _manifest_module()
        validated = adapter.validate(manifest)
        fingerprint = validated["manifest_sha256"]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as cx:
            cx.execute("BEGIN IMMEDIATE")
            cx.execute("CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            cx.execute("""CREATE TABLE IF NOT EXISTS lanes (
                id TEXT PRIMARY KEY, ord INTEGER NOT NULL, deps TEXT NOT NULL,
                resources TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'PENDING',
                owner TEXT, fence INTEGER NOT NULL DEFAULT 0,
                attempts INTEGER NOT NULL DEFAULT 0, deadline REAL,
                evidence_sha256 TEXT)""")
            current = cx.execute("SELECT value FROM metadata WHERE key='manifest_sha256'").fetchone()
            if current and current["value"] != fingerprint:
                raise AdmissionError("manifest changed: a different ledger is required")
            if current:
                count = cx.execute("SELECT COUNT(*) FROM lanes").fetchone()[0]
                if count != len(manifest["lanes"]):
                    raise AdmissionError("ledger/manifest row count mismatch")
            else:
                cx.execute("INSERT INTO metadata VALUES ('manifest_sha256', ?)", (fingerprint,))
                cx.execute("INSERT INTO metadata VALUES ('max_concurrent', ?)",
                           (str(manifest["max_concurrent"]),))
                for order, lane in enumerate(manifest["lanes"]):
                    cx.execute("INSERT INTO lanes (id, ord, deps, resources, status) VALUES (?, ?, ?, ?, 'PENDING')",
                               (lane["id"], order, json.dumps(lane["depends_on"]),
                                json.dumps(lane["exclusive_resources"])))
        return {"schema": SCHEMA, "manifest_sha256": fingerprint,
                "state": "INSTALLED_NOT_DISPATCHED", "lane_count": len(manifest["lanes"])}

    def claim(self, worker: str, *, ttl_seconds: int = 120) -> dict | None:
        if not isinstance(worker, str) or not IDENTIFIER.fullmatch(worker):
            raise AdmissionError("opaque worker identifier required")
        if type(ttl_seconds) is not int or not 1 <= ttl_seconds <= 3600:
            raise AdmissionError("ttl_seconds must be between 1 and 3600")
        now = self.clock()
        with self._connection() as cx:
            cx.execute("BEGIN IMMEDIATE")
            config = cx.execute("SELECT value FROM metadata WHERE key='max_concurrent'").fetchone()
            if not config:
                raise AdmissionError("ledger not initialized")
            # Expiry revokes only the claim, not any still-running external process.
            # Callers MUST use the fencing token and idempotency at their adapter.
            cx.execute("UPDATE lanes SET status='FAILED', owner=NULL, deadline=NULL "
                       "WHERE status='LEASED' AND deadline<=? AND attempts>=?",
                       (now, MAX_ATTEMPTS))
            cx.execute("UPDATE lanes SET status='PENDING', owner=NULL, deadline=NULL "
                       "WHERE status='LEASED' AND deadline<=?", (now,))
            rows = cx.execute("SELECT * FROM lanes ORDER BY ord").fetchall()
            active = [r for r in rows if r["status"] == "LEASED"]
            if len(active) >= int(config["value"]):
                return None
            held = set()
            for row in active:
                held.update(json.loads(row["resources"]))
            states = {r["id"]: r["status"] for r in rows}
            # Resolve dependency failures before granting any new claim.
            # A previous early return must not hide a blocked successor.
            for row in rows:
                if row["status"] != "PENDING":
                    continue
                if any(states.get(dep) in {"FAILED", "BLOCKED_DEPENDENCY"}
                       for dep in json.loads(row["deps"])):
                    cx.execute("UPDATE lanes SET status='BLOCKED_DEPENDENCY' WHERE id=?", (row["id"],))
                    states[row["id"]] = "BLOCKED_DEPENDENCY"
            for row in rows:
                if states[row["id"]] != "PENDING":
                    continue
                deps = json.loads(row["deps"])
                if any(states.get(dep) in {"FAILED", "BLOCKED_DEPENDENCY"} for dep in deps):
                    cx.execute("UPDATE lanes SET status='BLOCKED_DEPENDENCY' WHERE id=?", (row["id"],))
                    continue
                if any(states.get(dep) != "VERIFIED" for dep in deps):
                    continue
                resources = set(json.loads(row["resources"]))
                if resources & held:
                    continue
                token = row["fence"] + 1
                cx.execute("UPDATE lanes SET status='LEASED', owner=?, fence=?, attempts=attempts+1, deadline=? WHERE id=?",
                           (worker, token, now + ttl_seconds, row["id"]))
                return {"schema": SCHEMA, "lane_id": row["id"],
                        "owner": worker, "fence": token, "deadline_epoch": now + ttl_seconds,
                        "state": "LEASE_CLAIMED_NO_EXECUTION"}
        return None

    def _leased(self, cx, lane_id: str, worker: str, fence: int, now: float):
        if type(fence) is not int or fence < 1:
            raise AdmissionError("invalid fencing token")
        row = cx.execute("SELECT * FROM lanes WHERE id=?", (lane_id,)).fetchone()
        if (row is None or row["status"] != "LEASED" or row["owner"] != worker
                or row["fence"] != fence or row["deadline"] <= now):
            raise AdmissionError("stale, expired or unowned lease")
        return row

    def heartbeat(self, lane_id: str, worker: str, fence: int, *, ttl_seconds: int = 120):
        if type(ttl_seconds) is not int or not 1 <= ttl_seconds <= 3600:
            raise AdmissionError("invalid heartbeat ttl")
        now = self.clock()
        with self._connection() as cx:
            cx.execute("BEGIN IMMEDIATE")
            self._leased(cx, lane_id, worker, fence, now)
            cx.execute("UPDATE lanes SET deadline=? WHERE id=?", (now + ttl_seconds, lane_id))
        return {"state": "LEASE_RENEWED_NO_COMPLETION_PROOF"}

    def report(self, lane_id: str, worker: str, fence: int, *,
               evidence_sha256: str, succeeded: bool) -> dict:
        if not isinstance(evidence_sha256, str) or not DIGEST.fullmatch(evidence_sha256):
            raise AdmissionError("receipt SHA256 required; raw evidence belongs outside ledger")
        if type(succeeded) is not bool:
            raise AdmissionError("succeeded must be boolean")
        now = self.clock()
        with self._connection() as cx:
            cx.execute("BEGIN IMMEDIATE")
            self._leased(cx, lane_id, worker, fence, now)
            state = "REPORTED_UNVERIFIED" if succeeded else "FAILED"
            cx.execute("UPDATE lanes SET status=?, deadline=NULL, evidence_sha256=? WHERE id=?",
                       (state, evidence_sha256, lane_id))
        return {"lane_id": lane_id, "state": state, "proof": "WORKER_REPORT_ONLY"}

    def verify(self, lane_id: str, *, independent_verifier: Callable[[str, str], bool]) -> dict:
        # The real host must supply a trusted independent verifier; the ledger
        # itself cannot attest its independence or validate native session IDs.
        with self._connection() as cx:
            cx.execute("BEGIN IMMEDIATE")
            row = cx.execute("SELECT * FROM lanes WHERE id=?", (lane_id,)).fetchone()
            if row is None or row["status"] != "REPORTED_UNVERIFIED":
                raise AdmissionError("no unverified worker report exists")
            if independent_verifier(lane_id, row["evidence_sha256"]) is not True:
                raise AdmissionError("independent verifier rejected evidence")
            cx.execute("UPDATE lanes SET status='VERIFIED' WHERE id=?", (lane_id,))
        return {"lane_id": lane_id, "state": "VERIFIED",
                "proof": "EXTERNAL_VERIFIER_BOUNDARY"}

    def snapshot(self) -> dict:
        with self._connection() as cx:
            counts = cx.execute("SELECT status, COUNT(*) FROM lanes GROUP BY status").fetchall()
            return {"schema": SCHEMA, "states": {row[0]: row[1] for row in counts},
                    "proof_ceiling": "SINGLE_HOST_SQLITE_LEASE_LEDGER_NOT_NATIVE_AGENT_DISPATCH"}
