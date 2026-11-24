"""Checks for scripts/labels.py against the published packs in site/.

Run from the repository root: python -m unittest discover -s tests
"""

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import labels  # noqa: E402

SITE = ROOT / "site"
GLOSSARY = json.loads((ROOT / "labels" / "annotations.json").read_text(encoding="utf-8"))


@unittest.skipUnless((SITE / "graph.bin.gz").exists(), "site packs are not present")
class LabelPacking(unittest.TestCase):
    def render(self, glossary):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "annotations.json"
            path.write_text(json.dumps(glossary, ensure_ascii=False), encoding="utf-8")
            return labels.render(SITE, path)

    def edited(self, name, **changes):
        g = copy.deepcopy(GLOSSARY)
        entry = next(e for e in g["entries"] if e["name"] == name)
        for key, value in changes.items():
            if value is None:
                entry.pop(key, None)
            else:
                entry[key] = value
        return g

    def first(self, field):
        return next(e for e in GLOSSARY["entries"] if field in e)

    def test_published_packs_are_reproduced(self):
        rh, grh, _, _ = labels.render(SITE, ROOT / "labels" / "annotations.json")
        self.assertEqual(rh, (SITE / "annotations.json").read_text(encoding="utf-8"))
        self.assertEqual(grh, (SITE / "grh" / "annotations.json").read_text(encoding="utf-8"))

    def test_text_edit_reaches_both_views(self):
        entry = self.first("blueprint")
        rh, grh, _, _ = self.render(self.edited(entry["name"], title="Edited title"))
        rh_entries = json.loads(rh)["entries"]
        self.assertIn("Edited title", [e["title"] for e in rh_entries.values()])
        grh_names = [e["name"] for e in json.loads(grh)["entries"].values()]
        if entry["name"] in grh_names:
            self.assertIn("Edited title", [e["title"] for e in json.loads(grh)["entries"].values()])

    def test_unknown_declaration(self):
        entry = self.first("blueprint")
        with self.assertRaisesRegex(labels.LabelError, "unknown module"):
            self.render(self.edited(entry["name"], module="Nonexistent.Module"))

    def test_wrong_module(self):
        entry = self.first("blueprint")
        g = self.edited(entry["name"], module=GLOSSARY["entries"][-1]["module"])
        if g["entries"][-1]["module"] == entry["module"]:
            self.skipTest("same module")
        with self.assertRaisesRegex(labels.LabelError, "expected one declaration"):
            self.render(g)

    def test_unverified_caller(self):
        entry = self.first("caller")
        other = next(e for e in GLOSSARY["entries"] if e["name"] != entry["name"])
        g = self.edited(entry["name"], caller=other["name"], callerModule=other["module"])
        with self.assertRaisesRegex(labels.LabelError, "cannot confirm the compiled reference"):
            self.render(g)

    def test_line_mismatch(self):
        entry = self.first("blueprint")
        with self.assertRaisesRegex(labels.LabelError, "differs from the compiled source line"):
            self.render(self.edited(entry["name"], line=entry["line"] + 1))

    def test_missing_bottleneck(self):
        g = copy.deepcopy(GLOSSARY)
        g["entries"] = []
        with self.assertRaisesRegex(labels.LabelError, "bottlenecks have no label"):
            self.render(g)

    def test_draft_from_lean_statement_alone(self):
        entry = self.first("blueprint")
        rh, _, _, _ = self.render(self.edited(entry["name"], blueprint=None))
        edited = next(e for e in json.loads(rh)["entries"].values() if e["name"] == entry["name"])
        self.assertEqual(edited["line"], entry["line"])
        self.assertNotIn("blueprint", edited)

    def test_unknown_field(self):
        entry = self.first("blueprint")
        with self.assertRaisesRegex(labels.LabelError, "unknown fields"):
            self.render(self.edited(entry["name"], titel="typo"))

    def test_duplicate(self):
        g = copy.deepcopy(GLOSSARY)
        g["entries"].append(copy.deepcopy(self.first("blueprint")))
        with self.assertRaisesRegex(labels.LabelError, "duplicate label"):
            self.render(g)

    def test_revision(self):
        g = copy.deepcopy(GLOSSARY)
        g["revision"] = "0" * 40
        with self.assertRaisesRegex(labels.LabelError, "revision"):
            self.render(g)


if __name__ == "__main__":
    unittest.main()
