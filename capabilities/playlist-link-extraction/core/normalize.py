from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def normalize_source_ref(value: str) -> str:
    """Normalize a target source reference for stable provenance."""
    if not isinstance(value, str):
        raise TypeError("source_ref must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError("source_ref must be a non-empty string")
    return normalized


def normalize_url(value: str) -> str:
    """Normalize a URL for identity comparison without provider-specific rules.

    Rules are intentionally conservative and provider-agnostic:
    - trim whitespace
    - require a scheme and network location
    - lowercase scheme and host
    - drop default ports
    - drop fragments
    - normalize empty path to '/'
    - sort query parameters by key then value for stable identity
    """
    if not isinstance(value, str):
        raise TypeError("url must be a string")
    raw = value.strip()
    if not raw:
        raise ValueError("url must be a non-empty string")

    parts = urlsplit(raw)
    if not parts.scheme or not parts.netloc:
        raise ValueError(f"url must include scheme and host: {value!r}")

    scheme = parts.scheme.lower()
    hostname = (parts.hostname or "").lower()
    if not hostname:
        raise ValueError(f"url host is missing: {value!r}")

    port = parts.port
    if port is not None:
        if (scheme == "http" and port == 80) or (scheme == "https" and port == 443):
            netloc = hostname
        else:
            netloc = f"{hostname}:{port}"
    else:
        netloc = hostname

    path = parts.path or "/"
    query_items = parse_qsl(parts.query, keep_blank_values=True)
    query = urlencode(sorted(query_items), doseq=True)
    return urlunsplit((scheme, netloc, path, query, ""))
