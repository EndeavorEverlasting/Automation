from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

IR_SCHEMA = "document-formatting-ir/v1"
PLAN_SCHEMA = "document-formatting-google-docs-plan/v1"

SUPPORTED_FEATURES = {
    "semantic_headings",
    "internal_navigation",
    "named_external_links",
    "text_style",
    "paragraph_style",
    "bullet_lists",
    "tables",
    "inline_images",
    "revision_readback",
}

CAPABILITY_STATES = {
    "dynamic_page_fields": "READABLE_EXISTING_NOT_CREATABLE_VIA_CURRENT_BATCHUPDATE_SURFACE",
}


class GoogleDocsAdapterError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def capability_report(
    required_features: Sequence[str],
    accepted_degradations: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    normalized: list[str] = []
    for feature in required_features:
        if not isinstance(feature, str) or not feature.strip():
            raise GoogleDocsAdapterError(
                "GDA_FEATURE_INPUT",
                "required features must be non-empty strings",
            )
        value = feature.strip()
        if value not in normalized:
            normalized.append(value)

    policies: dict[str, dict[str, Any]] = {}
    for index, degradation in enumerate(accepted_degradations):
        if not isinstance(degradation, Mapping):
            raise GoogleDocsAdapterError(
                "GDA_DEGRADATION_POLICY",
                f"accepted_degradations[{index}] must be an object",
            )
        feature = degradation.get("feature")
        accepted_state = degradation.get("accepted_state")
        fallback = degradation.get("fallback_semantics")
        disclosure = degradation.get("disclosure_required")
        if not isinstance(feature, str) or not feature.strip():
            raise GoogleDocsAdapterError(
                "GDA_DEGRADATION_POLICY",
                f"accepted_degradations[{index}].feature must be non-empty",
            )
        feature = feature.strip()
        if feature not in normalized:
            raise GoogleDocsAdapterError(
                "GDA_DEGRADATION_POLICY",
                f"accepted degradation feature {feature!r} is not required",
            )
        if feature in policies:
            raise GoogleDocsAdapterError(
                "GDA_DEGRADATION_POLICY",
                f"duplicate accepted degradation for {feature!r}",
            )
        if not isinstance(accepted_state, str) or not accepted_state.strip():
            raise GoogleDocsAdapterError(
                "GDA_DEGRADATION_POLICY",
                f"accepted_degradations[{index}].accepted_state must be non-empty",
            )
        if not isinstance(fallback, str) or not fallback.strip():
            raise GoogleDocsAdapterError(
                "GDA_DEGRADATION_POLICY",
                f"accepted_degradations[{index}].fallback_semantics must be non-empty",
            )
        if not isinstance(disclosure, bool):
            raise GoogleDocsAdapterError(
                "GDA_DEGRADATION_POLICY",
                f"accepted_degradations[{index}].disclosure_required must be boolean",
            )
        policies[feature] = {
            "feature": feature,
            "accepted_state": accepted_state.strip(),
            "disclosure_required": disclosure,
            "fallback_semantics": fallback.strip(),
        }

    supported = sorted(feature for feature in normalized if feature in SUPPORTED_FEATURES)
    unavailable = sorted(feature for feature in normalized if feature not in SUPPORTED_FEATURES)
    accepted: list[dict[str, Any]] = []
    blocked: list[str] = []
    detail: dict[str, str] = {}
    for feature in unavailable:
        observed_state = CAPABILITY_STATES.get(feature, "UNSUPPORTED_BY_PROTOTYPE")
        detail[feature] = observed_state
        policy = policies.get(feature)
        known_provider_state = feature in CAPABILITY_STATES
        if (
            known_provider_state
            and policy
            and policy["accepted_state"] == observed_state
        ):
            accepted.append({**policy, "observed_state": observed_state})
        else:
            blocked.append(feature)

    if blocked:
        state = "BLOCKED_UNSUPPORTED_FEATURE"
    elif accepted:
        state = "READY_WITH_ACCEPTED_DEGRADATION"
    else:
        state = "READY"

    return {
        "provider_id": "google-docs",
        "required_features": normalized,
        "supported_features": supported,
        "unsupported_features": unavailable,
        "unsupported_detail": detail,
        "accepted_degradations": accepted,
        "blocked_features": blocked,
        "state": state,
    }

def _require_text(value: Any, *, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GoogleDocsAdapterError("GDA_IR_SCHEMA", f"{path} must be non-empty text")
    return value


def validate_ir(ir: Any) -> None:
    if not isinstance(ir, Mapping) or ir.get("schema_version") != IR_SCHEMA:
        raise GoogleDocsAdapterError(
            "GDA_IR_SCHEMA",
            f"IR schema must be {IR_SCHEMA!r}",
        )
    blocks = ir.get("blocks")
    if not isinstance(blocks, list) or not blocks:
        raise GoogleDocsAdapterError("GDA_IR_SCHEMA", "IR blocks must be a non-empty array")

    for index, block in enumerate(blocks):
        path = f"blocks[{index}]"
        if not isinstance(block, Mapping):
            raise GoogleDocsAdapterError("GDA_IR_SCHEMA", f"{path} must be an object")
        kind = _require_text(block.get("kind"), path=f"{path}.kind")
        _require_text(block.get("component"), path=f"{path}.component")
        style = block.get("style")
        if not isinstance(style, Mapping):
            raise GoogleDocsAdapterError("GDA_IR_SCHEMA", f"{path}.style must be an object")
        _require_text(style.get("role_id"), path=f"{path}.style.role_id")
        if not isinstance(style.get("mechanics"), Mapping):
            raise GoogleDocsAdapterError(
                "GDA_IR_SCHEMA", f"{path}.style.mechanics must be an object"
            )
        if not isinstance(style.get("colors"), Mapping):
            raise GoogleDocsAdapterError(
                "GDA_IR_SCHEMA", f"{path}.style.colors must be an object"
            )

        if kind in {"heading", "text"}:
            _require_text(block.get("text"), path=f"{path}.text")
            continue
        if kind == "metadata":
            _require_text(block.get("label"), path=f"{path}.label")
            _require_text(block.get("value"), path=f"{path}.value")
            continue
        if kind == "bullet_list":
            items = block.get("items")
            if not isinstance(items, list) or not items:
                raise GoogleDocsAdapterError(
                    "GDA_IR_SCHEMA", f"{path}.items must be a non-empty array"
                )
            for item_index, item in enumerate(items):
                _require_text(item, path=f"{path}.items[{item_index}]")
            continue
        if kind == "table":
            headers = block.get("headers")
            rows = block.get("rows")
            if not isinstance(headers, list) or not headers:
                raise GoogleDocsAdapterError(
                    "GDA_IR_SCHEMA", f"{path}.headers must be a non-empty array"
                )
            for header_index, header in enumerate(headers):
                _require_text(header, path=f"{path}.headers[{header_index}]")
            if not isinstance(rows, list):
                raise GoogleDocsAdapterError(
                    "GDA_IR_SCHEMA", f"{path}.rows must be an array"
                )
            for row_index, row in enumerate(rows):
                if not isinstance(row, list) or len(row) != len(headers):
                    raise GoogleDocsAdapterError(
                        "GDA_IR_SCHEMA",
                        f"{path}.rows[{row_index}] must contain {len(headers)} cells",
                    )
                for col_index, cell in enumerate(row):
                    _require_text(cell, path=f"{path}.rows[{row_index}][{col_index}]")
            continue
        if kind == "image":
            _require_text(block.get("asset_ref"), path=f"{path}.asset_ref")
            _require_text(block.get("alt_text"), path=f"{path}.alt_text")
            caption = block.get("caption")
            if caption is not None:
                _require_text(caption, path=f"{path}.caption")
            continue
        if kind == "link":
            _require_text(block.get("label"), path=f"{path}.label")
            link_type = block.get("link_type")
            if link_type == "external":
                _require_text(block.get("resource_url"), path=f"{path}.resource_url")
                continue
            if link_type == "internal":
                _require_text(
                    block.get("target_section_id"),
                    path=f"{path}.target_section_id",
                )
                continue
            raise GoogleDocsAdapterError(
                "GDA_IR_SCHEMA",
                f"{path}.link_type must be 'internal' or 'external'",
            )
        raise GoogleDocsAdapterError(
            "GDA_IR_SCHEMA",
            f"{path}.kind is unsupported: {kind!r}",
        )


def _operation_for_block(block: Mapping[str, Any]) -> list[dict[str, Any]]:
    kind = block["kind"]
    logical_id = block.get("anchor_id") or block.get("section_id")
    base = {
        "component": block["component"],
        "style": block["style"],
    }
    if logical_id:
        base["logical_id"] = logical_id

    if kind == "heading":
        return [{
            "operation": "insert_heading",
            **base,
            "text": block["text"],
            "heading_level": block.get("level"),
        }]
    if kind in {"text", "metadata"}:
        payload = {"operation": "insert_text", **base}
        payload["text"] = (
            f"{block['label']}: {block['value']}"
            if kind == "metadata"
            else block["text"]
        )
        return [payload]
    if kind == "bullet_list":
        return [{
            "operation": "insert_bullet_list",
            **base,
            "items": list(block["items"]),
        }]
    if kind == "table":
        return [{
            "operation": "insert_table",
            **base,
            "headers": list(block["headers"]),
            "rows": [list(row) for row in block["rows"]],
        }]
    if kind == "image":
        payload = {
            "operation": "insert_inline_image",
            **base,
            "asset_ref": block["asset_ref"],
            "alt_text": block["alt_text"],
        }
        if block.get("caption") is not None:
            payload["caption"] = block["caption"]
        return [payload]
    if kind == "link":
        if block.get("link_type") == "external":
            return [{
                "operation": "insert_external_link",
                **base,
                "label": block["label"],
                "url": block["resource_url"],
            }]
        if block.get("link_type") == "internal":
            return [{
                "operation": "reserve_internal_link",
                **base,
                "label": block["label"],
                "target_logical_id": block["target_section_id"],
            }]
    raise GoogleDocsAdapterError(
        "GDA_IR_BLOCK",
        f"unsupported IR block: kind={kind!r}",
    )


def build_plan(
    ir: Mapping[str, Any],
    *,
    required_features: Sequence[str],
    accepted_degradations: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    validate_ir(ir)

    capability = capability_report(
        required_features,
        accepted_degradations=accepted_degradations,
    )
    if capability["blocked_features"]:
        detail = ", ".join(
            f"{name}={capability['unsupported_detail'][name]}"
            for name in capability["blocked_features"]
        )
        raise GoogleDocsAdapterError(
            "GDA_UNSUPPORTED_FEATURE",
            f"Google Docs adapter cannot satisfy required features: {detail}",
        )

    phase1: list[dict[str, Any]] = []
    internal_links: list[dict[str, Any]] = []
    for source_order, block in enumerate(ir["blocks"]):
        for operation in _operation_for_block(block):
            if operation["operation"] == "reserve_internal_link":
                placeholder_id = f"internal-link-{source_order:04d}"
                phase1.append(
                    {
                        "operation": "insert_internal_link_placeholder",
                        "source_order": source_order,
                        "placeholder_id": placeholder_id,
                        "component": operation["component"],
                        "style": operation["style"],
                        "label": operation["label"],
                    }
                )
                internal_links.append(
                    {
                        "operation": "bind_internal_link",
                        "placeholder_id": placeholder_id,
                        "component": operation["component"],
                        "style": operation["style"],
                        "label": operation["label"],
                        "target_logical_id": operation["target_logical_id"],
                    }
                )
            else:
                phase1.append({"source_order": source_order, **operation})

    phases: list[dict[str, Any]] = [{
        "phase_id": "CONSTRUCT_AND_STYLE",
        "requires_revision_control": True,
        "operations": phase1,
        "proof_ceiling": "PROVIDER_MUTATION_PLANNED_NOT_EXECUTED",
    }]
    if internal_links:
        phases.append({
            "phase_id": "RESOLVE_HEADING_IDENTITIES",
            "depends_on": ["CONSTRUCT_AND_STYLE"],
            "operation": "provider_readback",
            "readback_fields": [
                "revisionId",
                "heading identities",
                "internal link placeholder ranges",
                "body structure",
            ],
            "proof_ceiling": "HEADING_IDENTITIES_PLANNED_NOT_OBSERVED",
        })
        phases.append({
            "phase_id": "APPLY_INTERNAL_LINKS",
            "depends_on": ["RESOLVE_HEADING_IDENTITIES"],
            "requires_revision_control": True,
            "operations": internal_links,
            "proof_ceiling": "INTERNAL_LINK_MUTATION_PLANNED_NOT_EXECUTED",
        })
    phases.append({
        "phase_id": "FINAL_READBACK",
        "depends_on": [phases[-1]["phase_id"]],
        "operation": "provider_readback",
        "readback_fields": ["revisionId", "body structure", "paragraph styles", "links", "inline objects"],
        "proof_ceiling": "READBACK_PLANNED_NOT_OBSERVED",
    })

    plan = {
        "schema_version": PLAN_SCHEMA,
        "provider_id": "google-docs",
        "source_ir_sha256": sha256_json(ir),
        "capability_report": capability,
        "required_disclosures": [
            {
                "feature": item["feature"],
                "observed_state": item["observed_state"],
                "fallback_semantics": item["fallback_semantics"],
            }
            for item in capability["accepted_degradations"]
            if item["disclosure_required"]
        ],
        "phases": phases,
        "state": "ADAPTER_PLAN_READY",
        "proof_ceiling": (
            "PROVIDER_REQUEST_PLAN_ONLY; no Google Docs mutation/readback or visual "
            "acceptance is implied"
        ),
    }
    plan["plan_sha256"] = sha256_json({**plan, "plan_sha256": ""})
    return plan

#!/usr/bin/env python3
import argparse
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "document_formatting_google_docs_adapter",
    Path(__file__).resolve(),
)
# This file is both library and CLI; main() below calls build_plan directly.


def _load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))



def _load_degradation_policy(path: str | None) -> list[dict[str, Any]]:
    if not path:
        return []
    payload = _load(path)
    if not isinstance(payload, list):
        raise GoogleDocsAdapterError(
            "GDA_DEGRADATION_POLICY",
            "degradation policy file must contain a JSON array",
        )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Translate document-formatting IR into a Google Docs provider plan."
    )
    parser.add_argument("--ir", required=True)
    parser.add_argument("--required-feature", action="append", default=[])
    parser.add_argument("--degradation-policy")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    try:
        ir = _load(args.ir)
        degradation_policy = _load_degradation_policy(args.degradation_policy)
    except FileNotFoundError as exc:
        print(f"GDA_INPUT_IO: file not found: {exc.filename}", file=sys.stderr)
        return 2
    except (OSError, UnicodeError) as exc:
        print(f"GDA_INPUT_IO: {exc}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(
            f"GDA_INPUT_JSON: invalid JSON at line {exc.lineno} column {exc.colno}",
            file=sys.stderr,
        )
        return 2
    except GoogleDocsAdapterError as exc:
        print(f"{exc.code}: {exc}", file=sys.stderr)
        return 2

    try:
        plan = build_plan(
            ir,
            required_features=args.required_feature,
            accepted_degradations=degradation_policy,
        )
    except GoogleDocsAdapterError as exc:
        print(f"{exc.code}: {exc}", file=sys.stderr)
        return 2

    path = Path(args.output)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(plan, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        print(f"GDA_OUTPUT_IO: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
