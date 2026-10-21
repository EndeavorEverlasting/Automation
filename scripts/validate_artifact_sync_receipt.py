from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT=ROOT/"capabilities/artifact-sync/schemas/receipt.v1.json"

def validate_receipt(receipt:Any, contract:dict[str,Any])->list[str]:
    errors=[]
    if not isinstance(receipt,dict): return ["receipt root must be a JSON object"]
    if receipt.get("schema_version")!=contract["schema_version"]: errors.append(f"schema_version must be {contract['schema_version']!r}")
    for field in contract["required_fields"]:
        if field not in receipt: errors.append(f"missing required field: {field}")
    if receipt.get("operation") not in contract["operations"]: errors.append("operation is unsupported")
    if receipt.get("artifact_action") not in contract["artifact_actions"]: errors.append("artifact_action is unsupported")
    if receipt.get("state") not in contract["states"]: errors.append("state is unsupported")

    allowed=set(contract["fidelity_dimensions"])
    req=receipt.get("required_fidelity_dimensions"); ver=receipt.get("verified_fidelity_dimensions")
    if not isinstance(req,list) or not req: errors.append("required_fidelity_dimensions must be a non-empty list"); req_set=set()
    else:
        req_set=set(req)
        if req_set-allowed: errors.append("required_fidelity_dimensions contains unsupported values")
        if len(req)!=len(req_set): errors.append("required_fidelity_dimensions must not contain duplicates")
    if not isinstance(ver,list): errors.append("verified_fidelity_dimensions must be a list"); ver_set=set()
    else:
        ver_set=set(ver)
        if ver_set-allowed: errors.append("verified_fidelity_dimensions contains unsupported values")
        if len(ver)!=len(ver_set): errors.append("verified_fidelity_dimensions must not contain duplicates")

    action=receipt.get("artifact_action"); state=receipt.get("state"); op=receipt.get("operation")
    if action=="format" and "presentation" not in req_set:
        errors.append("format action requires presentation fidelity")
    if action=="edit" and "content" not in req_set:
        errors.append("edit action requires content fidelity")
    if state=="SYNCED":
        missing=req_set-ver_set
        if missing: errors.append("SYNCED receipt is missing verified fidelity dimensions: "+", ".join(sorted(missing)))
        if op in {"push","reconcile"}:
            if receipt.get("provider_write_performed") is not True: errors.append("provider-bound SYNCED push/reconcile requires provider_write_performed=true")
            if receipt.get("read_back_verified") is not True: errors.append("provider-bound SYNCED push/reconcile requires read_back_verified=true")
        if action=="format" and "presentation" not in ver_set:
            errors.append("formatted authoritative artifact cannot be SYNCED without verified presentation fidelity")
    for field in ("provider_freshness_checked","baseline_checked","conflict_checked","provider_write_performed","read_back_verified"):
        if not isinstance(receipt.get(field),bool): errors.append(f"{field} must be boolean")
    if not isinstance(receipt.get("proof_ceiling"),str) or not receipt["proof_ceiling"].strip(): errors.append("proof_ceiling must be a non-empty string")
    return errors

def main()->int:
    p=argparse.ArgumentParser(); p.add_argument("--receipt",required=True,type=Path); p.add_argument("--contract",type=Path,default=DEFAULT_CONTRACT); a=p.parse_args()
    try:
        r=json.loads(a.receipt.read_text(encoding="utf-8")); c=json.loads(a.contract.read_text(encoding="utf-8"))
    except (OSError,json.JSONDecodeError) as exc:
        print(json.dumps({"state":"FAIL","errors":[str(exc)]},indent=2)); return 2
    e=validate_receipt(r,c)
    print(json.dumps({"schema_version":"artifact-sync-receipt-validation/v1","state":"PASS" if not e else "FAIL","errors":e},indent=2,sort_keys=True))
    return 0 if not e else 2
if __name__=="__main__": raise SystemExit(main())
