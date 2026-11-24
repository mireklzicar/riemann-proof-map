"""Index the compiled declaration graph reachable from classical RH.

Writes INDEX/meta.json, nodes.sqlite and NumPy arrays: reference CSR matrices in both
directions (uses-*, users-*), the immediate-dominator tree rooted at riemannHypothesis
(parent, tree-*), subtree sizes (totals), a breadth-first reference path (path) and the
number of distinct caller modules (callerMods). tmap_layout.py and pack.py read it.
"""

import argparse
import json
import pickle
from pathlib import Path
import sqlite3
import sys

import igraph
import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import breadth_first_order
from numba import njit

REVISION = "40e56bab026552e089d7afcfeff08d2defb9c005"  # LEAN_REV in pins.sh


@njit
def subtree_sizes(order, parents):
    totals = np.ones(len(order), dtype=np.int32)
    for i in range(len(order) - 1, 0, -1):
        n = order[i]
        totals[parents[n]] += totals[n]
    return totals


def store_csr(out, label, m):
    m.sort_indices()
    for suffix, a in [("off", m.indptr), ("dst", m.indices), ("kind", m.data)]:
        np.save(out / f"{label}-{suffix}.npy", a)


def index(graph, campaign, out):
    out.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(campaign / "tools"))
    with graph.open("rb") as src:
        g, roots, _, rh = pickle.load(src)
    live = np.flatnonzero(np.frombuffer(rh, np.uint8))
    n = len(live)
    old_to_new = np.full(g.n, -1, np.int32)
    old_to_new[live] = np.arange(n)
    root = int(old_to_new[roots["riemannHypothesis"]])

    def channel(offsets, edges, kind):
        m = csr_matrix(
            (np.ones(len(edges), np.uint8), np.asarray(edges), np.asarray(offsets)),
            shape=(g.n, g.n),
        )[live]
        m.sum_duplicates()
        m.data.fill(kind)
        dest = old_to_new[m.indices]
        assert dest.min() >= 0
        return csr_matrix((m.data, dest, m.indptr), shape=(n, n))

    m = channel(g.v_off, g.v_edges, 1) + channel(g.t_off, g.t_edges, 2)
    m.sort_indices()
    assert m.data.max() <= 3
    incoming = m.T.tocsr()
    store_csr(out, "uses", m)
    store_csr(out, "users", incoming)
    row = np.repeat(np.arange(n, dtype=np.int32), np.diff(m.indptr))
    print("dominator computation", n, m.nnz, flush=True)
    graph_ig = igraph.Graph(
        n=n, edges=np.column_stack([row, m.indices]).astype("int64"), directed=True
    )
    parents = np.array(graph_ig.dominator(root, mode="out"), np.int32)
    del graph_ig
    parents[root] = -1
    keep = parents >= 0
    assert keep.sum() == n - 1
    nodes = np.arange(n, dtype=np.int32)[keep]
    tree = csr_matrix((np.ones(n - 1, np.uint8), (parents[keep], nodes)), shape=m.shape)
    order = breadth_first_order(tree, root, return_predecessors=False)
    assert len(order) == n
    totals = subtree_sizes(order, parents)
    assert totals[root] == n
    store_csr(out, "tree", tree)
    # A direct reference path for any selected declaration.
    order, path = breadth_first_order(m, root)
    assert len(order) == n
    path[root] = -1
    mods = np.asarray(g.mods, dtype=np.int32)[live]
    # Count distinct source modules referring directly to each destination.
    pairs = np.unique(m.indices.astype(np.int64) * len(g.modnames) + mods[row])
    families = np.bincount(pairs // len(g.modnames), minlength=n).astype(np.int32)
    del pairs, row, order
    usercount = np.diff(incoming.indptr)
    for key, arr in [
        ("parent", parents),
        ("path", path),
        ("totals", totals),
        ("callerMods", families),
    ]:
        np.save(out / (key + ".npy"), arr)
    db = sqlite3.connect(out / "nodes.sqlite")
    db.executescript(
        "DROP TABLE IF EXISTS nodes; CREATE TABLE nodes(id INTEGER PRIMARY KEY, name TEXT, short TEXT, module INTEGER, kind TEXT, authored INTEGER, exclusive INTEGER, users INTEGER, modules INTEGER);"
    )

    def records():
        for i, j in enumerate(live):
            name = g.names[j]
            short = name.rsplit(".", 1)[-1]
            # Conservative name filter for UI rankings only. Always compute on the full graph.
            named = not (
                name.startswith("_")
                or "._" in name
                or short.startswith(("eq_", "match_", "proof_"))
                or short.isdigit()
            )
            yield i, name, short, int(mods[i]), g.kinds[j], named, int(
                totals[i] - 1
            ), int(usercount[i]), int(families[i])

    db.executemany("INSERT INTO nodes VALUES (?,?,?,?,?,?,?,?,?)", records())
    db.executescript(
        "CREATE INDEX full_name ON nodes(name COLLATE NOCASE);CREATE INDEX short_name ON nodes(short COLLATE NOCASE);CREATE INDEX bottlenecks ON nodes(authored,exclusive DESC,id);CREATE INDEX hubs ON nodes(authored,modules DESC,users DESC,id);"
    )
    db.commit()
    meta = dict(
        root=root,
        n=n,
        edges=m.nnz,
        modules=len(set(mods.tolist())),
        revision=REVISION,
        modnames=g.modnames,
    )
    (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False))
    for key in ["exclusive", "modules"]:
        print(
            key,
            db.execute(
                f"SELECT short,exclusive,modules FROM nodes WHERE authored=1 ORDER BY {key} DESC LIMIT 25"
            ).fetchall(),
            flush=True,
        )
    db.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("graph", type=Path, help="baseline.pkl")
    p.add_argument("campaign", type=Path, help="GRH simplification drive checkout")
    p.add_argument("out", type=Path, help="index directory")
    a = p.parse_args()
    index(a.graph, a.campaign, a.out)
