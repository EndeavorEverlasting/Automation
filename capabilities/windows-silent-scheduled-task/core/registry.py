"""Load consumer-owned silent-cron job registries."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA = "automation.windows-silent-scheduled-task.registry/v1"
REQUIRED_JOB_KEYS = ("id", "task_name", "script", "interval_min")


def load_registry(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("registry must be a JSON object")
    schema = str(raw.get("schema") or raw.get("schema_version") or "")
    if schema != SCHEMA:
        raise ValueError(f"unsupported registry schema {schema!r}; expected {SCHEMA}")
    jobs = raw.get("jobs")
    if not isinstance(jobs, list) or not jobs:
        raise ValueError("registry.jobs must be a non-empty list")
    seen: set[str] = set()
    for job in jobs:
        if not isinstance(job, dict):
            raise ValueError("each job must be an object")
        for key in REQUIRED_JOB_KEYS:
            if key not in job:
                raise ValueError(f"job missing required key {key!r}")
        job_id = str(job["id"])
        if job_id in seen:
            raise ValueError(f"duplicate job id {job_id!r}")
        seen.add(job_id)
        interval = int(job["interval_min"])
        if interval < 1 or interval > 24 * 60:
            raise ValueError(f"job {job_id}: interval_min out of range")
        run_level = str(job.get("run_level") or "Limited")
        if run_level not in {"Limited", "Highest"}:
            raise ValueError(f"job {job_id}: invalid run_level {run_level!r}")
        job["run_level"] = run_level
        job["args"] = str(job.get("args") or "").strip()
    return raw


def list_jobs(path: Path) -> list[dict[str, Any]]:
    return list(load_registry(path)["jobs"])


def job_by_id(job_id: str, path: Path) -> dict[str, Any]:
    for job in list_jobs(path):
        if str(job["id"]) == job_id:
            return job
    raise KeyError(f"unknown job id {job_id!r}")
