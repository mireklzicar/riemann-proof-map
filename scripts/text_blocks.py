"""Pack small random-access slices of the exact names used in the two views."""
import argparse
import gzip
import json
from pathlib import Path

import numpy as np

BLOCK_SIZE = 8192


def read_names(path):
    return gzip.decompress(path.read_bytes()).decode().split("\n")


def build(site):
    out = site / "text"
    out.mkdir(exist_ok=True)
    names = read_names(site / "names.txt.gz")
    modules = read_names(site / "modules.txt.gz")
    for label, rows in (("names", names), ("modules", modules)):
        for start in range(0, len(rows), BLOCK_SIZE):
            data = "\n".join(rows[start:start + BLOCK_SIZE]).encode()
            (out / f"{label}-{start // BLOCK_SIZE}.gz").write_bytes(gzip.compress(data, mtime=0))

    endpoints = json.loads((site / "endpoints.json").read_text())
    index = {"blockSize": BLOCK_SIZE}
    for goal, folder in (("rh", site), ("grh", site / "grh")):
        manifest = json.loads((folder / "manifest.json").read_text())
        fields = {a["key"]: a for a in manifest["arrays"]}
        raw = gzip.decompress((folder / "graph.bin.gz").read_bytes())

        def field(key):
            spec = fields[key]
            return np.frombuffer(raw, spec["dtype"], spec["length"], spec["offset"])

        node_modules = field("module")
        local = names if goal == "rh" else read_names(folder / "names.txt.gz")
        first = set(endpoints[goal]["exclusive"] + endpoints[goal]["ending"] + endpoints[goal]["route"])
        first.update(b["id"] for b in manifest["branches"])
        if goal == "grh":
            mapping = field("rhId")
            assert all(local[i] == names[v] if v >= 0 else i in first for i, v in enumerate(mapping))
        index[goal] = [[i, local[i], modules[node_modules[i]]] for i in sorted(first)]
    (out / "index.json").write_text(json.dumps(index, separators=(",", ":"), ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("site", type=Path)
    build(parser.parse_args().site)
