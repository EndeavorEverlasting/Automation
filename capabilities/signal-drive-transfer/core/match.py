"""Deterministic UI-selection → DB-row matching (no relevance judgment)."""
from __future__ import annotations

from typing import Any, Mapping, Sequence


class MatchError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


SPEC_KEYS = frozenset(
    {
        "ordinal",
        "exactBody",
        "startsWith",
        "includes",
        "andIncludes",
        "emptyWithAttachment",
        "afterOrdinal",
        "beforeOrdinal",
    }
)


def _require_profile(profile: Mapping[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(profile, Mapping):
        raise MatchError("MATCH_PROFILE_SHAPE", "match profile must be an object")
    specs = profile.get("matchSpecs")
    if not isinstance(specs, list) or not specs:
        raise MatchError("MATCH_PROFILE_SPECS", "matchSpecs must be a non-empty array")
    normalized: list[dict[str, Any]] = []
    seen: set[int] = set()
    for index, raw in enumerate(specs):
        if not isinstance(raw, Mapping):
            raise MatchError("MATCH_SPEC_SHAPE", f"matchSpecs[{index}] must be an object")
        unknown = set(raw) - SPEC_KEYS
        if unknown:
            raise MatchError(
                "MATCH_SPEC_UNKNOWN",
                f"matchSpecs[{index}] unknown keys: {sorted(unknown)}",
            )
        ordinal = raw.get("ordinal")
        if not isinstance(ordinal, int) or ordinal < 1:
            raise MatchError("MATCH_SPEC_ORDINAL", f"matchSpecs[{index}].ordinal invalid")
        if ordinal in seen:
            raise MatchError("MATCH_SPEC_ORDINAL_DUP", f"duplicate matchSpecs ordinal {ordinal}")
        seen.add(ordinal)
        modes = [
            bool(raw.get("exactBody")),
            bool(raw.get("startsWith")),
            bool(raw.get("includes")),
            bool(raw.get("emptyWithAttachment")),
        ]
        if sum(1 for flag in modes if flag) != 1:
            raise MatchError(
                "MATCH_SPEC_MODE",
                f"matchSpecs[{index}] must set exactly one match mode",
            )
        if raw.get("emptyWithAttachment"):
            after_ordinal = raw.get("afterOrdinal")
            before_ordinal = raw.get("beforeOrdinal")
            if not isinstance(after_ordinal, int) or not isinstance(before_ordinal, int):
                raise MatchError(
                    "MATCH_SPEC_BETWEEN",
                    f"matchSpecs[{index}] emptyWithAttachment requires afterOrdinal/beforeOrdinal",
                )
        normalized.append(dict(raw))
    return sorted(normalized, key=lambda item: int(item["ordinal"]))


def _candidates(
    rows: Sequence[Mapping[str, Any]],
    spec: Mapping[str, Any],
    used: set[Any],
) -> list[Mapping[str, Any]]:
    out: list[Mapping[str, Any]] = []
    for row in rows:
        row_id = row.get("id")
        if row_id in used:
            continue
        body = row.get("body") or ""
        if not isinstance(body, str):
            continue
        if "exactBody" in spec and body == spec["exactBody"]:
            out.append(row)
        elif "startsWith" in spec and body.startswith(str(spec["startsWith"])):
            out.append(row)
        elif "includes" in spec:
            needle = str(spec["includes"])
            extra = spec.get("andIncludes")
            if needle in body and (extra is None or str(extra) in body):
                out.append(row)
    return out


def match_messages(
    rows: Sequence[Mapping[str, Any]],
    profile: Mapping[str, Any],
    *,
    expected_count: int | None = None,
) -> dict[str, Any]:
    """Map matchSpecs onto DB rows. Ambiguity or miss is a hard failure."""
    specs = _require_profile(profile)
    if expected_count is not None and len(specs) != expected_count:
        raise MatchError(
            "MATCH_COUNT",
            f"matchSpecs length={len(specs)} != expected_count={expected_count}",
        )
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        raise MatchError("MATCH_ROWS", "rows must be a sequence of objects")
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping) or "id" not in row:
            raise MatchError("MATCH_ROW_SHAPE", f"rows[{index}] must include id")

    used: set[Any] = set()
    by_ordinal: dict[int, dict[str, Any]] = {}
    matched: list[dict[str, Any]] = []

    deferred = [spec for spec in specs if spec.get("emptyWithAttachment")]
    primary = [spec for spec in specs if not spec.get("emptyWithAttachment")]

    for spec in primary:
        candidates = _candidates(rows, spec, used)
        if len(candidates) != 1:
            raise MatchError(
                "MATCH_AMBIGUOUS_OR_MISS",
                f"ordinal {spec['ordinal']} matched {len(candidates)} rows",
            )
        row = candidates[0]
        used.add(row["id"])
        item = {
            "ordinal": spec["ordinal"],
            "id": row["id"],
            "sent_at": row.get("sent_at"),
            "sent_at_iso": row.get("sent_at_iso"),
            "body": row.get("body") or "",
            "hasAttachments": bool(row.get("hasAttachments")),
            "attachments": list(row.get("attachments") or []),
            "matchMode": next(
                key for key in ("exactBody", "startsWith", "includes") if key in spec
            ),
        }
        by_ordinal[spec["ordinal"]] = item
        matched.append(item)

    for spec in deferred:
        after_item = by_ordinal.get(int(spec["afterOrdinal"]))
        before_item = by_ordinal.get(int(spec["beforeOrdinal"]))
        if after_item is None or before_item is None:
            raise MatchError(
                "MATCH_BETWEEN_DEPENDENCY",
                f"ordinal {spec['ordinal']} requires resolved after/before ordinals",
            )
        after_ts = after_item.get("sent_at")
        before_ts = before_item.get("sent_at")
        if not isinstance(after_ts, (int, float)) or not isinstance(before_ts, (int, float)):
            raise MatchError(
                "MATCH_BETWEEN_TIMESTAMP",
                f"ordinal {spec['ordinal']} cannot bound empty attachment without timestamps",
            )
        between: list[Mapping[str, Any]] = []
        for row in rows:
            if row.get("id") in used:
                continue
            sent_at = row.get("sent_at")
            body = (row.get("body") or "").strip()
            if (
                isinstance(sent_at, (int, float))
                and after_ts < sent_at < before_ts
                and bool(row.get("hasAttachments"))
                and body == ""
            ):
                between.append(row)
        if len(between) != 1:
            raise MatchError(
                "MATCH_AMBIGUOUS_OR_MISS",
                f"ordinal {spec['ordinal']} emptyWithAttachment matched {len(between)} rows",
            )
        row = between[0]
        used.add(row["id"])
        item = {
            "ordinal": spec["ordinal"],
            "id": row["id"],
            "sent_at": row.get("sent_at"),
            "sent_at_iso": row.get("sent_at_iso"),
            "body": "",
            "hasAttachments": True,
            "attachments": list(row.get("attachments") or []),
            "matchMode": "emptyWithAttachment",
        }
        by_ordinal[spec["ordinal"]] = item
        matched.append(item)

    matched.sort(key=lambda item: int(item["ordinal"]))
    return {
        "contract": "automation.signal-drive-transfer.match/v1",
        "status": "MATCHED",
        "selectedCount": len(matched),
        "messages": matched,
    }
