"""Render matched messages into a deterministic markdown package."""
from __future__ import annotations

from typing import Any, Mapping, Sequence


def _body_text(body: Any) -> str:
    text = "" if body is None else str(body)
    text = text.replace("\u0000", "").strip()
    return text if text else "(no text body — media only)"


def render_message_markdown(message: Mapping[str, Any], *, total: int) -> str:
    ordinal = int(message["ordinal"])
    lines = [
        f"# Message {ordinal} of {total}",
        "",
        f"**Date/time (UTC):** {message.get('sent_at_iso') or ''}",
        "",
        "## Body / caption",
        "",
        _body_text(message.get("body")),
        "",
    ]
    attachments = list(message.get("attachmentsSaved") or message.get("attachments") or [])
    image_meta = list(message.get("imageMeta") or [])
    if image_meta or attachments:
        lines.extend(["## Attachments / images", ""])
        if image_meta:
            for item in image_meta:
                name = item.get("file") or item.get("path") or "attachment"
                ctype = item.get("contentType") or "application/octet-stream"
                size = item.get("bytes")
                suffix = f", {size} bytes" if isinstance(size, int) else ""
                lines.append(f"- `{name}` ({ctype}{suffix})")
        else:
            for index, item in enumerate(attachments):
                if isinstance(item, Mapping):
                    name = item.get("fileName") or item.get("path") or f"attachment-{index}"
                    ctype = item.get("contentType") or "application/octet-stream"
                    lines.append(f"- `{name}` ({ctype})")
                else:
                    lines.append(f"- `{item}`")
        lines.append("")
    return "\n".join(lines)


def build_index_markdown(
    messages: Sequence[Mapping[str, Any]],
    *,
    title: str,
    conversation_title: str | None = None,
) -> str:
    lines = [
        f"# {title}",
        "",
        f"**Selected messages:** {len(messages)}",
    ]
    if conversation_title:
        lines.append(f"**Conversation:** {conversation_title}")
    lines.extend(["", "## Index", ""])
    for message in messages:
        ordinal = int(message["ordinal"])
        preview = _body_text(message.get("body")).splitlines()[0][:120]
        stamp = message.get("sent_at_iso") or ""
        lines.append(f"- Message {ordinal}: {stamp} — {preview}")
    lines.append("")
    return "\n".join(lines)


def build_document_bundle(
    messages: Sequence[Mapping[str, Any]],
    *,
    title: str,
    conversation_title: str | None = None,
) -> dict[str, Any]:
    if not messages:
        raise ValueError("messages must be non-empty")
    ordered = sorted(messages, key=lambda item: int(item["ordinal"]))
    total = len(ordered)
    per_message: list[dict[str, Any]] = []
    parts: list[str] = []
    index = build_index_markdown(
        ordered, title=title, conversation_title=conversation_title
    )
    parts.append(index)
    for message in ordered:
        markdown = render_message_markdown(message, total=total)
        per_message.append(
            {
                "ordinal": int(message["ordinal"]),
                "title": f"{title} — Message {int(message['ordinal'])} of {total}",
                "markdown": markdown,
                "bytes": len(markdown.encode("utf-8")),
            }
        )
        parts.append("---\n\n" + markdown)
    doc_clean = "\n\n".join(parts).rstrip() + "\n"
    return {
        "contract": "automation.signal-drive-transfer.document/v1",
        "title": title,
        "selectedCount": total,
        "indexMarkdown": index,
        "docCleanMarkdown": doc_clean,
        "messages": per_message,
    }
