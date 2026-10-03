from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = ROOT / "harness/contracts/artifact-continuity-preflight.v1.json"

def _walk(value: Any, path: str = "$"):
    if isinstance(value, dict):
        for key, child in value.items():
            p = f"{path}.{key}"
            yield p, str(key), child
            yield from _walk(child, p)
    elif isinstance(value, list):
        for i, child in enumerate(value):
            p = f"{path}[{i}]"
            yield p, "", child
            yield from _walk(child, p)

def validate_packet(packet: Any, contract: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(packet, dict):
        return ["packet root must be a JSON object"]
    if packet.get("schema_version") != contract["packet_schema_version"]:
        errors.append(f"schema_version must be {contract['packet_schema_version']!r}")
    for field in contract["required_fields"]:
        if field not in packet:
            errors.append(f"missing required field: {field}")

    enum_fields = {
        "artifact_action":"artifact_actions","execution_environment":"execution_environments",
        "exact_source_binding_state":"exact_source_binding_states","provider_access_state":"provider_access_states",
        "provider_write_state":"provider_write_states","local_output_role":"local_output_roles",
        "provider_link_policy":"provider_link_policies","sync_obligation":"sync_obligations","result_state":"result_states"
    }
    for field, owner in enum_fields.items():
        if field in packet and packet[field] not in contract[owner]:
            errors.append(f"{field} must be one of {', '.join(contract[owner])}")

    dims = packet.get("required_fidelity_dimensions")
    allowed_dims = set(contract["fidelity_dimensions"])
    if not isinstance(dims, list) or not dims:
        errors.append("required_fidelity_dimensions must be a non-empty list")
        dims_set = set()
    else:
        dims_set = set(dims)
        unknown = dims_set - allowed_dims
        if unknown:
            errors.append(f"required_fidelity_dimensions contains unsupported values: {', '.join(sorted(unknown))}")
        if len(dims) != len(dims_set):
            errors.append("required_fidelity_dimensions must not contain duplicates")

    action = packet.get("artifact_action")
    if action == "format" and "presentation" not in dims_set:
        errors.append("format action requires presentation fidelity")
    if action == "edit" and "content" not in dims_set:
        errors.append("edit action requires content fidelity")

    for field in ("work_unit_id","artifact_semantic_id","proof_ceiling"):
        if not isinstance(packet.get(field), str) or not packet[field].strip():
            errors.append(f"{field} must be a non-empty string")
    if not isinstance(packet.get("known_provider_source"), bool):
        errors.append("known_provider_source must be boolean")

    fk = tuple(x.lower() for x in contract["privacy"]["forbidden_key_fragments"])
    fv = tuple(x.lower() for x in contract["privacy"]["forbidden_string_patterns"])
    for path, key, value in _walk(packet):
        if any(x in key.lower() for x in fk):
            errors.append(f"privacy violation at {path}: forbidden provider/private key")
        if isinstance(value, str) and any(x in value.lower() for x in fv):
            errors.append(f"privacy violation at {path}: raw provider locator")

    known=packet.get("known_provider_source"); exact=packet.get("exact_source_binding_state")
    access=packet.get("provider_access_state"); write=packet.get("provider_write_state")
    role=packet.get("local_output_role"); link=packet.get("provider_link_policy")
    obligation=packet.get("sync_obligation"); state=packet.get("result_state")

    if known is True:
        if link != "PRIMARY_WHEN_AVAILABLE":
            errors.append("known provider source requires provider_link_policy=PRIMARY_WHEN_AVAILABLE")
        if exact != "RESOLVED":
            if state != "BLOCKED_SOURCE_RESOLUTION": errors.append("known unresolved provider source must be BLOCKED_SOURCE_RESOLUTION")
            if obligation != "PENDING_SOURCE_RESOLUTION": errors.append("known unresolved provider source requires PENDING_SOURCE_RESOLUTION")
            if role == "CANONICAL_NEW_ARTIFACT": errors.append("cannot create CANONICAL_NEW_ARTIFACT while known provider identity is unresolved")
        elif access == "AVAILABLE":
            if role == "CANONICAL_NEW_ARTIFACT": errors.append("resolved accessible provider source cannot degrade to CANONICAL_NEW_ARTIFACT")
            if action in {"edit","format"} and write == "AUTHORIZED":
                if state != "READY_PROVIDER_FIRST": errors.append("authorized provider edit/format must be READY_PROVIDER_FIRST")
                if obligation != "NONE_PENDING": errors.append("authorized provider edit/format must not start with a pending sync obligation")
            elif action in {"edit","format"} and write != "AUTHORIZED":
                if state != "BLOCKED_PROVIDER_WRITE": errors.append("provider edit/format without write authority must be BLOCKED_PROVIDER_WRITE")
        elif access in {"BLOCKED","UNAVAILABLE","UNKNOWN"}:
            if state not in {"READY_LOCAL_WITH_SYNC_OBLIGATION","BLOCKED_PROVIDER_ACCESS"}:
                errors.append("unavailable provider must block or carry a local sync obligation")
            if state == "READY_LOCAL_WITH_SYNC_OBLIGATION" and obligation != "PENDING_PROVIDER_SYNC":
                errors.append("local continuation with unavailable provider requires PENDING_PROVIDER_SYNC")
            if role == "CANONICAL_NEW_ARTIFACT": errors.append("provider unavailability does not authorize a duplicate canonical artifact")
    elif known is False:
        if exact != "NOT_APPLICABLE": errors.append("no provider source requires exact_source_binding_state=NOT_APPLICABLE")
        if link != "NOT_APPLICABLE": errors.append("no provider source requires provider_link_policy=NOT_APPLICABLE")
        if state != "READY_NO_PROVIDER_SOURCE": errors.append("no provider source requires READY_NO_PROVIDER_SOURCE")
    return errors

def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument("--packet",required=True,type=Path); p.add_argument("--contract",type=Path,default=DEFAULT_CONTRACT); a=p.parse_args()
    try:
        packet=json.loads(a.packet.read_text(encoding="utf-8")); contract=json.loads(a.contract.read_text(encoding="utf-8"))
    except (OSError,json.JSONDecodeError) as exc:
        print(json.dumps({"state":"FAIL","errors":[str(exc)]},indent=2)); return 2
    errors=validate_packet(packet,contract)
    print(json.dumps({"schema_version":"automation-artifact-continuity-preflight-validation/v1","state":"PASS" if not errors else "FAIL","errors":errors},indent=2,sort_keys=True))
    return 0 if not errors else 2

if __name__ == "__main__": raise SystemExit(main())
