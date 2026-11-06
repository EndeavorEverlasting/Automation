from __future__ import annotations
import argparse, json, re
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT=ROOT/"capabilities/artifact-sync/schemas/binding.v1.json"

def _req(obj:Any, fields:list[str], prefix:str, errors:list[str]):
    if not isinstance(obj,dict): errors.append(f"{prefix} must be an object"); return
    for field in fields:
        if field not in obj: errors.append(f"{prefix} missing required field: {field}")

def _check_handle(value: Any, name: str, errors: list[str]) -> None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{name} must be a non-empty string handle")
        return
    drive_like = "://" in value
    absolute_like = value.startswith("/") or value.startswith("\\")
    windows_like = len(value) > 2 and value[1] == ":" and value[2] in ("/", "\\")
    if drive_like or absolute_like or windows_like:
        errors.append(f"{name} must not be a URL or absolute path")

def validate_binding(binding:Any, contract:dict[str,Any])->list[str]:
    errors=[]
    if not isinstance(binding,dict): return ["binding root must be a JSON object"]
    if binding.get("schema_version")!=contract["schema_version"]: errors.append(f"schema_version must be {contract['schema_version']!r}")
    _req(binding,contract["required_fields"],"binding",errors)
    if binding.get("artifact_kind") not in contract["artifact_kinds"]: errors.append("artifact_kind is unsupported")
    if binding.get("authority") not in contract["authority_states"]: errors.append("authority is unsupported")
    provider=binding.get("provider"); _req(provider,contract["provider_required_fields"],"provider",errors)
    if isinstance(provider,dict):
        _check_handle(provider.get("locator_handle"), "provider.locator_handle", errors)
        if provider.get("locator_resolution")!="private_runtime_only": errors.append("provider.locator_resolution must be private_runtime_only")
    baseline=binding.get("baseline_state"); _req(baseline,contract["baseline_state_required_fields"],"baseline_state",errors)
    if isinstance(baseline,dict):
        _check_handle(baseline.get("state_handle"), "baseline_state.state_handle", errors)
        if baseline.get("state_resolution")!="private_runtime_only": errors.append("baseline_state.state_resolution must be private_runtime_only")
    if binding.get("authority") in contract["local_side_required_when"]:
        local=binding.get("local_side"); _req(local,contract["local_side_required_fields"],"local_side",errors)
        if isinstance(local,dict):
            _check_handle(local.get("locator_handle"), "local_side.locator_handle", errors)
            if local.get("locator_resolution")!="private_runtime_only": errors.append("local_side.locator_resolution must be private_runtime_only")
    material=binding.get("local_materialization"); _req(material,contract["local_materialization_required_fields"],"local_materialization",errors)
    if isinstance(material,dict):
        mode=material.get("mode"); retain=material.get("retain_after_success"); budget=material.get("max_retained_bytes")
        if mode not in contract["local_materialization_modes"]: errors.append("local_materialization.mode is unsupported")
        if not isinstance(retain,bool): errors.append("local_materialization.retain_after_success must be boolean")
        if not isinstance(budget,int) or budget<0: errors.append("local_materialization.max_retained_bytes must be a non-negative integer")
        if mode=="ephemeral" and (retain is not False or budget!=0): errors.append("ephemeral materialization requires retain_after_success=false and max_retained_bytes=0")
        if mode=="persistent" and (retain is not True or not isinstance(budget,int) or budget<=0): errors.append("persistent materialization requires retain_after_success=true and a positive byte budget")
    policy=binding.get("sync_policy"); _req(policy,contract["sync_policy_required_fields"],"sync_policy",errors)
    if isinstance(policy,dict):
        if policy.get("default_direction") not in contract["directions"]: errors.append("sync_policy.default_direction is unsupported")
        if policy.get("conflict_policy") not in contract["conflict_policies"]: errors.append("sync_policy.conflict_policy is unsupported")
        if policy.get("freshness_policy") not in contract["freshness_policies"]: errors.append("sync_policy.freshness_policy is unsupported")
        if policy.get("native_write_policy") not in contract["native_write_policies"]: errors.append("sync_policy.native_write_policy is unsupported")
        if str(binding.get("artifact_kind","")).startswith("native_") and policy.get("native_write_policy")!="provider_native_api_required":
            errors.append("native artifact kinds require native_write_policy=provider_native_api_required")
        cps=policy.get("checkpoint_triggers")
        if not isinstance(cps,list) or not cps: errors.append("sync_policy.checkpoint_triggers must be a non-empty list")
        elif any(x not in contract["checkpoint_triggers"] for x in cps): errors.append("sync_policy.checkpoint_triggers contains an unsupported trigger")
    s=json.dumps(binding,sort_keys=True)
    for pat in (r"https://(?:drive|docs)\.google\.com/",r"\bdrive_file_id\b",r"\bgoogle_drive_id\b"):
        if re.search(pat,s,re.I): errors.append("binding contains a forbidden raw provider locator")
    return errors

def main()->int:
    p=argparse.ArgumentParser(); p.add_argument("--binding",required=True,type=Path); p.add_argument("--contract",type=Path,default=DEFAULT_CONTRACT); a=p.parse_args()
    try:
        b=json.loads(a.binding.read_text(encoding="utf-8")); c=json.loads(a.contract.read_text(encoding="utf-8"))
    except (OSError,json.JSONDecodeError) as exc:
        print(json.dumps({"state":"FAIL","errors":[str(exc)]},indent=2)); return 2
    e=validate_binding(b,c); print(json.dumps({"schema_version":"artifact-sync-binding-validation/v1","state":"PASS" if not e else "FAIL","errors":e},indent=2,sort_keys=True)); return 0 if not e else 2
if __name__=="__main__": raise SystemExit(main())
