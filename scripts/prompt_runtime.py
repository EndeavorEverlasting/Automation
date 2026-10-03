#!/usr/bin/env python3
"""Resolve operator P-number shorthand from canonical repository-owned prompt sources.

This bridge deliberately does not use conversational/model memory as prompt authority.
It resolves exact P-number identities from configured canonical GitHub repository
sources and emits a machine-readable invocation packet. Execution of the recovered
prompt remains the responsibility of the repo-capable agent/runtime that invoked it.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "prompt-sources.v1.json"

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
    r"\b(what\s+is|show\s+me|describe|explain|inspect|find|where\s+is)\b",
    re.IGNORECASE,
)
EXPLICIT_ID_RE = re.compile(r"\bP\s*0*(\d{1,3})\b", re.IGNORECASE)
VERB_NUMERIC_ID_RE = re.compile(
    r"\b(?:invoke|run|execute|use|apply|incorporate|implement|call)\s+"
    r"(?:prompt\s+)?0*(\d{1,3})\b",
    re.IGNORECASE,
)
BARE_NUMERIC_RE = re.compile(r"^\s*0*(\d{1,3})\s*$")
BARE_PID_RE = re.compile(r"^\s*P\s*0*(\d{1,3})\s*$", re.IGNORECASE)


class PromptRuntimeError(RuntimeError):
    """Base error for deterministic prompt-runtime failures."""


class PromptSourceError(PromptRuntimeError):
    """Raised when a configured prompt source cannot be read."""


def normalize_prompt_id(number: str | int) -> str:
    n = int(number)
    if not 0 <= n <= 999:
        raise PromptRuntimeError(f"prompt number out of range: {n}")
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
    bare_prompt = bool(
        (BARE_PID_RE.match(stripped) or BARE_NUMERIC_RE.match(stripped)) and prompt_ids
    )
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


def _prompt_entries(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict) and x.get("id")]
    if isinstance(payload, dict):
        for key in ("prompts", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                return [x for x in value if isinstance(x, dict) and x.get("id")]
    return []


def _env_or(value: str | None, env_name: str | None) -> str | None:
    if env_name:
        observed = os.environ.get(env_name)
        if observed:
            return observed
    return value


def load_config(path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PromptRuntimeError(f"cannot read prompt source config {path}: {exc}") from exc

    if payload.get("schema_version") != "automation-prompt-sources/v1":
        raise PromptRuntimeError("unsupported prompt source config schema")

    for key in ("portable", "retained"):
        if key not in payload or not isinstance(payload[key], dict):
            raise PromptRuntimeError(f"prompt source config missing {key!r}")
    return payload


class GitHubContentsClient:
    """Small stdlib GitHub Contents API client with optional token auth."""

    def __init__(self, token: str | None = None, opener=None):
        self.token = token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        self.opener = opener or urllib.request.urlopen
        self._cache: dict[tuple[str, str, str], tuple[Any, dict[str, Any]]] = {}

    def _request_envelope(self, url: str, *, authenticated: bool) -> dict[str, Any]:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "EndeavorEverlasting-Automation-PromptRuntime/1",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if authenticated and self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = urllib.request.Request(url, headers=headers)
        with self.opener(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))

    def fetch_json(self, repository: str, path: str, ref: str) -> tuple[Any, dict[str, Any]]:
        key = (repository, path, ref)
        if key in self._cache:
            return self._cache[key]

        quoted_path = urllib.parse.quote(path, safe="/")
        query = urllib.parse.urlencode({"ref": ref})
        url = f"https://api.github.com/repos/{repository}/contents/{quoted_path}?{query}"
        try:
            envelope = self._request_envelope(url, authenticated=bool(self.token))
        except urllib.error.HTTPError as exc:
            # GitHub Actions' repository-scoped GITHUB_TOKEN can return 404 for a
            # different public repository even though anonymous public access is
            # valid. Retry once without credentials so an over-scoped token cannot
            # make a public canonical prompt source disappear. Private sources still
            # fail closed if the anonymous retry is also rejected.
            if self.token and exc.code in {403, 404}:
                try:
                    envelope = self._request_envelope(url, authenticated=False)
                except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as retry_exc:
                    raise PromptSourceError(
                        f"cannot fetch {repository}@{ref}:{path}: authenticated request returned {exc.code}; "
                        f"anonymous retry failed: {retry_exc}"
                    ) from retry_exc
            else:
                raise PromptSourceError(
                    f"cannot fetch {repository}@{ref}:{path}: {exc}"
                ) from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise PromptSourceError(
                f"cannot fetch {repository}@{ref}:{path}: {exc}"
            ) from exc

        encoded = envelope.get("content")
        if not isinstance(encoded, str):
            raise PromptSourceError(
                f"GitHub response for {repository}@{ref}:{path} has no file content"
            )
        try:
            raw = base64.b64decode(encoded).decode("utf-8")
            payload = json.loads(raw)
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PromptSourceError(
                f"invalid JSON at {repository}@{ref}:{path}: {exc}"
            ) from exc

        meta = {
            "repository": repository,
            "ref": ref,
            "path": path,
            "blob_sha": envelope.get("sha"),
            "html_url": envelope.get("html_url"),
        }
        self._cache[key] = (payload, meta)
        return payload, meta


FetchJson = Callable[[str, str, str], tuple[Any, dict[str, Any]]]


def _resolved_source(source: dict[str, Any]) -> tuple[str, str]:
    repository = _env_or(source.get("repository"), source.get("repository_env"))
    ref = _env_or(source.get("ref", "main"), source.get("ref_env"))
    if not repository or not ref:
        raise PromptRuntimeError("prompt source repository/ref resolved empty")
    return str(repository), str(ref)


def _portable_registry_paths(boundaries: dict[str, Any]) -> list[str]:
    shared = boundaries.get("shared_inputs", {})
    paths: list[str] = []
    base = shared.get("base_registry")
    if isinstance(base, str):
        paths.append(base)
    paths.extend(x for x in (shared.get("content_registries") or []) if isinstance(x, str))
    extensions = (
        boundaries.get("products", {})
        .get("afk-agent-flow", {})
        .get("extension_registries")
        or []
    )
    paths.extend(x for x in extensions if isinstance(x, str))
    # stable dedupe
    return list(dict.fromkeys(paths))


def _retained_registry_paths(boundaries: dict[str, Any]) -> list[str]:
    values = (
        boundaries.get("products", {})
        .get("triage-local-operations", {})
        .get("donor_retained_registries")
        or []
    )
    return [x for x in values if isinstance(x, str)]


def _portable_physical_path(promptkit_root: str, logical_path: str) -> str:
    root = promptkit_root.rstrip("/")
    if logical_path.startswith("registry/"):
        return f"{root}/{logical_path}"
    return f"{root}/registry/{logical_path}"


def _find_prompt(
    pid: str,
    repository: str,
    ref: str,
    paths: list[tuple[str, str]],
    fetch_json: FetchJson,
) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for logical_path, physical_path in paths:
        payload, meta = fetch_json(repository, physical_path, ref)
        for entry in _prompt_entries(payload):
            if str(entry.get("id", "")).strip().upper() == pid:
                hits.append(
                    {
                        "logical_path": logical_path,
                        "physical_path": physical_path,
                        "entry": entry,
                        "meta": meta,
                    }
                )
    return hits


def _record(pid: str, state: str, hit: dict[str, Any], repository: str) -> dict[str, Any]:
    entry = hit["entry"]
    body = str(entry.get("copyContent") or "")
    meta = hit["meta"]
    return {
        "prompt_id": pid,
        "state": state,
        "canonical_repository": repository,
        "registry_path": hit["physical_path"],
        "source_ref": meta.get("ref"),
        "source_blob_sha": meta.get("blob_sha"),
        "source_url": meta.get("html_url"),
        "name": entry.get("name"),
        "type": entry.get("type"),
        "class": entry.get("class"),
        "copy_content_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
        "copy_content": body,
    }


def resolve_prompt_id(
    pid: str, config: dict[str, Any], fetch_json: FetchJson
) -> dict[str, Any]:
    portable = config["portable"]
    retained = config["retained"]
    portable_repo, portable_ref = _resolved_source(portable)
    retained_repo, retained_ref = _resolved_source(retained)

    boundaries_path = portable["product_boundaries_path"]
    boundaries, boundary_meta = fetch_json(portable_repo, boundaries_path, portable_ref)
    promptkit_root = portable["promptkit_root"]

    portable_paths = [
        (logical, _portable_physical_path(promptkit_root, logical))
        for logical in _portable_registry_paths(boundaries)
    ]
    retained_paths = [(logical, logical) for logical in _retained_registry_paths(boundaries)]

    primary_hits = _find_prompt(
        pid, portable_repo, portable_ref, portable_paths, fetch_json
    )
    retained_hits = _find_prompt(
        pid, retained_repo, retained_ref, retained_paths, fetch_json
    )

    if len(primary_hits) > 1:
        return {
            "prompt_id": pid,
            "state": "SOURCE_CONFLICT",
            "reason": "Prompt ID appears more than once in portable canonical registries.",
            "matches": [h["physical_path"] for h in primary_hits],
        }
    if len(retained_hits) > 1:
        return {
            "prompt_id": pid,
            "state": "SOURCE_CONFLICT",
            "reason": "Prompt ID appears more than once in retained canonical registries.",
            "matches": [h["physical_path"] for h in retained_hits],
        }
    if primary_hits and retained_hits:
        return {
            "prompt_id": pid,
            "state": "SOURCE_CONFLICT",
            "reason": "Prompt ID appears in both portable and retained canonical owners.",
            "matches": [
                f"{portable_repo}:{primary_hits[0]['physical_path']}",
                f"{retained_repo}:{retained_hits[0]['physical_path']}",
            ],
        }
    if primary_hits:
        record = _record(pid, "RESOLVED_PORTABLE", primary_hits[0], portable_repo)
    elif retained_hits:
        record = _record(pid, "RESOLVED_RETAINED", retained_hits[0], retained_repo)
    else:
        return {
            "prompt_id": pid,
            "state": "UNRESOLVED",
            "reason": "Exact prompt ID was not found in configured canonical registries; fuzzy substitution is forbidden.",
            "boundary_source": boundary_meta,
        }

    record["boundary_source"] = boundary_meta
    return record


def resolve_prompt_invocation(
    text: str, config: dict[str, Any], fetch_json: FetchJson
) -> dict[str, Any]:
    prompt_ids = extract_prompt_ids(text)
    intent = classify_intent(text, prompt_ids)
    resolutions: list[dict[str, Any]] = []

    for pid in prompt_ids:
        try:
            resolutions.append(resolve_prompt_id(pid, config, fetch_json))
        except PromptSourceError as exc:
            resolutions.append(
                {
                    "prompt_id": pid,
                    "state": "PROVIDER_LOOKUP_REQUIRED",
                    "reason": str(exc),
                }
            )

    states = [r["state"] for r in resolutions]
    if not prompt_ids:
        overall = "UNRESOLVED"
    elif any(s == "SOURCE_CONFLICT" for s in states):
        overall = "SOURCE_CONFLICT"
    elif any(s in {"UNRESOLVED", "PROVIDER_LOOKUP_REQUIRED"} for s in states):
        overall = "PARTIAL_OR_BLOCKED" if len(states) > 1 else states[0]
    else:
        overall = "RESOLVED"

    return {
        "schema_version": "automation-prompt-invocation/v1",
        "operator_text": text,
        "prompt_ids": prompt_ids,
        "intent": intent,
        "execution_required": intent
        in {"EXECUTE", "EXECUTE_AND_IMPLEMENT", "EXECUTE_THEN_MUTATE"},
        "implementation_required": intent == "EXECUTE_AND_IMPLEMENT",
        "overall_state": overall,
        "resolutions": resolutions,
        "authority_rule": "Repository-owned canonical prompt sources, never conversational/model memory.",
        "proof_ceiling": (
            "Canonical prompt source/intent resolution only. The consuming agent/runtime "
            "must separately prove workflow execution, mutation, validation, integration, deployment, "
            "and production behavior."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text", required=True, help="Operator text containing P-number invocation")
    parser.add_argument(
        "--config", default=str(DEFAULT_CONFIG), help="Prompt source configuration JSON"
    )
    parser.add_argument("--no-copy", action="store_true", help="Omit copyContent from output")
    parser.add_argument("--output", help="Optional path for the JSON invocation packet")
    args = parser.parse_args(argv)

    try:
        config = load_config(Path(args.config))
        client = GitHubContentsClient()
        result = resolve_prompt_invocation(args.text, config, client.fetch_json)
    except PromptRuntimeError as exc:
        print(f"prompt-runtime error: {exc}", file=sys.stderr)
        return 1

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


if __name__ == "__main__":
    raise SystemExit(main())
