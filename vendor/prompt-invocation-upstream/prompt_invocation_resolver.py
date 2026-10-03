#!/usr/bin/env python3
"""Resolve P-number invocation shorthand to exact canonical prompt ownership.

TokenCorridor is canonical for shared/product-portable Prompt Kit registries.
Triage remains canonical for its donor-retained management-operations registry.
The resolver never guesses a prompt by title/similarity and never selects a source
merely because it is newer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
BOUNDARIES_REL = Path("src/tokencorridor/interface/promptkit/registry/prompts/product-boundaries.v1.json")
TC_PROMPTKIT_ROOT = Path("src/tokencorridor/interface/promptkit")
TRIAGE_REPOSITORY = "EndeavorEverlasting/web-excel-repair-triage"
TC_REPOSITORY = "EndeavorEverlasting/TokenCorridor"
CATALOG_REL = Path("harness/exports/prompt-invocation-catalog.v1.json")
UPSTREAM_CONTRACT = "prompt-invocation-upstream/v1"

EXECUTION_RE = re.compile(
    r"\b(invoke|run|execute|use|apply|incorporate|implement|call)\b", re.IGNORECASE
)
IMPLEMENT_RE = re.compile(r"\bimplement\b", re.IGNORECASE)
MUTATION_RE = re.compile(
    r"\b(rewrite|reword|edit|upgrade|strengthen|compress|critique|redesign|revise)\b|"
    r"\b(improve\s+the\s+prompt|mutate\s+the\s+prompt)\b",
    re.IGNORECASE,
)
REFERENCE_RE = re.compile(
    r"\b(what\s+is|show\s+me|describe|explain|inspect|find|where\s+is)\b", re.IGNORECASE
)
EXPLICIT_ID_RE = re.compile(r"\bP\s*0*(\d{1,3})\b", re.IGNORECASE)
VERB_NUMERIC_ID_RE = re.compile(
    r"\b(?:invoke|run|execute|use|apply|incorporate|implement|call)\s+(?:prompt\s+)?0*(\d{1,3})\b",
    re.IGNORECASE,
)
BARE_NUMERIC_RE = re.compile(r"^\s*0*(\d{1,3})\s*$")
BARE_PID_RE = re.compile(r"^\s*P\s*0*(\d{1,3})\s*$", re.IGNORECASE)


class PromptResolutionError(ValueError):
    pass


def normalize_prompt_id(number: str | int) -> str:
    n = int(number)
    if not 0 <= n <= 999:
        raise PromptResolutionError(f"prompt number out of range: {n}")
    return f"P{n:02d}" if n < 100 else f"P{n}"


def extract_prompt_ids(text: str) -> list[str]:
    ids: list[str] = []
    for match in EXPLICIT_ID_RE.finditer(text):
        pid = normalize_prompt_id(match.group(1))
        if pid not in ids:
            ids.append(pid)
    if not ids:
        for match in VERB_NUMERIC_ID_RE.finditer(text):
            pid = normalize_prompt_id(match.group(1))
            if pid not in ids:
                ids.append(pid)
    if not ids:
        match = BARE_NUMERIC_RE.match(text) or BARE_PID_RE.match(text)
        if match:
            ids.append(normalize_prompt_id(match.group(1)))
    return ids


def classify_intent(text: str, prompt_ids: list[str]) -> str:
    stripped = text.strip()
    bare_prompt = bool(BARE_PID_RE.match(stripped) or BARE_NUMERIC_RE.match(stripped)) and bool(prompt_ids)
    execution = bool(EXECUTION_RE.search(text)) or bare_prompt
    mutation = bool(MUTATION_RE.search(text))
    reference = bool(REFERENCE_RE.search(text))
    implement = bool(IMPLEMENT_RE.search(text))

    if execution and mutation:
        return "EXECUTE_THEN_MUTATE"
    if execution and implement:
        return "EXECUTE_AND_IMPLEMENT"
    if execution:
        return "EXECUTE"
    if mutation and prompt_ids:
        return "MUTATE_PROMPT"
    if reference and prompt_ids:
        return "REFERENCE"
    if prompt_ids:
        return "REFERENCE"
    return "UNKNOWN"


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PromptResolutionError(f"cannot read JSON {path}: {exc}") from exc


def _prompt_entries(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict) and x.get("id")]
    if isinstance(payload, dict):
        for key in ("prompts", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                return [x for x in value if isinstance(x, dict) and x.get("id")]
    return []


def _git_head(root: Path) -> str | None:
    try:
        p = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return p.stdout.strip() or None


def _tc_registry_path(tc_root: Path, registry_rel: str) -> Path:
    rel = Path(registry_rel)
    if rel.parts and rel.parts[0] == "registry":
        rel = Path(*rel.parts[1:])
    return tc_root / TC_PROMPTKIT_ROOT / "registry" / rel


def _iter_tc_canonical_registries(
    tc_root: Path, boundaries: dict[str, Any]
) -> Iterable[tuple[str, Path]]:
    seen: set[str] = set()
    shared = boundaries.get("shared_inputs", {})
    rels = [shared.get("base_registry")]
    rels.extend(shared.get("content_registries") or [])
    rels.extend(
        boundaries.get("products", {}).get("afk-agent-flow", {}).get("extension_registries")
        or []
    )
    for rel in rels:
        if not isinstance(rel, str) or rel in seen:
            continue
        seen.add(rel)
        yield rel, _tc_registry_path(tc_root, rel)


def _iter_triage_retained_registries(
    triage_root: Path, boundaries: dict[str, Any]
) -> Iterable[tuple[str, Path]]:
    rels = (
        boundaries.get("products", {})
        .get("triage-local-operations", {})
        .get("donor_retained_registries")
        or []
    )
    for rel in rels:
        if isinstance(rel, str):
            yield rel, triage_root / rel


def _find_prompt_in_files(
    pid: str, files: Iterable[tuple[str, Path]]
) -> list[tuple[str, Path, dict[str, Any]]]:
    hits: list[tuple[str, Path, dict[str, Any]]] = []
    for logical_path, path in files:
        if not path.is_file():
            continue
        for entry in _prompt_entries(_load_json(path)):
            if str(entry.get("id", "")).strip().upper() == pid:
                hits.append((logical_path, path, entry))
    return hits


def _find_triage_donor_fallback(
    pid: str, triage_root: Path, retained_paths: set[Path]
) -> list[tuple[str, Path, dict[str, Any]]]:
    hits: list[tuple[str, Path, dict[str, Any]]] = []
    candidates = []
    base = triage_root / "docs/prompts.json"
    if base.is_file():
        candidates.append(base)
    prompt_dir = triage_root / "registry/prompts"
    if prompt_dir.is_dir():
        candidates.extend(sorted(prompt_dir.glob("*.json")))
    for path in candidates:
        if path in retained_paths:
            continue
        try:
            rel = path.relative_to(triage_root).as_posix()
        except ValueError:
            rel = path.as_posix()
        for entry in _prompt_entries(_load_json(path)):
            if str(entry.get("id", "")).strip().upper() == pid:
                hits.append((rel, path, entry))
    return hits


def _resolved_record(
    pid: str,
    state: str,
    repository: str,
    root: Path,
    logical_path: str,
    entry: dict[str, Any],
    warning: str | None = None,
) -> dict[str, Any]:
    copy_content = str(entry.get("copyContent") or "")
    record = {
        "prompt_id": pid,
        "state": state,
        "canonical_repository": repository,
        "repository_head": _git_head(root),
        "registry_path": logical_path,
        "name": entry.get("name"),
        "type": entry.get("type"),
        "class": entry.get("class"),
        "copy_content_sha256": hashlib.sha256(copy_content.encode("utf-8")).hexdigest(),
        "copy_content": copy_content,
    }
    if warning:
        record["warning"] = warning
    return record


def resolve_prompt_id_from_catalog(pid: str, catalog_path: Path) -> dict[str, Any]:
    catalog = _load_json(catalog_path)
    if catalog.get("schema_version") != "prompt-invocation-catalog/v1":
        raise PromptResolutionError(
            f"unsupported prompt invocation catalog schema in {catalog_path}"
        )
    matches = [
        item
        for item in catalog.get("prompts", [])
        if isinstance(item, dict)
        and str(item.get("prompt_id", "")).strip().upper() == pid
    ]
    if len(matches) > 1:
        return {
            "prompt_id": pid,
            "state": "SOURCE_CONFLICT",
            "reason": "Prompt ID appears more than once in the upstream invocation catalog.",
        }
    if not matches:
        return {
            "prompt_id": pid,
            "state": "UNRESOLVED",
            "reason": "Exact prompt ID was not found in the upstream invocation catalog.",
        }

    entry = matches[0]
    copy_content = str(entry.get("copy_content") or "")
    return {
        "prompt_id": pid,
        "state": "RESOLVED_UPSTREAM",
        "upstream_contract": UPSTREAM_CONTRACT,
        "resolution_source": "UPSTREAM_CATALOG_PINNED",
        "authority_kind": entry.get("authority_kind"),
        "canonical_repository": entry.get("canonical_repository"),
        "registry_path": entry.get("canonical_registry_path"),
        "source_blob_sha": entry.get("source_blob_sha"),
        "name": entry.get("name"),
        "type": entry.get("type"),
        "class": entry.get("class"),
        "copy_content_sha256": hashlib.sha256(copy_content.encode("utf-8")).hexdigest(),
        "copy_content": copy_content,
    }


def resolve_prompt_id(
    pid: str, tc_root: Path, triage_root: Path | None = None
) -> dict[str, Any]:
    boundaries = _load_json(tc_root / BOUNDARIES_REL)
    tc_hits = _find_prompt_in_files(
        pid, _iter_tc_canonical_registries(tc_root, boundaries)
    )
    if len(tc_hits) > 1:
        return {
            "prompt_id": pid,
            "state": "SOURCE_CONFLICT",
            "reason": "Prompt ID appears more than once inside TokenCorridor canonical registries.",
            "matches": [x[0] for x in tc_hits],
        }

    retained_hits: list[tuple[str, Path, dict[str, Any]]] = []
    retained_paths: set[Path] = set()
    if triage_root is not None:
        retained_files = list(
            _iter_triage_retained_registries(triage_root, boundaries)
        )
        retained_paths = {p for _, p in retained_files}
        retained_hits = _find_prompt_in_files(pid, retained_files)
        if len(retained_hits) > 1:
            return {
                "prompt_id": pid,
                "state": "SOURCE_CONFLICT",
                "reason": "Prompt ID appears more than once inside Triage retained canonical registries.",
                "matches": [x[0] for x in retained_hits],
            }

    if tc_hits and retained_hits:
        return {
            "prompt_id": pid,
            "state": "SOURCE_CONFLICT",
            "reason": "Product-boundary violation: the same ID appears in TokenCorridor portable and Triage retained canonical owners.",
            "matches": [tc_hits[0][0], retained_hits[0][0]],
        }

    if tc_hits:
        logical, _, entry = tc_hits[0]
        return _resolved_record(
            pid,
            "RESOLVED_TOKENCORRIDOR",
            TC_REPOSITORY,
            tc_root,
            f"src/tokencorridor/interface/promptkit/{logical}",
            entry,
        )

    if retained_hits:
        logical, _, entry = retained_hits[0]
        return _resolved_record(
            pid,
            "RESOLVED_TRIAGE_RETAINED",
            TRIAGE_REPOSITORY,
            triage_root,
            logical,
            entry,
        )

    if triage_root is None:
        return {
            "prompt_id": pid,
            "state": "PROVIDER_LOOKUP_REQUIRED",
            "canonical_repository_hint": TRIAGE_REPOSITORY,
            "reason": "Prompt ID is not in TokenCorridor canonical portable/shared registries and no Triage checkout/provider snapshot was supplied.",
            "lookup_contract": "Inspect Triage product-boundary/retained registry before any donor fallback. Do not fuzzy-map the ID.",
        }

    donor_hits = _find_triage_donor_fallback(pid, triage_root, retained_paths)
    if len(donor_hits) > 1:
        return {
            "prompt_id": pid,
            "state": "SOURCE_CONFLICT",
            "reason": "Prompt ID appears in multiple non-retained Triage donor registries while absent from TokenCorridor canonical registries.",
            "matches": [x[0] for x in donor_hits],
        }
    if donor_hits:
        logical, _, entry = donor_hits[0]
        return _resolved_record(
            pid,
            "RESOLVED_TRIAGE_DONOR_FALLBACK",
            TRIAGE_REPOSITORY,
            triage_root,
            logical,
            entry,
            warning="Migration gap: this prompt is discoverable only from a Triage donor surface. Do not treat donor fallback as TokenCorridor authority cutover.",
        )

    return {
        "prompt_id": pid,
        "state": "UNRESOLVED",
        "reason": "Exact prompt ID was not found in TokenCorridor canonical registries or the supplied Triage registries.",
    }


def resolve_prompt_invocation(
    text: str,
    tc_root: Path = ROOT,
    triage_root: Path | None = None,
    catalog_path: Path | None = None,
) -> dict[str, Any]:
    prompt_ids = extract_prompt_ids(text)
    intent = classify_intent(text, prompt_ids)
    selected_catalog = catalog_path or (tc_root / CATALOG_REL)
    if selected_catalog.is_file():
        resolutions = [
            resolve_prompt_id_from_catalog(pid, selected_catalog) for pid in prompt_ids
        ]
        resolution_mode = "UPSTREAM_CATALOG_PINNED"
    else:
        resolutions = [
            resolve_prompt_id(pid, tc_root, triage_root) for pid in prompt_ids
        ]
        resolution_mode = "LEGACY_INTERNAL_REGISTRY_RESOLUTION"
    states = [r["state"] for r in resolutions]
    if not prompt_ids:
        overall = "UNRESOLVED"
    elif any(s == "SOURCE_CONFLICT" for s in states):
        overall = "SOURCE_CONFLICT"
    elif any(s in {"PROVIDER_LOOKUP_REQUIRED", "UNRESOLVED"} for s in states):
        overall = "PARTIAL_OR_BLOCKED" if len(states) > 1 else states[0]
    else:
        overall = "RESOLVED"
    return {
        "schema_version": "prompt-invocation-resolution-result/v1",
        "operator_text": text,
        "prompt_ids": prompt_ids,
        "intent": intent,
        "execution_required": intent
        in {"EXECUTE", "EXECUTE_AND_IMPLEMENT", "EXECUTE_THEN_MUTATE"},
        "implementation_required": intent == "EXECUTE_AND_IMPLEMENT",
        "upstream_contract": UPSTREAM_CONTRACT,
        "resolution_mode": resolution_mode,
        "overall_state": overall,
        "resolutions": resolutions,
        "proof_ceiling": "Deterministic upstream prompt identity/intent resolution only; actual workflow execution and integration require separate proof.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--text", required=True, help="Operator text containing P-number shorthand"
    )
    parser.add_argument(
        "--token-root", default=str(ROOT), help="TokenCorridor repository root"
    )
    parser.add_argument(
        "--triage-root",
        default=None,
        help="Legacy maintainer-only Triage checkout override; downstream consumers should use the upstream catalog.",
    )
    parser.add_argument(
        "--catalog",
        default=str(ROOT / CATALOG_REL),
        help="Stable upstream prompt catalog; downstream consumers may supply a synchronized catalog path.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional path for the machine-readable resolution packet.",
    )
    parser.add_argument(
        "--no-copy", action="store_true", help="Omit copyContent from output after resolution"
    )
    args = parser.parse_args(argv)
    try:
        result = resolve_prompt_invocation(
            args.text,
            Path(args.token_root).resolve(),
            Path(args.triage_root).resolve() if args.triage_root else None,
            Path(args.catalog).resolve() if args.catalog else None,
        )
        if args.no_copy:
            for item in result.get("resolutions", []):
                item.pop("copy_content", None)
        rendered = json.dumps(result, indent=2, sort_keys=True)
        print(rendered)
        if args.output:
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(rendered + "\n", encoding="utf-8")
        return 0 if result["overall_state"] == "RESOLVED" else 2
    except PromptResolutionError as exc:
        print(f"prompt-resolution error: {exc}", file=__import__("sys").stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
