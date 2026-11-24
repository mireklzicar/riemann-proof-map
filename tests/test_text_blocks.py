"""Every on-demand text block must preserve the exact names in the search index."""

import gzip
import json
import unittest
from pathlib import Path

SITE = Path(__file__).resolve().parents[1] / "site"


class TextBlocks(unittest.TestCase):
    def test_names_match_original_tables(self):
        index = json.loads((SITE / "text/index.json").read_text())
        for key in ("names", "modules"):
            with self.subTest(key=key), gzip.open(SITE / f"{key}.txt.gz", "rb") as original:
                paths = sorted((SITE / "text").glob(f"{key}-*.gz"),
                               key=lambda p: int(p.stem.split("-")[1]))
                for number, path in enumerate(paths):
                    self.assertEqual(path.name, f"{key}-{number}.gz")
                    block = gzip.decompress(path.read_bytes()).split(b"\n")
                    if number < len(paths) - 1:
                        self.assertEqual(len(block), index["blockSize"])
                    for row in block:
                        self.assertEqual(row, original.readline().rstrip(b"\n"))
                self.assertEqual(original.read(), b"")


if __name__ == "__main__":
    unittest.main()
