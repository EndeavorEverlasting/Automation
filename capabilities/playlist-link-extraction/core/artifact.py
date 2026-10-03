from __future__ import annotations

import csv
import io
from typing import Any

from .normalize import normalize_source_ref, normalize_url

OBSERVATION_SCHEMA = "playlist-link-observation-batch/v1"
ARTIFACT_SCHEMA = "playlist-link-artifact/v1"
CAPABILITY_ID = "playlist-link-extraction"
PROOF_CEILING = (
    "Core normalization, occurrence/uniqueness, canonical JSON, and CSV "
    "projection are proven with synthetic fixtures. Live provider adapters, "
    "authenticated runtime extraction, and production use remain unproven."
)


def validate_observation_batch(batch: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(batch, dict):
        return ["observation batch root must be a JSON object"]

    if batch.get("schema_version") != OBSERVATION_SCHEMA:
        errors.append(f"schema_version must be {OBSERVATION_SCHEMA!r}")

    targets = batch.get("targets")
    if not isinstance(targets, list) or not targets:
        errors.append("targets must be a non-empty list")
        targets = []

    observations = batch.get("observations")
    if not isinstance(observations, list):
        errors.append("observations must be a list")
        observations = []

    target_ids: set[str] = set()
    for index, target in enumerate(targets):
        prefix = f"targets[{index}]"
        if not isinstance(target, dict):
            errors.append(f"{prefix} must be an object")
            continue
        target_id = target.get("target_id")
        source_ref = target.get("source_ref")
        if not isinstance(target_id, str) or not target_id.strip():
            errors.append(f"{prefix}.target_id must be a non-empty string")
        else:
            if target_id in target_ids:
                errors.append(f"duplicate target_id: {target_id!r}")
            target_ids.add(target_id)
        if not isinstance(source_ref, str) or not source_ref.strip():
            errors.append(f"{prefix}.source_ref must be a non-empty string")
        else:
            try:
                normalize_source_ref(source_ref)
            except (TypeError, ValueError) as exc:
                errors.append(f"{prefix}.source_ref is invalid: {exc}")

    for index, observation in enumerate(observations):
        prefix = f"observations[{index}]"
        if not isinstance(observation, dict):
            errors.append(f"{prefix} must be an object")
            continue
        target_id = observation.get("target_id")
        url = observation.get("url")
        ordinal = observation.get("ordinal")
        adapter_id = observation.get("adapter_id")
        if not isinstance(target_id, str) or not target_id.strip():
            errors.append(f"{prefix}.target_id must be a non-empty string")
        elif target_ids and target_id not in target_ids:
            errors.append(f"{prefix}.target_id {target_id!r} is not declared in targets")
        if not isinstance(url, str) or not url.strip():
            errors.append(f"{prefix}.url must be a non-empty string")
        elif isinstance(url, str):
            try:
                normalize_url(url)
            except (TypeError, ValueError) as exc:
                errors.append(f"{prefix}.url is invalid: {exc}")
        if not isinstance(ordinal, int) or isinstance(ordinal, bool) or ordinal < 0:
            errors.append(f"{prefix}.ordinal must be a non-negative integer")
        if not isinstance(adapter_id, str) or not adapter_id.strip():
            errors.append(f"{prefix}.adapter_id must be a non-empty string")
        adapter_data = observation.get("adapter_data", {})
        if adapter_data is not None and not isinstance(adapter_data, dict):
            errors.append(f"{prefix}.adapter_data must be an object when present")

    return errors


def build_artifact(batch: dict[str, Any]) -> dict[str, Any]:
    errors = validate_observation_batch(batch)
    if errors:
        raise ValueError("; ".join(errors))

    targets_out: list[dict[str, Any]] = []
    for target in batch["targets"]:
        item = {
            "target_id": target["target_id"].strip(),
            "source_ref": normalize_source_ref(target["source_ref"]),
        }
        label = target.get("label")
        if isinstance(label, str) and label.strip():
            item["label"] = label.strip()
        targets_out.append(item)

    sorted_observations = sorted(
        batch["observations"],
        key=lambda item: (
            item["target_id"],
            item["ordinal"],
            item["url"],
            item["adapter_id"],
        ),
    )

    occurrences: list[dict[str, Any]] = []
    unique_links: list[dict[str, Any]] = []
    unique_index: dict[str, int] = {}
    adapter_ids: set[str] = set()

    for observation in sorted_observations:
        target_id = observation["target_id"].strip()
        adapter_id = observation["adapter_id"].strip()
        adapter_ids.add(adapter_id)
        observed_url = observation["url"].strip()
        normalized = normalize_url(observed_url)
        title = observation.get("title")
        adapter_data = observation.get("adapter_data") or {}

        occurrence = {
            "target_id": target_id,
            "ordinal": observation["ordinal"],
            "observed_url": observed_url,
            "normalized_url": normalized,
            "adapter_id": adapter_id,
        }
        if isinstance(title, str) and title.strip():
            occurrence["title"] = title.strip()
        if adapter_data:
            occurrence["adapter_data"] = adapter_data
        occurrences.append(occurrence)

        if normalized not in unique_index:
            unique_index[normalized] = len(unique_links)
            unique_item = {
                "normalized_url": normalized,
                "first_observed_url": observed_url,
                "first_target_id": target_id,
                "first_ordinal": observation["ordinal"],
                "occurrence_count": 1,
                "adapter_ids": [adapter_id],
            }
            if isinstance(title, str) and title.strip():
                unique_item["title"] = title.strip()
            unique_links.append(unique_item)
        else:
            unique_item = unique_links[unique_index[normalized]]
            unique_item["occurrence_count"] += 1
            if adapter_id not in unique_item["adapter_ids"]:
                unique_item["adapter_ids"].append(adapter_id)

    return {
        "schema_version": ARTIFACT_SCHEMA,
        "capability_id": CAPABILITY_ID,
        "targets": targets_out,
        "occurrences": occurrences,
        "unique_links": unique_links,
        "receipt": {
            "capability_id": CAPABILITY_ID,
            "core_status": "CORE_IMPLEMENTED_ADAPTERS_PENDING",
            "target_count": len(targets_out),
            "occurrence_count": len(occurrences),
            "unique_link_count": len(unique_links),
            "adapter_ids": sorted(adapter_ids),
            "proof_ceiling": PROOF_CEILING,
        },
    }


def artifact_to_csv_rows(artifact: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for occurrence in artifact.get("occurrences", []):
        rows.append(
            {
                "target_id": str(occurrence["target_id"]),
                "ordinal": str(occurrence["ordinal"]),
                "observed_url": str(occurrence["observed_url"]),
                "normalized_url": str(occurrence["normalized_url"]),
                "adapter_id": str(occurrence["adapter_id"]),
                "title": str(occurrence.get("title", "")),
            }
        )
    return rows


def render_csv(artifact: dict[str, Any]) -> str:
    rows = artifact_to_csv_rows(artifact)
    buffer = io.StringIO()
    fieldnames = [
        "target_id",
        "ordinal",
        "observed_url",
        "normalized_url",
        "adapter_id",
        "title",
    ]
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buffer.getvalue()
