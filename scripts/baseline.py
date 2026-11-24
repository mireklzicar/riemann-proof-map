"""Load GRAPH/consts.tsv.zst with the drive's graph loader and write GRAPH/baseline.pkl.

The pickle holds (graph, roots, five-target reach, RH reach) and refers to classes in
DRIVE/tools/cone.py, so every later step adds DRIVE/tools to the import path. Only load
a pickle you built yourself.
"""

import argparse
import pickle
import sys
from pathlib import Path


def main(graph, drive):
    sys.path.insert(0, str(drive / "tools"))
    import common
    import cone

    g = cone.load_graph(str(graph), say=lambda s: print(s, flush=True))
    assert not g.errors and len(g.modnames) == 175_187
    roots = cone.find_names(g, common.TARGETS)
    assert len(roots) == 5
    mark = cone.reach(g, list(roots.values()))
    rh = cone.reach(g, [roots["riemannHypothesis"]])
    print("reachable from the five targets", sum(mark), "from RH", sum(rh), flush=True)
    tmp = graph / "baseline.pkl.tmp"
    with tmp.open("wb") as f:
        pickle.dump((g, roots, mark, rh), f, protocol=5)
    tmp.replace(graph / "baseline.pkl")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("graph", type=Path, help="directory holding consts.tsv.zst")
    p.add_argument("drive", type=Path, help="GRH simplification drive checkout")
    a = p.parse_args()
    main(a.graph, a.drive)
