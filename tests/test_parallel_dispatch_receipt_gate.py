"""PS-0131 synthetic negative and positive gates; NOT provider authentication."""
import importlib.util
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[1] / "capabilities/parallel-dispatch/receipt_gate.py"
spec = importlib.util.spec_from_file_location("auto_pd_receipt_gate", PATH)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

NOW = 1800000000
HEAD = "a" * 40
DIGEST = "b" * 64


def fixture():
    p = dict(schema=gate.SCHEMA, task_key="PROMPT-SCRATCH", lane_id="PS-0131",
             actor="trusted-executor", owner="Automation", resource_id="repo_main",
             expected_head=HEAD, claim_token="claim:17", receipt_ref="receipt:42",
             max_age_seconds=120)
    c = dict(task_key=p["task_key"], lane_id=p["lane_id"], actor=p["actor"], owner=p["owner"],
             resource_id=p["resource_id"], expected_head=HEAD,
             claim_token=p["claim_token"], state="ACTIVE",
             issued_at_epoch=NOW - 60, deadline_epoch=NOW + 90, fence=7)
    r = dict(receipt_ref=p["receipt_ref"], task_key=p["task_key"], lane_id=p["lane_id"],
             actor=p["actor"], owner=p["owner"], resource_id=p["resource_id"],
             head=HEAD, evidence_sha256=DIGEST, observed_at_epoch=NOW - 30,
             state="PROVIDER_VERIFIED", fence=7)
    return p, c, r


def attempt(p, c, r, head=HEAD):
    return gate.preflight(p, claim_reader=lambda *_: c, receipt_reader=lambda *_: r,
                          head_reader=lambda *_: head, now_epoch=NOW)


class ReceiptGateTests(unittest.TestCase):
    def test_valid_synthetic_triple_is_only_adapter_asserted(self):
        p, c, r = fixture()
        result = attempt(p, c, r)
        self.assertEqual(result["state"], "ADAPTER_ASSERTED_PREFLIGHT_ONLY")
        self.assertIn("NOT_PRODUCTION", result["proof_ceiling"])
        self.assertNotIn("claim_token", result)

    def test_no_admission_from_missing_reader(self):
        p, c, r = fixture()
        with self.assertRaises(gate.AdmissionError):
            gate.preflight(p, claim_reader=None, receipt_reader=lambda *_: r,
                           head_reader=lambda *_: HEAD, now_epoch=NOW)

    def test_provider_failure_fails_closed(self):
        p, c, r = fixture()
        def unavailable(*_):
            raise ConnectionError("no provider")
        with self.assertRaisesRegex(gate.AdmissionError, "provider read unavailable"):
            gate.preflight(p, claim_reader=unavailable, receipt_reader=lambda *_: r,
                           head_reader=lambda *_: HEAD, now_epoch=NOW)

    def test_claim_expiry_and_fence(self):
        p, c, r = fixture()
        c["deadline_epoch"] = NOW
        with self.assertRaisesRegex(gate.AdmissionError, "expired"):
            attempt(p, c, r)
        c["deadline_epoch"] = NOW + 90
        c["fence"] = 8
        with self.assertRaisesRegex(gate.AdmissionError, "fence mismatch"):
            attempt(p, c, r)

    def test_preclaim_receipt_replay_rejected(self):
        p, c, r = fixture()
        c["issued_at_epoch"] = NOW - 20
        # Receipt is fresh, matching identity/head/fence, but older than claim.
        with self.assertRaisesRegex(gate.AdmissionError, "predates claim"):
            attempt(p, c, r)

    def test_claim_issuance_bounds_and_missing_field(self):
        for change, message in (
            ({"issued_at_epoch": NOW + 1}, "issued in future"),
            ({"issued_at_epoch": NOW + 91}, "window invalid"),
            ({"issued_at_epoch": 0}, "invalid epoch"),
        ):
            with self.subTest(change=change):
                p, c, r = fixture()
                c.update(change)
                with self.assertRaisesRegex(gate.AdmissionError, message):
                    attempt(p, c, r)
        p, c, r = fixture()
        del c["issued_at_epoch"]
        with self.assertRaisesRegex(gate.AdmissionError, "missing or unexpected"):
            attempt(p, c, r)

    def test_receipt_at_claim_issuance_boundary_is_admitted_only_as_assertion(self):
        p, c, r = fixture()
        c["issued_at_epoch"] = r["observed_at_epoch"]
        result = attempt(p, c, r)
        self.assertEqual(result["state"], "ADAPTER_ASSERTED_PREFLIGHT_ONLY")

    def test_cross_task_claim_or_receipt_replay_rejected(self):
        # All other lane/resource/actor/fence/head fields match: task identity
        # must still be bound by BOTH independent provider records.
        for provider_record in ("claim", "receipt"):
            with self.subTest(provider_record=provider_record):
                p, c, r = fixture()
                (c if provider_record == "claim" else r)["task_key"] = "OTHER-TASK"
                with self.assertRaisesRegex(gate.AdmissionError, "task_key mismatch"):
                    attempt(p, c, r)

    def test_missing_provider_task_identity_fails_closed(self):
        for provider_record in ("claim", "receipt"):
            with self.subTest(provider_record=provider_record):
                p, c, r = fixture()
                del (c if provider_record == "claim" else r)["task_key"]
                with self.assertRaisesRegex(gate.AdmissionError, "missing or unexpected"):
                    attempt(p, c, r)

    def test_claim_turnover_during_provider_reads_fails_closed(self):
        # A claim may be revoked or replaced while receipt/head reads run.
        # The first valid snapshot alone must not authorize preflight.
        for mutation in ({"fence": 8}, {"state": "REVOKED"},
                         {"claim_token": "claim:18"}):
            with self.subTest(mutation=mutation):
                p, c, r = fixture()
                calls = [0]
                def read_claim(*_):
                    calls[0] += 1
                    return c if calls[0] == 1 else {**c, **mutation}
                with self.assertRaisesRegex(gate.AdmissionError, "changed during preflight"):
                    gate.preflight(p, claim_reader=read_claim,
                                   receipt_reader=lambda *_: r,
                                   head_reader=lambda *_: HEAD, now_epoch=NOW)
                self.assertEqual(calls[0], 2)

    def test_mutable_claim_snapshot_cannot_hide_turnover(self):
        p, c, r = fixture()
        calls = [0]
        def read_claim(*_):
            calls[0] += 1
            if calls[0] == 2:
                c["fence"] = 8  # Same mutable provider dictionary, new lease.
            return c
        with self.assertRaisesRegex(gate.AdmissionError, "changed during preflight"):
            gate.preflight(p, claim_reader=read_claim,
                           receipt_reader=lambda *_: r,
                           head_reader=lambda *_: HEAD, now_epoch=NOW)

    def test_head_turnover_during_provider_reads_fails_closed(self):
        p, c, r = fixture()
        calls = [0]
        def read_head(*_):
            calls[0] += 1
            return HEAD if calls[0] == 1 else "f" * 40
        with self.assertRaisesRegex(gate.AdmissionError, "head changed during preflight"):
            gate.preflight(p, claim_reader=lambda *_: c,
                           receipt_reader=lambda *_: r,
                           head_reader=read_head, now_epoch=NOW)
        self.assertEqual(calls[0], 2)

    def test_provider_recheck_failure_fails_closed(self):
        p, c, r = fixture()
        calls = [0]
        def read_claim(*_):
            calls[0] += 1
            if calls[0] == 2:
                raise ConnectionError("claim authority unavailable")
            return c
        with self.assertRaisesRegex(gate.AdmissionError, "provider read unavailable"):
            gate.preflight(p, claim_reader=read_claim,
                           receipt_reader=lambda *_: r,
                           head_reader=lambda *_: HEAD, now_epoch=NOW)

    def test_claim_expiry_during_provider_reads_fails_closed(self):
        from unittest.mock import patch
        p, c, r = fixture()
        # The provider returned a valid claim at the start, but the reads
        # consumed the remaining lease. No preflight admission is possible.
        with patch.object(gate.time, "time", side_effect=[NOW - 5, NOW + 91]):
            with self.assertRaisesRegex(gate.AdmissionError, "expired during preflight"):
                gate.preflight(p, claim_reader=lambda *_: c,
                               receipt_reader=lambda *_: r,
                               head_reader=lambda *_: HEAD)

    def test_wrong_actor_owner_or_lane_rejected(self):
        for field in ("actor", "owner", "lane_id", "resource_id"):
            with self.subTest(field=field):
                p, c, r = fixture()
                r[field] = "intruder"
                with self.assertRaises(gate.AdmissionError):
                    attempt(p, c, r)

    def test_stale_head_rejected(self):
        p, c, r = fixture()
        with self.assertRaisesRegex(gate.AdmissionError, "revision"):
            attempt(p, c, r, head="f" * 40)

    def test_fabricated_or_stale_receipt_rejected(self):
        for change in (dict(state="UNVERIFIED"), dict(observed_at_epoch=NOW-121),
                       dict(observed_at_epoch=NOW+1), dict(evidence_sha256="fake")):
            with self.subTest(change=change):
                p, c, r = fixture()
                r.update(change)
                with self.assertRaises(gate.AdmissionError):
                    attempt(p, c, r)

    def test_unicode_and_invalid_identity_rejected(self):
        for resource in ("path:docs", "docs/subdir", "\u200b", "\u00a0", "r" * 81, ""):
            with self.subTest(resource=resource):
                p, c, r = fixture()
                p["resource_id"] = resource
                with self.assertRaises(gate.AdmissionError):
                    attempt(p, c, r)

    def test_strict_shape_and_ttl(self):
        p, c, r = fixture()
        p["unknown"] = True
        with self.assertRaises(gate.AdmissionError):
            attempt(p, c, r)
        p.pop("unknown")
        p["max_age_seconds"] = True
        with self.assertRaises(gate.AdmissionError):
            attempt(p, c, r)

    def test_no_trust_in_unverified_claim(self):
        p, c, r = fixture()
        c["state"] = "REPORTED_UNVERIFIED"
        with self.assertRaisesRegex(gate.AdmissionError, "not active"):
            attempt(p, c, r)

    def test_future_receipt_outside_claim_window(self):
        p, c, r = fixture()
        r["observed_at_epoch"] = NOW - 1
        c["deadline_epoch"] = NOW - 2
        with self.assertRaises(gate.AdmissionError):
            attempt(p, c, r)


    def test_unrepresentable_provider_epochs_fail_as_admission_errors(self):
        # Python math.isfinite(int) raises OverflowError for huge integers.
        # Provider-supplied time must fail closed with the gate's own error.
        huge = 10 ** 400
        p, c, r = fixture()
        with self.assertRaisesRegex(gate.AdmissionError, "now_epoch: invalid epoch"):
            gate.preflight(p, claim_reader=lambda *_: c,
                           receipt_reader=lambda *_: r,
                           head_reader=lambda *_: HEAD, now_epoch=huge)
        for field in ("issued_at_epoch", "deadline_epoch"):
            with self.subTest(field=field):
                p, c, r = fixture()
                c[field] = huge
                with self.assertRaisesRegex(gate.AdmissionError, "invalid epoch"):
                    attempt(p, c, r)
        p, c, r = fixture()
        r["observed_at_epoch"] = huge
        with self.assertRaisesRegex(gate.AdmissionError, "invalid epoch"):
            attempt(p, c, r)
        self.assertEqual(attempt(*fixture())["state"], "ADAPTER_ASSERTED_PREFLIGHT_ONLY")



if __name__ == "__main__":
    unittest.main()
