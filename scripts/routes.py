"""Pack actual reference paths and dependency stages for the two published endpoints."""

import argparse
import gzip
import json
import pickle
import sys
from pathlib import Path

import numpy as np
from numba import njit
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import breadth_first_order, connected_components


@njit
def reference_levels(component, members, starts, offsets, dst, incoming, src):
    """Choose a longest path through the component DAG, with real edges inside each SCC."""
    levels = np.zeros(len(starts) - 1, np.int32)
    down = np.full(len(component), -1, np.int32)
    seen = np.zeros(len(component), np.uint8)
    q = np.empty(len(component), np.int32)
    for c in range(len(levels)):
        group = members[starts[c] : starts[c + 1]]
        max_level = 0
        for v in group:
            for k in range(offsets[v], offsets[v + 1]):
                child = component[dst[k]]
                if child != c:
                    assert child < c  # SciPy's Tarjan order is sink-first.
                    max_level = max(max_level, 1 + levels[child])
        levels[c] = max_level
        count = 0
        for v in group:
            for k in range(offsets[v], offsets[v + 1]):
                w = dst[k]
                if component[w] != c and levels[component[w]] + 1 == max_level:
                    down[v] = w
                    q[count] = v
                    count += 1
                    seen[v] = 1
                    break
        if count == 0:
            q[0] = group[0]
            seen[group[0]] = 1
            count = 1
        pos = 0
        while pos < count:
            v = q[pos]
            pos += 1
            for k in range(incoming[v], incoming[v + 1]):
                w = src[k]
                if component[w] == c and not seen[w]:
                    down[w] = v
                    seen[w] = 1
                    q[count] = w
                    count += 1
        assert count == len(group)
    return down, levels[component]


def build(graph_file, campaign, site):
    sys.path.insert(0, str(campaign / "tools"))
    with graph_file.open("rb") as f:
        g, roots, _, _ = pickle.load(f)

    def matrix(off, dst):
        return csr_matrix(
            (np.ones(len(dst), np.uint8), np.asarray(dst), np.asarray(off)),
            shape=(g.n, g.n),
        )

    full = matrix(g.t_off, g.t_edges) + matrix(g.v_off, g.v_edges)
    for target, out in [
        ("riemannHypothesis", site),
        ("LFunction_eq_zero_re", site / "grh"),
    ]:
        live = np.sort(
            breadth_first_order(full, roots[target], return_predecessors=False)
        )
        root = int(np.searchsorted(live, roots[target]))
        graph = full[live][:, live].tocsr()
        graph.sort_indices()
        order, up = breadth_first_order(graph, root)
        assert len(order) == len(live)
        up[root] = -1
        rev = graph.T.tocsr()
        n, c = connected_components(graph, directed=True, connection="strong")
        members = np.argsort(c, kind="stable")
        starts = np.r_[0, np.cumsum(np.bincount(c, minlength=n))]
        down, level = reference_levels(
            c, members, starts, graph.indptr, graph.indices, rev.indptr, rev.indices
        )
        assert level[root] == level.max() and 0 < level[root] < 65536
        with gzip.open(out / "names.txt.gz", "rt", encoding="utf8") as f:
            assert all(
                name == g.names[v]
                for name, v in zip(f.read().split("\n"), live, strict=True)
            )
        idx = np.arange(len(live))
        assert np.all(graph[up[up >= 0], idx[up >= 0]].A1) and np.all(
            graph[idx[down >= 0], down[down >= 0]].A1
        )
        arrays = (up.astype("<i4"), down.astype("<i4"), level.astype("<u2"))
        payload = b"".join(a.tobytes() for a in arrays)
        (out / "routes.bin.gz").write_bytes(gzip.compress(payload, compresslevel=6, mtime=0))
        print(target, len(live), int(level[root]), flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for key in ("graph", "campaign", "site"):
        p.add_argument(key, type=Path)
    a = p.parse_args()
    build(a.graph, a.campaign, a.site)
