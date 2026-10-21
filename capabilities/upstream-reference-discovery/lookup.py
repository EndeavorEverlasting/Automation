#!/usr/bin/env python3
"""Deterministic, offline upstream reference discovery. No network, installs, or promotion."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

SUPPORTED = {"upstream-intelligence-consumer/v1", "upstream-intelligence-catalog/v1"}
TYPES = {"public_reference", "codex_portable_candidate", "chatgpt_work_plugin_reference"}
PROOF = {"DISCOVERED", "REGISTERED_REFERENCE", "CANDIDATE", "DONOR", "LINK_ONLY_CASE_STUDY",
         "HISTORICAL_DOCUMENTED_UNVERIFIED", "DISCOVERED_NOT_IMPLEMENTED"}
def load(path: Path) -> dict:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict) or obj.get("schema_version") not in SUPPORTED:
        raise ValueError("unsupported upstream-intelligence registry schema")
    items = obj.get("resources")
    if not isinstance(items, list):
        raise ValueError("resources must be an array")
    seen = set()
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("resource must be object")
        ident = item.get("id")
        if not isinstance(ident, str) or not ident.strip() or ident in seen:
            raise ValueError("duplicate, empty or invalid resource id")
        seen.add(ident)
        if item.get("kind") not in TYPES:
            raise ValueError(f"invalid resource kind: {ident}")
        target = item.get("locator")
        if not isinstance(target, str) or not target.startswith(("https://", "skills://")):
            raise ValueError(f"invalid locator: {ident}")
        if target.startswith("skills://") and item["kind"] != "chatgpt_work_plugin_reference":
            raise ValueError(f"plugin locator cannot be mistaken for portable skill: {ident}")
        if item.get("installed_locally") is not False:
            raise ValueError(f"catalog may not claim locally installed: {ident}")
        if not item.get("source_provenance"):
            raise ValueError(f"source provenance missing: {ident}")
    return obj

def find(obj: dict, query: str, limit: int = 8, category: str = "") -> list[dict]:
    words = [w.lower() for w in query.split() if w.strip()]
    ranked = []
    for item in obj["resources"]:
        if category and category.lower() not in (str(item.get("category") or "")).lower():
            continue
        hay = " ".join(str(item.get(k, "")) for k in ("id", "name", "category", "mechanism", "tags")).lower()
        if words and not all(w in hay for w in words):
            continue
        score = sum((4 if w in str(item.get("name", "")).lower() else 1) for w in words)
        ranked.append((score,item["id"],item))
    ranked.sort(key=lambda x:(-x[0],x[1]))
    return [it for _,__,it in ranked[:limit]]

def main(argv: list[str] | None = None) -> int:
    p=argparse.ArgumentParser(description="Offline skill/design source locator with proof states")
    p.add_argument("--registry",type=Path,required=True)
    p.add_argument("--query",default="")
    p.add_argument("--category",default="")
    p.add_argument("--limit",type=int,default=8)
    p.add_argument("--validate",action="store_true")
    args=p.parse_args(argv)
    try:
        if not (1<=args.limit<=50):
            raise ValueError("limit must be 1..50")
        registry=load(args.registry)
        results=[] if args.validate else find(registry,args.query,args.limit,args.category)
        print(json.dumps({"state":"REGISTRY_VALID" if args.validate else "REFERENCE_DISCOVERY_ONLY",
                          "registry":str(args.registry),"matches":len(results),
                          "results":results,"proof_ceiling":"Research pointers only. No provider access, install, license clearance, adoption or host skill discovery proven."},indent=2))
        return 0
    except (OSError,ValueError,TypeError) as exc:
        print(json.dumps({"state":"INVALID_REFERENCE_REGISTRY","reason":str(exc)}))
        return 2

if __name__=="__main__":
    sys.exit(main())
