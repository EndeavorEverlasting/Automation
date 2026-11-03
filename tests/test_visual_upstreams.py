"""Expose the source-catalog offline canaries to the repository's existing root CI unittest discovery.

The capability owns the tests; this root bridge prevents new checks from being
silently skipped by Automation Validation's existing `python -m unittest discover -s tests` gate.
"""
import importlib.util
from pathlib import Path

_TEST_PATH = (
    Path(__file__).resolve().parents[1]
    / "capabilities" / "visual-state-compare" / "tests" / "test_upstreams.py"
)
_spec = importlib.util.spec_from_file_location("visual_upstream_owned_tests", _TEST_PATH)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)

UpstreamCatalogTests = _module.UpstreamCatalogTests
