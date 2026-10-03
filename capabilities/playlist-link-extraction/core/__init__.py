"""Reusable playlist-link-extraction core.

Adapters supply observation batches. This package owns normalization,
deduplication, ordered membership, canonical JSON, and CSV projections.
"""

from .artifact import build_artifact, artifact_to_csv_rows, validate_observation_batch
from .normalize import normalize_source_ref, normalize_url

__all__ = [
    "build_artifact",
    "artifact_to_csv_rows",
    "validate_observation_batch",
    "normalize_source_ref",
    "normalize_url",
]
