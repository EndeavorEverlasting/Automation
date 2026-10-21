"""Synthetic upstream intelligence locator canaries."""
import json
from pathlib import Path
from unittest import TestCase
from tempfile import TemporaryDirectory
import importlib.util

MODULE = Path(__file__).resolve().parents[1] / "lookup.py"
spec=importlib.util.spec_from_file_location("upstream_reference_lookup",MODULE)
lookup=importlib.util.module_from_spec(spec)
spec.loader.exec_module(lookup)
class TestLocator(TestCase):
    def item(self,**changes):
        o={"id":"motion","name":"Motion","kind":"public_reference","category":"design",
           "mechanism":"animate","locator":"https://motion.dev","installed_locally":False,
           "source_provenance":"upstream workbook / Curated Sources"}
        o.update(changes)
        return o
    def test_query_is_bounded(self):
        d={"schema_version":"upstream-intelligence-consumer/v1",
           "resources":[self.item(),self.item(id="other",name="Another",locator="https://example.org")]}
        with TemporaryDirectory() as tmp:
            p=Path(tmp)/"data.json";p.write_text(json.dumps(d))
            o=lookup.load(p)
            self.assertEqual([x["id"] for x in lookup.find(o,"Motion")],["motion"])
            self.assertEqual(len(lookup.find(o,"",limit=1)),1)
    def test_no_false_installs(self):
        for item in [self.item(installed_locally=True),
                     self.item(kind="public_reference",locator="skills://plugins/example"),
                     self.item(source_provenance=""), self.item(locator="file:///secrets")]:
            with TemporaryDirectory() as tmp:
                p=Path(tmp)/"data.json";p.write_text(json.dumps({"schema_version":"upstream-intelligence-consumer/v1","resources":[item]}))
                with self.assertRaises(ValueError):
                    lookup.load(p)
    def test_duplicate_and_bad_schema(self):
        with TemporaryDirectory() as tmp:
            p=Path(tmp)/"data.json"
            p.write_text(json.dumps({"schema_version":"upstream-intelligence-consumer/v1","resources":[self.item(),self.item()]}))
            with self.assertRaises(ValueError):lookup.load(p)
            p.write_text(json.dumps({"schema_version":"wrong","resources":[]}))
            with self.assertRaises(ValueError):lookup.load(p)
