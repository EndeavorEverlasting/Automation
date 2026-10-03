from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = ROOT / "harness/contracts/runtime-execution-handoff.v1.json"


def _walk(value: Any, path: str = "$"):
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            yield child_path, key, child
            yield from _walk(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            child_path = f"{path}[{index}]"
            yield child_path, None, child
            yield from _walk(child, child_path)


def _has_meaningful_content(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, dict):
        return bool(value) and all(
            isinstance(key, str)
            and bool(key.strip())
            and _has_meaningful_content(child)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return bool(value) and all(_has_meaningful_content(child) for child in value)
    return value is not None


def validate_packet(
    packet: Any,
    contract: dict[str, Any],
    *,
    require_ready: bool = False,
) -> list[str]:
    errors: list[str] = []

    if not isinstance(packet, dict):
        return ["packet root must be a JSON object"]

    if packet.get("schema_version") != contract["packet_schema_version"]:
        errors.append(
            "schema_version must be "
            + repr(contract["packet_schema_version"])
        )

    for field in contract["required_fields"]:
        if field not in packet:
            errors.append(f"missing required field: {field}")

    for field in contract["nonempty_string_fields"]:
        value = packet.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{field} must be a non-empty string")

    for field in contract["list_fields"]:
        value = packet.get(field)
        if value is not None and not isinstance(value, list):
            errors.append(f"{field} must be a list")

    for field in contract["nonempty_list_fields"]:
        value = packet.get(field)
        if not isinstance(value, list) or not value:
            errors.append(f"{field} must be a non-empty list")

    for field in contract["string_list_fields"]:
        value = packet.get(field)
        if not isinstance(value, list):
            continue
        for index, item in enumerate(value):
            if not isinstance(item, str) or not item.strip():
                errors.append(
                    f"{field}[{index}] must be a non-empty string"
                )

    evidence_inputs = packet.get("evidence_inputs")
    if isinstance(evidence_inputs, list):
        required_evidence_fields = contract["evidence_input_required_fields"]
        for index, item in enumerate(evidence_inputs):
            if not isinstance(item, dict) or not item:
                errors.append(
                    f"evidence_inputs[{index}] must be a non-empty object"
                )
                continue
            for field in required_evidence_fields:
                value = item.get(field)
                if not isinstance(value, str) or not value.strip():
                    errors.append(
                        f"evidence_inputs[{index}].{field} must be a non-empty string"
                    )
            if not _has_meaningful_content(item):
                errors.append(
                    f"evidence_inputs[{index}] must contain meaningful non-null data"
                )

    state = packet.get("packet_state")
    if state not in contract["packet_states"]:
        errors.append(
            "packet_state must be one of "
            + ", ".join(contract["packet_states"])
        )

    environment = packet.get("execution_environment")
    if environment not in contract["execution_environments"]:
        errors.append(
            "execution_environment must be one of "
            + ", ".join(contract["execution_environments"])
        )

    if require_ready and state != "READY":
        errors.append("packet_state must be READY when --require-ready is used")

    if (
        state == "READY"
        and contract["ready_rules"]["forbid_unknown_runtime"]
        and environment == "UNKNOWN_RUNTIME"
    ):
        errors.append("READY packet cannot use UNKNOWN_RUNTIME")

    privacy = contract["privacy"]
    forbidden_keys = tuple(
        fragment.lower() for fragment in privacy["forbidden_key_fragments"]
    )
    forbidden_patterns = tuple(
        pattern.lower() for pattern in privacy["forbidden_string_patterns"]
    )
    forbidden_regexes = [
        re.compile(pattern) for pattern in privacy["forbidden_string_regexes"]
    ]

    for path, key, value in _walk(packet):
        if key is not None:
            lower_key = str(key).lower()
            for fragment in forbidden_keys:
                if fragment in lower_key:
                    errors.append(
                        f"privacy violation at {path}: forbidden key fragment {fragment!r}"
                    )
                    break

        if isinstance(value, str):
            lower_value = value.lower()
            for pattern in forbidden_patterns:
                if pattern in lower_value:
                    errors.append(
                        f"privacy violation at {path}: forbidden locator pattern {pattern!r}"
                    )
            for regex in forbidden_regexes:
                if regex.search(value):
                    errors.append(
                        f"privacy violation at {path}: forbidden path pattern {regex.pattern!r}"
                    )

    return errors


def _write_receipt(receipt: dict[str, Any], output: Path | None) -> None:
    serialized = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialized, encoding="utf-8")
    else:
        sys.stdout.write(serialized)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", required=True, type=Path)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args()

    contract = json.loads(args.contract.read_text(encoding="utf-8"))

    try:
        packet = json.loads(args.packet.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        receipt = {
            "schema_version": "automation-runtime-handoff-validation-receipt/v1",
            "packet_schema_version": None,
            "contract_schema_version": contract.get("schema_version"),
            "state": "FAIL",
            "errors": [f"packet read/JSON error: {exc}"],
        }
        _write_receipt(receipt, args.output)
        return 2

    errors = validate_packet(
        packet,
        contract,
        require_ready=args.require_ready,
    )
    packet_schema_version = (
        packet.get("schema_version") if isinstance(packet, dict) else None
    )
    receipt = {
        "schema_version": "automation-runtime-handoff-validation-receipt/v1",
        "packet_schema_version": packet_schema_version,
        "contract_schema_version": contract.get("schema_version"),
        "state": "PASS" if not errors else "FAIL",
        "errors": errors,
    }
    _write_receipt(receipt, args.output)
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
