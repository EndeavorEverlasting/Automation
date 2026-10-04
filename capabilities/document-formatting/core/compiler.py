from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping

SOURCE_SCHEMA = "document-formatting-source/v1"
DESIGN_SCHEMA = "document-formatting-design-spec/v1"
IR_SCHEMA = "document-formatting-ir/v1"
RECEIPT_SCHEMA = "document-formatting-compiler-receipt/v1"

URL_RE = re.compile(r"https?://[^\s<>()]+", re.IGNORECASE)
SECTION_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")

TEXT_BLOCK_TYPES = {"paragraph", "warning", "evidence", "signature_line"}
SPECIAL_BLOCK_TYPES = {"command", "bullet_list", "table", "image"}
ALLOWED_BLOCK_TYPES = TEXT_BLOCK_TYPES | SPECIAL_BLOCK_TYPES

FRAME_ROLE_KEYS = {
    "title",
    "subtitle",
    "metadata",
    "navigation_heading",
    "navigation_link",
    "resource_heading",
    "resource_link",
    "heading_1",
    "heading_2",
}


class DocumentCompileError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _fail(code: str, message: str) -> None:
    raise DocumentCompileError(code, message)


def _non_empty_string(value: Any, *, path: str, allow_url: bool = False) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail("DF_REQUIRED_FIELD", f"{path} must be non-empty text")
    if value != value.strip():
        _fail("DF_CANONICAL_TEXT", f"{path} must not contain surrounding whitespace")
    if not allow_url and URL_RE.search(value):
        _fail("DF_RAW_VISIBLE_URL", f"{path} contains a raw visible URL; use a named resource")
    return value


def _role_style(spec: Mapping[str, Any], role_id: str) -> dict[str, Any]:
    role = spec["roles"].get(role_id)
    if not isinstance(role, Mapping):
        _fail("DF_DESIGN_SPEC", f"unknown role: {role_id}")
    colors: dict[str, str] = {}
    for prop, token in role.get("colors", {}).items():
        colors[prop] = spec["palette"][token]
    return {
        "role_id": role_id,
        "mechanics": dict(role.get("mechanics", {})),
        "colors": colors,
    }


def validate_design_spec(spec: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(spec, dict):
        return ["design spec root must be an object"]
    if spec.get("schema_version") != DESIGN_SCHEMA:
        errors.append(f"schema_version must be {DESIGN_SCHEMA!r}")
    if not isinstance(spec.get("spec_id"), str) or not spec["spec_id"].strip():
        errors.append("spec_id must be a non-empty string")
    if not isinstance(spec.get("page_mechanics"), dict):
        errors.append("page_mechanics must be an object")
    palette = spec.get("palette")
    if not isinstance(palette, dict) or not palette:
        errors.append("palette must be a non-empty object")
        palette = {}
    roles = spec.get("roles")
    if not isinstance(roles, dict) or not roles:
        errors.append("roles must be a non-empty object")
        roles = {}
    for role_id, role in roles.items():
        if not isinstance(role_id, str) or not role_id:
            errors.append("role IDs must be non-empty strings")
            continue
        if not isinstance(role, dict):
            errors.append(f"roles.{role_id} must be an object")
            continue
        if not isinstance(role.get("mechanics", {}), dict):
            errors.append(f"roles.{role_id}.mechanics must be an object")
        colors = role.get("colors", {})
        if not isinstance(colors, dict):
            errors.append(f"roles.{role_id}.colors must be an object")
            continue
        for prop, token in colors.items():
            if not isinstance(prop, str) or not prop:
                errors.append(f"roles.{role_id}.colors keys must be non-empty")
            if token not in palette:
                errors.append(f"roles.{role_id}.colors.{prop} references unknown palette token {token!r}")

    frame_roles = spec.get("frame_roles")
    if not isinstance(frame_roles, dict):
        errors.append("frame_roles must be an object")
        frame_roles = {}
    missing_frame = sorted(FRAME_ROLE_KEYS - set(frame_roles))
    if missing_frame:
        errors.append("frame_roles missing: " + ", ".join(missing_frame))
    for key, role_id in frame_roles.items():
        if key not in FRAME_ROLE_KEYS:
            errors.append(f"unexpected frame_roles key: {key}")
        if role_id not in roles:
            errors.append(f"frame_roles.{key} references unknown role {role_id!r}")

    block_map = spec.get("block_component_map")
    if not isinstance(block_map, dict):
        errors.append("block_component_map must be an object")
        block_map = {}
    if set(block_map) != ALLOWED_BLOCK_TYPES:
        errors.append("block_component_map must cover exactly: " + ", ".join(sorted(ALLOWED_BLOCK_TYPES)))
    for block_type, role_value in block_map.items():
        role_ids = role_value if isinstance(role_value, list) else [role_value]
        if not role_ids or any(r not in roles for r in role_ids):
            errors.append(f"block_component_map.{block_type} must reference known roles")

    archetypes = spec.get("archetypes")
    if not isinstance(archetypes, dict) or not archetypes:
        errors.append("archetypes must be a non-empty object")
        archetypes = {}
    known_components = set(roles)
    for archetype, cfg in archetypes.items():
        if not isinstance(cfg, dict):
            errors.append(f"archetypes.{archetype} must be an object")
            continue
        required_sections = cfg.get("required_sections", [])
        if not isinstance(required_sections, list) or not all(isinstance(x, str) and x for x in required_sections):
            errors.append(f"archetypes.{archetype}.required_sections must be an array of strings")
        nav = cfg.get("navigation", {})
        if not isinstance(nav, dict):
            errors.append(f"archetypes.{archetype}.navigation must be an object")
        else:
            mode = nav.get("mode")
            if mode not in {"ALWAYS", "NEVER", "WHEN_H1_COUNT_GTE"}:
                errors.append(f"archetypes.{archetype}.navigation.mode is invalid")
            if mode == "WHEN_H1_COUNT_GTE":
                threshold = nav.get("threshold")
                if not isinstance(threshold, int) or threshold < 1:
                    errors.append(f"archetypes.{archetype}.navigation.threshold must be positive")
            if mode != "NEVER" and (not isinstance(nav.get("title"), str) or not nav["title"].strip()):
                errors.append(f"archetypes.{archetype}.navigation.title is required")
        reqs = cfg.get("section_component_requirements", {})
        if not isinstance(reqs, dict):
            errors.append(f"archetypes.{archetype}.section_component_requirements must be an object")
        else:
            for section_title, components in reqs.items():
                if not isinstance(components, list) or not components:
                    errors.append(
                        f"archetypes.{archetype}.section_component_requirements.{section_title} must be non-empty"
                    )
                    continue
                unknown = sorted(set(components) - known_components)
                if unknown:
                    errors.append(
                        f"archetypes.{archetype}.section_component_requirements.{section_title} has unknown roles: {unknown}"
                    )
        if not isinstance(cfg.get("named_resource_links_required"), bool):
            errors.append(f"archetypes.{archetype}.named_resource_links_required must be boolean")
    return errors


def _validate_source_block(block: Any, *, path: str, spec: Mapping[str, Any]) -> None:
    if not isinstance(block, Mapping):
        _fail("DF_BLOCK", f"{path} must be an object")
    block_type = _non_empty_string(block.get("type"), path=f"{path}.type")
    if block_type not in spec["block_component_map"]:
        _fail("DF_BLOCK", f"{path}.type must be one of {sorted(spec['block_component_map'])}")

    if block_type in TEXT_BLOCK_TYPES:
        _non_empty_string(block.get("text"), path=f"{path}.text")
        return
    if block_type == "command":
        _non_empty_string(block.get("text"), path=f"{path}.text", allow_url=True)
        return
    if block_type == "bullet_list":
        items = block.get("items")
        if not isinstance(items, list) or not items:
            _fail("DF_BLOCK", f"{path}.items must be a non-empty array")
        for index, item in enumerate(items):
            _non_empty_string(item, path=f"{path}.items[{index}]")
        return
    if block_type == "table":
        headers = block.get("headers")
        rows = block.get("rows")
        if not isinstance(headers, list) or not headers:
            _fail("DF_BLOCK", f"{path}.headers must be a non-empty array")
        for index, header in enumerate(headers):
            _non_empty_string(header, path=f"{path}.headers[{index}]")
        if not isinstance(rows, list):
            _fail("DF_BLOCK", f"{path}.rows must be an array")
        for row_index, row in enumerate(rows):
            if not isinstance(row, list) or len(row) != len(headers):
                _fail("DF_BLOCK", f"{path}.rows[{row_index}] must contain {len(headers)} cells")
            for col_index, cell in enumerate(row):
                _non_empty_string(cell, path=f"{path}.rows[{row_index}][{col_index}]")
        return
    if block_type == "image":
        _non_empty_string(block.get("asset_ref"), path=f"{path}.asset_ref", allow_url=True)
        _non_empty_string(block.get("alt_text"), path=f"{path}.alt_text")
        caption = block.get("caption")
        if caption is not None:
            _non_empty_string(caption, path=f"{path}.caption")
        return


def validate_source(source: Any, spec: Mapping[str, Any]) -> None:
    if not isinstance(source, Mapping):
        _fail("DF_SOURCE_SCHEMA", "source root must be an object")
    if source.get("schema_version") != SOURCE_SCHEMA:
        _fail("DF_SOURCE_SCHEMA", f"schema_version must be {SOURCE_SCHEMA!r}")

    archetype = _non_empty_string(source.get("archetype"), path="archetype")
    if archetype not in spec["archetypes"]:
        _fail("DF_ARCHETYPE", f"unknown archetype: {archetype}")
    _non_empty_string(source.get("title"), path="title")
    subtitle = source.get("subtitle")
    if subtitle is not None:
        _non_empty_string(subtitle, path="subtitle")

    metadata = source.get("metadata")
    if not isinstance(metadata, list):
        _fail("DF_REQUIRED_FIELD", "metadata must be an array")
    for index, item in enumerate(metadata):
        if not isinstance(item, Mapping):
            _fail("DF_REQUIRED_FIELD", f"metadata[{index}] must be an object")
        _non_empty_string(item.get("label"), path=f"metadata[{index}].label")
        _non_empty_string(item.get("value"), path=f"metadata[{index}].value")

    resources = source.get("resources")
    if not isinstance(resources, list):
        _fail("DF_REQUIRED_FIELD", "resources must be an array")
    normalized_resources = []
    for index, item in enumerate(resources):
        if not isinstance(item, Mapping):
            _fail("DF_RESOURCE", f"resources[{index}] must be an object")
        label = _non_empty_string(item.get("label"), path=f"resources[{index}].label")
        url = _non_empty_string(item.get("url"), path=f"resources[{index}].url", allow_url=True)
        if URL_RE.fullmatch(label):
            _fail("DF_RESOURCE", f"resources[{index}].label must be descriptive")
        if not URL_RE.fullmatch(url):
            _fail("DF_RESOURCE", f"resources[{index}].url must be absolute http(s)")
        normalized_resources.append((label, url))
    if len(normalized_resources) != len(set(normalized_resources)):
        _fail("DF_RESOURCE", "resources must not contain duplicate label/url pairs")

    sections = source.get("sections")
    if not isinstance(sections, list) or not sections:
        _fail("DF_REQUIRED_FIELD", "sections must be a non-empty array")
    seen_ids: set[str] = set()
    for index, section in enumerate(sections):
        path = f"sections[{index}]"
        if not isinstance(section, Mapping):
            _fail("DF_REQUIRED_FIELD", f"{path} must be an object")
        section_id = _non_empty_string(section.get("id"), path=f"{path}.id")
        if not SECTION_ID_RE.fullmatch(section_id):
            _fail("DF_SECTION_ID", f"{path}.id must match {SECTION_ID_RE.pattern}")
        if section_id in seen_ids:
            _fail("DF_DUPLICATE_SECTION_ID", f"duplicate section id: {section_id}")
        seen_ids.add(section_id)
        _non_empty_string(section.get("title"), path=f"{path}.title")
        level = section.get("level")
        if type(level) is not int or level not in {1, 2}:
            _fail("DF_SECTION_LEVEL", f"{path}.level must be 1 or 2")
        blocks = section.get("blocks")
        if not isinstance(blocks, list) or not blocks:
            _fail("DF_BLOCK", f"{path}.blocks must be a non-empty array")
        for block_index, block in enumerate(blocks):
            _validate_source_block(block, path=f"{path}.blocks[{block_index}]", spec=spec)

    archetype_cfg = spec["archetypes"][archetype]
    titles = [section["title"] for section in sections]
    missing_sections = [x for x in archetype_cfg.get("required_sections", []) if x not in titles]
    if missing_sections:
        _fail("DF_REQUIRED_SECTION", "missing required sections: " + ", ".join(missing_sections))

    if archetype_cfg.get("named_resource_links_required") and not resources:
        _fail("DF_RESOURCE", "this archetype requires at least one named resource")

    requirements = archetype_cfg.get("section_component_requirements", {})
    for section_title, required_roles in requirements.items():
        matching = [s for s in sections if s["title"] == section_title]
        if not matching:
            _fail("DF_REQUIRED_SECTION", f"missing section required for component rule: {section_title}")
        present: set[str] = set()
        for block in matching[0]["blocks"]:
            mapped = spec["block_component_map"][block["type"]]
            present.update(mapped if isinstance(mapped, list) else [mapped])
        missing = sorted(set(required_roles) - present)
        if missing:
            _fail(
                "DF_REQUIRED_COMPONENT",
                f"section {section_title!r} missing required roles: {', '.join(missing)}",
            )


def _navigation_required(archetype_cfg: Mapping[str, Any], sections: list[Mapping[str, Any]]) -> bool:
    nav = archetype_cfg["navigation"]
    mode = nav["mode"]
    if mode == "ALWAYS":
        return True
    if mode == "NEVER":
        return False
    h1_count = sum(1 for section in sections if section["level"] == 1)
    return h1_count >= nav["threshold"]


def _append_block(
    blocks: list[dict[str, Any]],
    *,
    kind: str,
    component: str,
    spec: Mapping[str, Any],
    payload: Mapping[str, Any] | None = None,
) -> None:
    block = {
        "kind": kind,
        "component": component,
        "style": _role_style(spec, component),
    }
    if payload:
        block.update(payload)
    blocks.append(block)


def _structure_projection(block: Mapping[str, Any]) -> dict[str, Any]:
    keep = {
        "kind",
        "component",
        "section_id",
        "anchor_id",
        "target_section_id",
        "resource_url",
        "asset_ref",
        "row_count",
        "column_count",
    }
    return {key: block[key] for key in sorted(keep) if key in block}


def compile_document(
    source: Mapping[str, Any],
    design_spec: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    errors = validate_design_spec(design_spec)
    if errors:
        _fail("DF_DESIGN_SPEC", "; ".join(errors))
    validate_source(source, design_spec)

    archetype = source["archetype"]
    cfg = design_spec["archetypes"][archetype]
    frame = design_spec["frame_roles"]
    sections = list(source["sections"])
    navigation_required = _navigation_required(cfg, sections)

    blocks: list[dict[str, Any]] = []
    _append_block(
        blocks,
        kind="text",
        component=frame["title"],
        spec=design_spec,
        payload={"text": source["title"]},
    )
    if source.get("subtitle"):
        _append_block(
            blocks,
            kind="text",
            component=frame["subtitle"],
            spec=design_spec,
            payload={"text": source["subtitle"]},
        )
    for item in source["metadata"]:
        _append_block(
            blocks,
            kind="metadata",
            component=frame["metadata"],
            spec=design_spec,
            payload={"label": item["label"], "value": item["value"]},
        )

    if navigation_required:
        nav_title = cfg["navigation"]["title"]
        _append_block(
            blocks,
            kind="heading",
            component=frame["navigation_heading"],
            spec=design_spec,
            payload={"text": nav_title, "anchor_id": "__navigation"},
        )
        for section in sections:
            if section["level"] != 1:
                continue
            _append_block(
                blocks,
                kind="link",
                component=frame["navigation_link"],
                spec=design_spec,
                payload={
                    "label": section["title"],
                    "target_section_id": section["id"],
                    "link_type": "internal",
                },
            )

    if source["resources"]:
        _append_block(
            blocks,
            kind="heading",
            component=frame["resource_heading"],
            spec=design_spec,
            payload={"text": "Resources", "anchor_id": "__resources"},
        )
        for resource in source["resources"]:
            _append_block(
                blocks,
                kind="link",
                component=frame["resource_link"],
                spec=design_spec,
                payload={
                    "label": resource["label"],
                    "resource_url": resource["url"],
                    "link_type": "external",
                },
            )

    for section in sections:
        heading_component = frame["heading_1"] if section["level"] == 1 else frame["heading_2"]
        _append_block(
            blocks,
            kind="heading",
            component=heading_component,
            spec=design_spec,
            payload={
                "text": section["title"],
                "section_id": section["id"],
                "anchor_id": section["id"],
                "level": section["level"],
            },
        )
        for source_block in section["blocks"]:
            block_type = source_block["type"]
            mapped = design_spec["block_component_map"][block_type]
            component = mapped[0] if isinstance(mapped, list) else mapped
            payload: dict[str, Any] = {"section_id": section["id"], "source_block_type": block_type}
            if block_type in TEXT_BLOCK_TYPES | {"command"}:
                payload["text"] = source_block["text"]
                kind = "text"
            elif block_type == "bullet_list":
                payload["items"] = list(source_block["items"])
                kind = "bullet_list"
            elif block_type == "table":
                payload["headers"] = list(source_block["headers"])
                payload["rows"] = [list(row) for row in source_block["rows"]]
                payload["row_count"] = len(source_block["rows"])
                payload["column_count"] = len(source_block["headers"])
                kind = "table"
            elif block_type == "image":
                payload["asset_ref"] = source_block["asset_ref"]
                payload["alt_text"] = source_block["alt_text"]
                if source_block.get("caption") is not None:
                    payload["caption"] = source_block["caption"]
                kind = "image"
            else:
                _fail("DF_BLOCK", f"unsupported block type: {block_type}")
            _append_block(blocks, kind=kind, component=component, spec=design_spec, payload=payload)

    components_used = sorted({block["component"] for block in blocks})
    non_color_projection = {
        "page_mechanics": design_spec["page_mechanics"],
        "roles": {
            role_id: design_spec["roles"][role_id].get("mechanics", {})
            for role_id in components_used
        },
        "component_sequence": [block["component"] for block in blocks],
    }
    palette_projection = {
        "palette": design_spec["palette"],
        "role_color_tokens": {
            role_id: design_spec["roles"][role_id].get("colors", {})
            for role_id in components_used
        },
    }
    structure_projection = [_structure_projection(block) for block in blocks]

    ir: dict[str, Any] = {
        "schema_version": IR_SCHEMA,
        "spec_id": design_spec["spec_id"],
        "archetype": archetype,
        "page_mechanics": dict(design_spec["page_mechanics"]),
        "blocks": blocks,
        "metrics": {
            "navigation_required": navigation_required,
            "internal_link_count": sum(
                1 for block in blocks if block.get("link_type") == "internal"
            ),
            "named_external_link_count": sum(
                1 for block in blocks if block.get("link_type") == "external"
            ),
            "image_count": sum(1 for block in blocks if block["kind"] == "image"),
            "table_count": sum(1 for block in blocks if block["kind"] == "table"),
        },
        "fingerprints": {
            "content": sha256_json(source),
            "structure": sha256_json(structure_projection),
            "non_color_aesthetic": sha256_json(non_color_projection),
            "palette": sha256_json(palette_projection),
            "compiled": "",
        },
    }
    compiled_projection = json.loads(json.dumps(ir))
    compiled_projection["fingerprints"]["compiled"] = ""
    ir["fingerprints"]["compiled"] = sha256_json(compiled_projection)

    receipt = {
        "schema_version": RECEIPT_SCHEMA,
        "state": "COMPILED_PROVIDER_NEUTRAL_DOCUMENT",
        "spec_id": design_spec["spec_id"],
        "design_spec_sha256": sha256_json(design_spec),
        "source_sha256": sha256_json(source),
        "compiled_sha256": ir["fingerprints"]["compiled"],
        "proof_ceiling": (
            "PROVIDER_NEUTRAL_IR_ONLY; no provider mutation, readback, render, "
            "visual acceptance, or cross-platform fidelity is implied"
        ),
    }
    return ir, receipt
