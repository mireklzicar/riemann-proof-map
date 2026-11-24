"""Extract editor source ranges only. The public viewer fetches Lean text on demand."""

import argparse
import gzip
import json
from pathlib import Path
import numpy as np


def load_decls(path):
    # The declaration dictionary precedes the much larger cross-reference table.
    with path.open("rb") as f:
        raw = bytearray()
        while chunk := f.read(16384):
            raw.extend(chunk)
            end = raw.find(b',"directImports"')
            if end >= 0 and raw.startswith(b'{"decls":'):
                return json.loads(raw[:end] + b"}")["decls"]
        return json.loads(raw)["decls"]


def build(site, lib):
    with gzip.open(site / "modules.txt.gz", "rt", encoding="utf8") as f:
        modules = f.read().split("\n")
    for out in (site, site / "grh"):
        manifest = json.loads((out / "manifest.json").read_text())
        blob = gzip.decompress((out / "graph.bin.gz").read_bytes())
        field = next(a for a in manifest["arrays"] if a["key"] == "module")
        m = np.frombuffer(blob, "<u4", field["length"], field["offset"])
        with gzip.open(out / "names.txt.gz", "rt", encoding="utf8") as f:
            names = f.read().split("\n")
        spans = np.zeros((len(m), 4), dtype="<i4")
        order = np.argsort(m, kind="stable")
        breaks = np.r_[0, 1 + np.flatnonzero(np.diff(m[order])), len(m)]
        for start, end in zip(breaks, breaks[1:]):
            module = modules[m[order[start]]]
            decls = load_decls(lib / Path(*module.split(".")).with_suffix(".ilean"))
            for i in order[start:end]:
                original = name = names[i]
                while name not in decls and "." in name:
                    name = name.rsplit(".", 1)[0]
                if name in decls:
                    sl, sc, el, ec = decls[name][:4]
                    spans[i] = [
                        (sl + 1) if name == original else -(sl + 1),
                        sc,
                        el + 1,
                        ec,
                    ]
        with gzip.open(out / "source-spans.bin.gz", "wb", compresslevel=6) as f:
            f.write(spans.tobytes())
        print(
            out.name,
            "exact",
            np.sum(spans[:, 0] > 0),
            "enclosing",
            np.sum(spans[:, 0] < 0),
            flush=True,
        )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("site", type=Path)
    p.add_argument("lib", type=Path)
    a = p.parse_args()
    build(a.site, a.lib)
