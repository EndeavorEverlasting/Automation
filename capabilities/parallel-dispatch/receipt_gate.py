"""PS-0131: provider-neutral, fail-closed claim/receipt preflight.

A caller must supply *trusted* adapters for live claim, receipt and head reads.
This module cannot establish adapter trust, execute work, or fence side effects.
It must not be used as standalone production execution authority.
"""
from __future__ import annotations

import math
import re
import time
from typing import Any, Callable

SCHEMA = "automation.trusted-execution-preflight/v1"
_NativeResourcePattern = r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,79}$"
_NATIVE_RESOURCE_ID = re.compile(_NativeResourcePattern)  # parity with run.py ID
_SHA = re.compile(r"^[0-9a-f]{40}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,191}$")
_FIELDS = frozenset({"schema", "task_key", "lane_id", "actor", "owner",
                     "resource_id", "expected_head", "claim_token", "receipt_ref",
                     "max_age_seconds"})
_CLAIM_FIELDS = frozenset({"task_key", "lane_id", "actor", "owner", "resource_id",
                           "expected_head", "claim_token", "state",
                           "issued_at_epoch", "deadline_epoch", "fence"})
_RECEIPT_FIELDS = frozenset({"receipt_ref", "task_key", "lane_id", "actor", "owner",
                             "resource_id", "head", "evidence_sha256",
                             "observed_at_epoch", "state", "fence"})


class AdmissionError(ValueError):
    """An execution attempt is not admitted; do not start the executor."""


def _id(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _NATIVE_RESOURCE_ID.fullmatch(value):
        raise AdmissionError(f"{label}: invalid native identity")
    return value


def _ref(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _REF.fullmatch(value):
        raise AdmissionError(f"{label}: invalid opaque reference")
    return value


def _epoch(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise AdmissionError(f"{label}: invalid epoch")
    try:
        normalized = float(value)
    except (OverflowError, ValueError, TypeError) as exc:
        raise AdmissionError(f"{label}: invalid epoch") from exc
    if not math.isfinite(normalized):
        raise AdmissionError(f"{label}: invalid epoch")
    return normalized


def _exact_record(value: Any, fields: frozenset[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise AdmissionError(f"{label}: missing or unexpected fields")
    return value


def preflight(packet: dict[str, Any], *,
              claim_reader: Callable[[str, str], dict[str, Any]],
              receipt_reader: Callable[[str], dict[str, Any]],
              head_reader: Callable[[str], str],
              now_epoch: float | None = None) -> dict[str, Any]:
    """Admit only a consistent, fresh triple of externally read provider facts.

    All three readers MUST be independently authenticated by the host. Passing
    caller-supplied dictionaries, spreadsheets, or always-true callbacks is NOT
    production authentication. No state is mutated and no claim is acquired.
    """
    p = _exact_record(packet, _FIELDS, "packet")
    if p["schema"] != SCHEMA:
        raise AdmissionError("schema mismatch")
    for key in ("task_key", "lane_id", "actor", "owner", "resource_id"):
        _id(p[key], key)
    if not isinstance(p["expected_head"], str) or not _SHA.fullmatch(p["expected_head"]):
        raise AdmissionError("expected_head: immutable SHA required")
    _ref(p["claim_token"], "claim_token")
    _ref(p["receipt_ref"], "receipt_ref")
    ttl = p["max_age_seconds"]
    if type(ttl) is not int or not 1 <= ttl <= 3600:
        raise AdmissionError("max_age_seconds: invalid bound")
    now = _epoch(time.time() if now_epoch is None else now_epoch, "now_epoch")
    if not all(callable(x) for x in (claim_reader, receipt_reader, head_reader)):
        raise AdmissionError("trusted readers required")

    # Read fresh claim, provider receipt and current revision. A failure to
    # contact any provider must fail closed; it must never become admission.
    try:
        # Snapshot provider values: an adapter may reuse a mutable dict.
        # Re-read the claim and head after the receipt read to detect lease
        # turnover/revocation or branch movement during the preflight window.
        claim = dict(_exact_record(claim_reader(p["resource_id"], p["claim_token"]),
                                   _CLAIM_FIELDS, "claim"))
        receipt = dict(_exact_record(receipt_reader(p["receipt_ref"]),
                                     _RECEIPT_FIELDS, "receipt"))
        observed_head = head_reader(p["resource_id"])
        confirmed_claim = dict(_exact_record(claim_reader(p["resource_id"], p["claim_token"]),
                                             _CLAIM_FIELDS, "confirmed claim"))
        confirmed_head = head_reader(p["resource_id"])
    except AdmissionError:
        raise
    except Exception as exc:
        raise AdmissionError("provider read unavailable") from exc

    if confirmed_claim != claim:
        raise AdmissionError("claim changed during preflight")
    if confirmed_head != observed_head:
        raise AdmissionError("head changed during preflight")
    # Live calls may outlast an initially valid lease or freshness window.
    # Re-check wall-clock time after all provider reads. An injected fixed
    # clock keeps synthetic tests deterministic; it cannot attest real time.
    now = _epoch(time.time() if now_epoch is None else now_epoch, "now_epoch")

    for key in ("task_key", "lane_id", "actor", "owner", "resource_id", "expected_head", "claim_token"):
        if claim[key] != p[key]:
            raise AdmissionError(f"claim {key} mismatch")
    if claim["state"] != "ACTIVE":
        raise AdmissionError("claim not active")
    fence = claim["fence"]
    if type(fence) is not int or fence <= 0:
        raise AdmissionError("claim fence invalid")
    issued_at = _epoch(claim["issued_at_epoch"], "claim issued_at")
    deadline = _epoch(claim["deadline_epoch"], "claim deadline")
    if deadline <= issued_at:
        raise AdmissionError("claim window invalid")
    if issued_at > now:
        raise AdmissionError("claim issued in future")
    if deadline <= now:
        raise AdmissionError("claim expired during preflight")

    for key in ("receipt_ref", "task_key", "lane_id", "actor", "owner", "resource_id"):
        if receipt[key] != p[key]:
            raise AdmissionError(f"receipt {key} mismatch")
    if receipt["state"] != "PROVIDER_VERIFIED":
        raise AdmissionError("receipt not provider-verified")
    if receipt["fence"] != fence or type(receipt["fence"]) is not int:
        raise AdmissionError("receipt fence mismatch")
    if receipt["head"] != p["expected_head"] or observed_head != p["expected_head"]:
        raise AdmissionError("stale or divergent provider revision")
    if not isinstance(receipt["evidence_sha256"], str) or not _DIGEST.fullmatch(receipt["evidence_sha256"]):
        raise AdmissionError("receipt evidence digest invalid")
    observed_at = _epoch(receipt["observed_at_epoch"], "receipt timestamp")
    if observed_at > now or now - observed_at > ttl:
        raise AdmissionError("receipt missing freshness")
    if observed_at < issued_at:
        raise AdmissionError("receipt predates claim")
    if observed_at >= deadline:
        raise AdmissionError("receipt outside claim window")

    return {"schema": SCHEMA, "state": "ADAPTER_ASSERTED_PREFLIGHT_ONLY",
            "task_key": p["task_key"], "lane_id": p["lane_id"],
            "resource_id": p["resource_id"], "observed_head": observed_head,
            "fence": fence, "evidence_sha256": receipt["evidence_sha256"],
            "proof_ceiling": "TRUSTED_ADAPTER_DEPENDENCY_NOT_PRODUCTION_EXECUTOR_FENCING"}
