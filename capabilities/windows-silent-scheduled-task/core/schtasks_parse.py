"""Parse ``schtasks /Query /FO LIST /V`` output into a flat map."""
from __future__ import annotations


STATE_MISSING = "MISSING"
STATE_DISABLED = "DISABLED"
STATE_READY = "READY"
STATE_UNKNOWN = "UNKNOWN"


def parse_schtasks_list(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()
        if key and key not in out:
            out[key] = val
    return out


def classify_status(fields: dict[str, str], *, present: bool) -> str:
    if not present:
        return STATE_MISSING
    state = (fields.get("Scheduled Task State") or "").strip().lower()
    status = (fields.get("Status") or "").strip().lower()
    if state == "disabled" or status == "disabled":
        return STATE_DISABLED
    if status in {"ready", "running", "queued"}:
        return STATE_READY
    if status and status not in {"ready", "running", "queued"}:
        return STATE_UNKNOWN
    if state == "enabled":
        return STATE_READY
    return STATE_UNKNOWN
