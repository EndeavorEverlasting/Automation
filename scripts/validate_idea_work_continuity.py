#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "harness" / "contracts" / "idea-work-continuity.v1.json"


class ContinuityValidationError(ValueError):
    pass


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ContinuityValidationError(f"{path} must contain a JSON object")
    return value


def _walk_strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _walk_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_strings(item)


def validate_receipt(receipt: dict[str, Any], contract: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    if receipt.get("schema_version") != contract["receipt_schema_version"]:
        errors.append("schema_version must match the contract receipt schema")

    for field in contract["required_fields"]:
        if field not in receipt:
            errors.append(f"missing required field: {field}")

    if errors:
        return errors

    source = receipt.get("source")
    plan = receipt.get("existing_remote_plan")
    target = receipt.get("target")
    anchor = receipt.get("durable_anchor")
    priority = receipt.get("priority")

    if not isinstance(source, dict):
        errors.append("source must be an object")
        source = {}
    if not isinstance(plan, dict):
        errors.append("existing_remote_plan must be an object")
        plan = {}
    if not isinstance(target, dict):
        errors.append("target must be an object")
        target = {}
    if not isinstance(anchor, dict):
        errors.append("durable_anchor must be an object")
        anchor = {}
    if not isinstance(priority, dict):
        errors.append("priority must be an object")
        priority = {}

    if source.get("state") not in contract["source_states"]:
        errors.append("source.state is unsupported")
    if source.get("raw_content_persisted") is not False:
        errors.append("source.raw_content_persisted must be false")
    digest = source.get("content_sha256")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        errors.append("source.content_sha256 must be a lowercase 64-hex SHA-256")
    for field in ("semantic_source", "item_identity_handle"):
        if not isinstance(source.get(field), str) or not source[field].strip():
            errors.append(f"source.{field} must be a non-empty string")

    if plan.get("state") not in contract["existing_plan_states"]:
        errors.append("existing_remote_plan.state is unsupported")
    if target.get("consumer_state") not in contract["consumer_states"]:
        errors.append("target.consumer_state is unsupported")
    if target.get("collision_state") not in contract["collision_states"]:
        errors.append("target.collision_state is unsupported")
    if not isinstance(target.get("semantic_owner"), str) or not target["semantic_owner"].strip():
        errors.append("target.semantic_owner must be a non-empty string")

    disposition = receipt.get("disposition")
    if disposition not in contract["dispositions"]:
        errors.append("disposition is unsupported")
    if anchor.get("type") not in contract["durable_anchor_types"]:
        errors.append("durable_anchor.type is unsupported")
    if not isinstance(anchor.get("identity"), str) or not anchor["identity"].strip():
        errors.append("durable_anchor.identity must be a non-empty string")

    execution_relevant = receipt.get("execution_relevant")
    if not isinstance(execution_relevant, bool):
        errors.append("execution_relevant must be boolean")
    elif execution_relevant:
        if disposition == "NO_EXECUTION_OBLIGATION":
            errors.append("execution-relevant ideas cannot use NO_EXECUTION_OBLIGATION")
        if anchor.get("type") == "NO_ACTION":
            errors.append("execution-relevant ideas require a durable non-NO_ACTION anchor")
    else:
        if disposition != "NO_EXECUTION_OBLIGATION":
            errors.append("non-execution-relevant ideas must use NO_EXECUTION_OBLIGATION")
        if anchor.get("type") != "NO_ACTION":
            errors.append("non-execution-relevant ideas must use durable_anchor.type=NO_ACTION")

    plan_state = plan.get("state")
    if plan_state == "FOUND":
        if not isinstance(plan.get("canonical_owner"), str) or not plan["canonical_owner"].strip():
            errors.append("FOUND plan requires canonical_owner")
        if not isinstance(plan.get("anchor"), str) or not plan["anchor"].strip():
            errors.append("FOUND plan requires anchor")
        if disposition == "CREATE_REMOTE_PLAN":
            errors.append("CREATE_REMOTE_PLAN is forbidden when an existing canonical plan is FOUND")
    if plan_state == "NOT_FOUND" and disposition in {"MIRROR_EXISTING_PLAN", "APPEND_ITERATION"}:
        errors.append(f"{disposition} requires an existing canonical plan")

    consumer_state = target.get("consumer_state")
    collision_state = target.get("collision_state")
    if (
        execution_relevant is True
        and consumer_state in {"MIGRATION_ACTIVE", "CONVERGENCE_ACTIVE"}
        and collision_state != "CLEAR"
        and disposition != "DEFERRED_ADOPTION"
    ):
        errors.append(
            "migration/convergence-active consumer with non-clear collision state must use DEFERRED_ADOPTION"
        )

    expected_anchor = {
        "MIRROR_EXISTING_PLAN": "EXISTING_PLAN",
        "APPEND_ITERATION": "PLAN_ITERATION",
        "CREATE_REMOTE_PLAN": "NEW_PLAN",
        "DEFERRED_ADOPTION": "DEFERRED_ADOPTION",
        "BLOCKED_OWNER_RESOLUTION": "DEFERRED_ADOPTION",
        "NO_EXECUTION_OBLIGATION": "NO_ACTION",
    }.get(disposition)
    if expected_anchor and anchor.get("type") != expected_anchor:
        errors.append(
            f"disposition {disposition} requires durable_anchor.type={expected_anchor}"
        )

    priority_source = priority.get("source")
    if priority_source not in {"OPERATOR", "UNSPECIFIED"}:
        errors.append("priority.source must be OPERATOR or UNSPECIFIED")
    if priority_source == "UNSPECIFIED" and priority.get("value") is not None:
        errors.append("UNSPECIFIED priority must have value=null")
    if priority_source == "OPERATOR" and priority.get("value") in (None, ""):
        errors.append("OPERATOR priority requires an explicit value")

    next_transition = receipt.get("next_transition")
    if not isinstance(next_transition, str) or not next_transition.strip():
        errors.append("next_transition must be a non-empty string")

    evidence_refs = receipt.get("evidence_refs")
    if not isinstance(evidence_refs, list) or not evidence_refs or not all(
        isinstance(item, str) and item.strip() for item in evidence_refs
    ):
        errors.append("evidence_refs must be a non-empty string list")

    if not isinstance(receipt.get("proof_ceiling"), str) or not receipt["proof_ceiling"].strip():
        errors.append("proof_ceiling must be a non-empty string")

    for pattern in contract["privacy"]["forbidden_string_patterns"]:
        for text in _walk_strings(receipt):
            if pattern.lower() in text.lower():
                errors.append(f"privacy violation: forbidden string pattern {pattern!r}")
                break

    return sorted(set(errors))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate idea-work-continuity receipts")
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--output")
    args = parser.parse_args(argv)

    contract = _load_json(CONTRACT_PATH)
    receipt = _load_json(Path(args.receipt))
    errors = validate_receipt(receipt, contract)
    result = {
        "schema_version": "idea-work-continuity-validation/v1",
        "receipt": args.receipt,
        "state": "PASS" if not errors else "FAIL",
        "errors": errors,
        "proof_ceiling": "Deterministic contract validation only; no provider mutation or consumer adoption is proven."
    }

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(result, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
