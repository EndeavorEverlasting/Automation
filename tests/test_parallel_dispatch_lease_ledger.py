"""Synthetic state-transition tests; no provider or native agent execution."""
import importlib.util
from concurrent.futures import ThreadPoolExecutor
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "capabilities" / "parallel-dispatch" / "lease_ledger.py"
spec = importlib.util.spec_from_file_location("auto_pd_lease", SOURCE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
LeaseLedger, AdmissionError = mod.LeaseLedger, mod.AdmissionError
DIGEST = "a" * 64


def manifest(n=3, cap=2):
    return {"schema": "automation.parallel-dispatch-manifest/v1",
            "max_concurrent": cap,
            "lanes": [{"id": f"job-{i}", "argv": ["python", "-V"],
                       "depends_on": ["job-0"] if i == 2 else [],
                       "exclusive_resources": ["shared"] if i in (0, 1) else [],
                       "timeout_seconds": 20} for i in range(n)]}


class DurableLeaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.now = [1000.0]
        self.db = LeaseLedger(Path(self.temp.name) / "private.db",
                              clock=lambda: self.now[0])
        self.db.install(manifest())

    def tearDown(self):
        self.temp.cleanup()

    def test_mutex_dependency_and_independent_proof(self):
        first = self.db.claim("workerA")
        self.assertEqual(first["lane_id"], "job-0")
        self.assertIsNone(self.db.claim("workerB"))
        self.db.heartbeat("job-0", "workerA", first["fence"])
        self.db.report("job-0", "workerA", first["fence"],
                       evidence_sha256=DIGEST, succeeded=True)
        # A worker success claim must never satisfy a dependent lane.
        second = self.db.claim("workerB")
        self.assertEqual(second["lane_id"], "job-1")
        self.db.report("job-1", "workerB", second["fence"],
                       evidence_sha256=DIGEST, succeeded=True)
        self.assertIsNone(self.db.claim("workerC"))
        with self.assertRaises(AdmissionError):
            self.db.verify("job-0", independent_verifier=lambda *_: False)
        self.db.verify("job-0", independent_verifier=lambda _, sha: sha == DIGEST)
        third = self.db.claim("workerC")
        self.assertEqual(third["lane_id"], "job-2")

    def test_expiry_fencing_and_bounded_retry(self):
        first = self.db.claim("workerA", ttl_seconds=5)
        self.now[0] += 6
        second = self.db.claim("workerB", ttl_seconds=5)
        self.assertEqual(second["lane_id"], "job-0")
        self.assertGreater(second["fence"], first["fence"])
        with self.assertRaises(AdmissionError):
            self.db.report("job-0", "workerA", first["fence"],
                           evidence_sha256=DIGEST, succeeded=True)
        self.now[0] += 6
        self.db.claim("workerC")
        self.assertEqual(self.db.snapshot()["states"]["FAILED"], 1)

    def test_manifest_rebind_and_invalid_owner_fail_closed(self):
        with self.assertRaises(AdmissionError):
            self.db.claim("invalid/worker")
        with self.assertRaises(AdmissionError):
            self.db.heartbeat("job-0", "workerA", 0)
        changed = manifest()
        changed["lanes"][0]["timeout_seconds"] = 99
        with self.assertRaises(AdmissionError):
            self.db.install(changed)

    def test_reopen_keeps_fencing_and_live_lease(self):
        self.db.claim("workerA")
        resumed = LeaseLedger(self.db.path, clock=lambda: self.now[0])
        resumed.install(manifest())
        self.assertEqual(resumed.snapshot()["states"]["LEASED"], 1)

    def test_hundred_items_are_queue_not_hundred_running_agents(self):
        large = LeaseLedger(Path(self.temp.name) / "scale.db",
                            clock=lambda: self.now[0])
        large.install(manifest(n=100, cap=4))
        claims = [large.claim(f"worker{i}") for i in range(4)]
        self.assertTrue(all(claims))
        self.assertIsNone(large.claim("worker5"))
        self.assertEqual(large.snapshot()["states"]["LEASED"], 4)

    def test_concurrent_claimers_obey_single_host_cap(self):
        large = LeaseLedger(Path(self.temp.name) / "parallel.db",
                            clock=lambda: self.now[0])
        large.install(manifest(n=100, cap=4))
        with ThreadPoolExecutor(max_workers=16) as workers:
            claims = list(workers.map(lambda i: large.claim(f"worker{i}"),
                                      range(32)))
        admitted = [claim for claim in claims if claim is not None]
        self.assertEqual(len(admitted), 4)
        self.assertEqual(len({item["lane_id"] for item in admitted}), 4)
        self.assertEqual(large.snapshot()["states"]["LEASED"], 4)

    def test_worker_failure_blocks_dependency(self):
        first = self.db.claim("workerA")
        self.db.report("job-0", "workerA", first["fence"],
                       evidence_sha256=DIGEST, succeeded=False)
        self.db.claim("workerB")
        # Dependency job-2 is classified terminal as an upstream failure.
        self.assertEqual(self.db.snapshot()["states"]["BLOCKED_DEPENDENCY"], 1)

    def test_rejected_receipt_and_stale_heartbeat(self):
        first = self.db.claim("workerA", ttl_seconds=5)
        with self.assertRaises(AdmissionError):
            self.db.report("job-0", "workerA", first["fence"],
                           evidence_sha256="not-sha", succeeded=True)
        self.now[0] += 5
        with self.assertRaises(AdmissionError):
            self.db.heartbeat("job-0", "workerA", first["fence"])


    def test_fenced_sqlite_effect_applies_once_and_replays_without_mutation(self):
        import sqlite3
        lease = self.db.claim("workerA")
        calls = [0]
        def apply(cx):
            calls[0] += 1
            cx.execute("CREATE TABLE IF NOT EXISTS app_effects (value TEXT)")
            cx.execute("INSERT INTO app_effects VALUES ('once')")
        args = dict(lane_id="job-0", worker="workerA", fence=lease["fence"],
                    effect_id="effect-1", payload_sha256=DIGEST, apply=apply)
        first = self.db.apply_fenced_sqlite_effect(**args)
        replay = self.db.apply_fenced_sqlite_effect(**args)
        self.assertEqual(first["state"], "SQLITE_EFFECT_APPLIED")
        self.assertEqual(replay["state"], "SQLITE_EFFECT_ALREADY_APPLIED")
        self.assertIn("NOT_EXTERNAL_FENCING", first["proof_ceiling"])
        self.assertEqual(calls[0], 1)
        with sqlite3.connect(self.db.path) as cx:
            self.assertEqual(cx.execute("SELECT COUNT(*) FROM app_effects").fetchone()[0], 1)
            self.assertEqual(cx.execute("SELECT COUNT(*) FROM fenced_effects").fetchone()[0], 1)

    def test_fenced_sqlite_effect_rejects_stale_worker_after_turnover(self):
        import sqlite3
        first = self.db.claim("workerA", ttl_seconds=5)
        self.now[0] += 6
        second = self.db.claim("workerB", ttl_seconds=5)
        self.assertGreater(second["fence"], first["fence"])
        def apply(cx):
            cx.execute("CREATE TABLE IF NOT EXISTS app_effects (value TEXT)")
            cx.execute("INSERT INTO app_effects VALUES ('fresh')")
        with self.assertRaisesRegex(AdmissionError, "stale, expired or unowned"):
            self.db.apply_fenced_sqlite_effect("job-0", "workerA", first["fence"],
                effect_id="turnover", payload_sha256=DIGEST, apply=apply)
        applied = self.db.apply_fenced_sqlite_effect("job-0", "workerB", second["fence"],
            effect_id="turnover", payload_sha256=DIGEST, apply=apply)
        self.assertEqual(applied["state"], "SQLITE_EFFECT_APPLIED")
        with sqlite3.connect(self.db.path) as cx:
            self.assertEqual(cx.execute("SELECT COUNT(*) FROM app_effects").fetchone()[0], 1)

    def test_fenced_sqlite_effect_rolls_back_callback_failure(self):
        import sqlite3
        lease = self.db.claim("workerA")
        def broken(cx):
            cx.execute("CREATE TABLE app_effects (value TEXT)")
            cx.execute("INSERT INTO app_effects VALUES ('not-committed')")
            raise RuntimeError("simulated local failure")
        with self.assertRaisesRegex(RuntimeError, "simulated"):
            self.db.apply_fenced_sqlite_effect("job-0", "workerA", lease["fence"],
                effect_id="rollback", payload_sha256=DIGEST, apply=broken)
        with sqlite3.connect(self.db.path) as cx:
            self.assertIsNone(cx.execute(
                "SELECT name FROM sqlite_master WHERE name='app_effects'").fetchone())
        def good(cx):
            cx.execute("CREATE TABLE app_effects (value TEXT)")
            cx.execute("INSERT INTO app_effects VALUES ('committed')")
        self.db.apply_fenced_sqlite_effect("job-0", "workerA", lease["fence"],
            effect_id="rollback", payload_sha256=DIGEST, apply=good)
        with sqlite3.connect(self.db.path) as cx:
            self.assertEqual(cx.execute("SELECT value FROM app_effects").fetchone()[0],
                             "committed")

    def test_fenced_sqlite_effect_rejects_conflicting_reuse_and_lane(self):
        first = self.db.claim("workerA")
        def apply(cx):
            cx.execute("CREATE TABLE IF NOT EXISTS app_effects (value TEXT)")
            cx.execute("INSERT INTO app_effects VALUES ('first')")
        self.db.apply_fenced_sqlite_effect("job-0", "workerA", first["fence"],
            effect_id="shared-key", payload_sha256=DIGEST, apply=apply)
        with self.assertRaisesRegex(AdmissionError, "conflicting payload or lane"):
            self.db.apply_fenced_sqlite_effect("job-0", "workerA", first["fence"],
                effect_id="shared-key", payload_sha256="b"*64, apply=apply)
        self.db.report("job-0", "workerA", first["fence"],
                       evidence_sha256=DIGEST, succeeded=True)
        second = self.db.claim("workerB")
        self.assertEqual(second["lane_id"], "job-1")
        with self.assertRaisesRegex(AdmissionError, "conflicting payload or lane"):
            self.db.apply_fenced_sqlite_effect("job-1", "workerB", second["fence"],
                effect_id="shared-key", payload_sha256=DIGEST, apply=apply)

    def test_fenced_sqlite_effect_concurrent_replays_apply_once(self):
        import sqlite3
        lease = self.db.claim("workerA")
        calls = [0]
        def apply(cx):
            calls[0] += 1
            cx.execute("CREATE TABLE IF NOT EXISTS app_effects (value TEXT)")
            cx.execute("INSERT INTO app_effects VALUES ('once')")
        def run(_):
            return self.db.apply_fenced_sqlite_effect(
                "job-0", "workerA", lease["fence"], effect_id="parallel",
                payload_sha256=DIGEST, apply=apply)["state"]
        with ThreadPoolExecutor(max_workers=8) as pool:
            states = list(pool.map(run, range(8)))
        self.assertEqual(states.count("SQLITE_EFFECT_APPLIED"), 1)
        self.assertEqual(states.count("SQLITE_EFFECT_ALREADY_APPLIED"), 7)
        self.assertEqual(calls[0], 1)
        with sqlite3.connect(self.db.path) as cx:
            self.assertEqual(cx.execute("SELECT COUNT(*) FROM app_effects").fetchone()[0], 1)

    def test_fenced_sqlite_effect_expiry_during_callback_rolls_back(self):
        import sqlite3
        lease = self.db.claim("workerA", ttl_seconds=5)
        def slow(cx):
            cx.execute("CREATE TABLE app_effects (value TEXT)")
            cx.execute("INSERT INTO app_effects VALUES ('expired')")
            self.now[0] += 6
        with self.assertRaisesRegex(AdmissionError, "stale, expired or unowned"):
            self.db.apply_fenced_sqlite_effect("job-0", "workerA", lease["fence"],
                effect_id="late", payload_sha256=DIGEST, apply=slow)
        with sqlite3.connect(self.db.path) as cx:
            self.assertIsNone(cx.execute(
                "SELECT name FROM sqlite_master WHERE name='app_effects'").fetchone())


if __name__ == "__main__":
    unittest.main()
