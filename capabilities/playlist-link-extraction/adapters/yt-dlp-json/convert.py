"""Convert offline yt-dlp-style playlist JSON into observation batches.

This adapter owns provider-specific interpretation only. It does not
normalize URLs, deduplicate links, or build canonical artifacts.
"""

from __future__ import annotations

from typing import Any

ADAPTER_ID = "yt-dlp-json"
OBSERVATION_SCHEMA = "playlist-link-observation-batch/v1"
PROVIDER_PAYLOAD_SCHEMA = "yt-dlp-json-playlist-payload/v1"
FORBIDDEN_KEY_FRAGMENTS = (
    "cookie",
    "password",
    "secret",
    "token",
    "authorization",
    "api_key",
    "session",
    "credential",
    "browser_profile",
)


def validate_provider_payload(payload: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["provider payload root must be a JSON object"]

    errors.extend(_privacy_errors(payload, "$"))

    payload_type = payload.get("_type")
    if payload_type is not None and payload_type != "playlist":
        errors.append("provider payload _type must be 'playlist' when present")

    entries = payload.get("entries")
    if not isinstance(entries, list) or not entries:
        errors.append("provider payload entries must be a non-empty list")
        return errors

    usable = 0
    for index, entry in enumerate(entries):
        prefix = f"entries[{index}]"
        if entry is None:
            continue
        if not isinstance(entry, dict):
            errors.append(f"{prefix} must be an object or null")
            continue
        errors.extend(_privacy_errors(entry, prefix))
        url = _entry_url(entry)
        if not url:
            errors.append(
                f"{prefix} must provide webpage_url, url, or original_url"
            )
            continue
        usable += 1

    if usable == 0:
        errors.append("provider payload entries contain no usable URL-bearing items")
    return errors


def convert_playlist_payload(
    payload: dict[str, Any],
    *,
    target_id: str,
    source_ref: str | None = None,
    label: str | None = None,
) -> dict[str, Any]:
    errors = validate_provider_payload(payload)
    if errors:
        raise ValueError("; ".join(errors))
    if not isinstance(target_id, str) or not target_id.strip():
        raise ValueError("target_id must be a non-empty string")

    resolved_source = source_ref
    if resolved_source is None:
        for key in ("webpage_url", "original_url", "url"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                resolved_source = value.strip()
                break
    if not isinstance(resolved_source, str) or not resolved_source.strip():
        raise ValueError(
            "source_ref is required when the provider payload omits webpage_url/url"
        )

    target: dict[str, Any] = {
        "target_id": target_id.strip(),
        "source_ref": resolved_source.strip(),
    }
    resolved_label = label
    if resolved_label is None:
        title = payload.get("title")
        if isinstance(title, str) and title.strip():
            resolved_label = title.strip()
    if isinstance(resolved_label, str) and resolved_label.strip():
        target["label"] = resolved_label.strip()

    observations: list[dict[str, Any]] = []
    ordinal = 0
    for entry in payload["entries"]:
        if entry is None:
            continue
        assert isinstance(entry, dict)
        url = _entry_url(entry)
        if not url:
            continue
        observation: dict[str, Any] = {
            "target_id": target["target_id"],
            "url": url,
            "ordinal": ordinal,
            "adapter_id": ADAPTER_ID,
            "adapter_data": _adapter_data(payload, entry, ordinal),
        }
        title = entry.get("title")
        if isinstance(title, str) and title.strip():
            observation["title"] = title.strip()
        observations.append(observation)
        ordinal += 1

    return {
        "schema_version": OBSERVATION_SCHEMA,
        "targets": [target],
        "observations": observations,
    }


def _privacy_errors(node: dict[str, Any], path: str) -> list[str]:
    errors: list[str] = []
    for key in node:
        lowered = str(key).lower()
        if any(fragment in lowered for fragment in FORBIDDEN_KEY_FRAGMENTS):
            errors.append(
                f"{path}.{key} is forbidden in tracked offline provider payloads"
            )
    return errors


def _entry_url(entry: dict[str, Any]) -> str | None:
    for key in ("webpage_url", "url", "original_url"):
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _adapter_data(
    payload: dict[str, Any],
    entry: dict[str, Any],
    ordinal: int,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "provider": "yt-dlp",
        "adapter_id": ADAPTER_ID,
        "provider_payload_schema": PROVIDER_PAYLOAD_SCHEMA,
        "playlist_index": ordinal,
    }
    for key in ("id", "extractor", "extractor_key", "ie_key"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            data[f"playlist_{key}"] = value.strip()
    for key in ("id", "ie_key", "extractor", "extractor_key"):
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            data[f"entry_{key}"] = value.strip()
    return data
