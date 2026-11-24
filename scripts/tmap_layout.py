"""Lay out RH's immediate-dominator tree with TMAP (MinHash + LSH forest + OGDF FM3).

Hubs with many dominator children would collapse into discs, so each hub's
children are joined by a MinHash/LSH-forest k-NN minimum spanning tree
(TMAP's own construction) before the whole tree goes through TMAP's layout.
Runs in the separate Python 3.9 TMAP environment (env/tmap.yml) and writes
OUT/edges.npz and OUT/layout.npz.
"""

import argparse
import json
import re
import sqlite3
import time
from pathlib import Path

import numpy as np
import tmap as tm

STOP = {"of", "the", "to", "in", "on", "and", "is", "at", "for", "with", "by"}
CAMEL = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+")


def tokens(name, module):
    out = set()
    for part in name.split("."):
        for piece in part.split("_"):
            for w in CAMEL.findall(piece):
                w = w.lower()
                if len(w) > 1 and w not in STOP:
                    out.add(w)
    comps = module.split(".")
    for i, c in enumerate(comps):
        out.add("M%d:%s" % (i, c))
    out.add("MOD:" + module)
    return list(out) or ["∅"]


def capped_kruskal(size, rows, cols, vals, cap):
    """Kruskal's MST with a degree cap on every vertex except 0 (the hub).

    k-NN graphs have hubs (generic names close to many others); an uncapped MST
    turns them into stars. The hub's links (always present) keep the result spanning.
    """
    root = list(range(size))
    def find(v):
        while root[v] != v:
            root[v] = root[root[v]]
            v = root[v]
        return v
    deg = [0] * size
    out_a, out_b, out_w = [], [], []
    for e in np.argsort(vals, kind="stable").tolist():
        u, v = int(rows[e]), int(cols[e])
        if (u and deg[u] >= cap) or (v and deg[v] >= cap):
            continue
        ru, rv = find(u), find(v)
        if ru == rv:
            continue
        root[ru] = rv
        deg[u] += 1; deg[v] += 1
        out_a.append(u); out_b.append(v); out_w.append(float(vals[e]))
        if len(out_a) == size - 1:
            break
    return np.asarray(out_a, np.int64), np.asarray(out_b, np.int64), np.asarray(out_w)


def sibling_tree(hub, kids, totals, names, mods, modnames, mh, k):
    """Edges (a, b, w) forming a tree over hub+kids by TMAP's k-NN MST."""
    m = len(kids)
    # Identical token sets would all pick the same nearest neighbour (MinHash hubness),
    # so each group of duplicates becomes a small 4-ary tree in name order and only
    # one representative per group enters the LSH forest.
    groups = {}
    for j, c in enumerate(kids):
        groups.setdefault(frozenset(tokens(names[c], modnames[mods[c]])), []).append(j)
    reps, df, dt = [], [], []
    for members in groups.values():
        members.sort(key=lambda j: names[kids[j]])
        reps.append(members[0])
        for q in range(1, len(members)):
            df.append(members[(q - 1) // 4] + 1)
            dt.append(members[q] + 1)
    reps = np.asarray(reps, np.int64)
    f = np.zeros(0, np.int64); t = np.zeros(0, np.int64); w = np.zeros(0)
    if len(reps) > 1:
        fps = mh.batch_from_string_array(
            [sorted(tokens(names[kids[j]], modnames[mods[kids[j]]])) for j in reps]
        )
        lf = tm.LSHForest(mh_dim, 128)
        lf.batch_add(fps)
        lf.index()
        vf, vt, vw = tm.VectorUint(), tm.VectorUint(), tm.VectorFloat()
        lf.get_knn_graph(vf, vt, vw, k, 10)
        f = reps[np.asarray(vf, np.int64)] + 1
        t = reps[np.asarray(vt, np.int64)] + 1
        w = np.asarray(vw, np.float64) + 1e-3
    f = np.concatenate([f, np.asarray(df, np.int64)])
    t = np.concatenate([t, np.asarray(dt, np.int64)])
    w = np.concatenate([w, np.full(len(df), 1e-4)])
    keep = f != t
    # LSH finds no neighbours for generic names, so chain siblings in (module, name)
    # order as a fallback that is dearer than any similarity edge.
    order = sorted(range(m), key=lambda j: (modnames[mods[kids[j]]], names[kids[j]]))
    cf = np.asarray(order[:-1], np.int64) + 1
    ct = np.asarray(order[1:], np.int64) + 1
    cw = np.full(len(cf), 1.5)
    # The hub links straight to its heaviest children; any other hub link costs more
    # than the chain, so it is never needed.
    hf = np.zeros(m, np.int64)
    ht = np.arange(1, m + 1)
    hw = np.full(m, 3.0)
    hw[np.argsort(-totals[kids], kind="stable")[:HUB_LINKS]] = 1e-3
    rows = np.concatenate([f[keep], cf, hf])
    cols = np.concatenate([t[keep], ct, ht])
    vals = np.concatenate([w[keep], cw, hw])
    # Keep the cheapest copy of each undirected pair (the sparse constructor would sum them).
    lo, hi = np.minimum(rows, cols), np.maximum(rows, cols)
    key = lo * (m + 1) + hi
    pick = np.lexsort((vals, key))
    first = np.ones(len(pick), bool)
    first[1:] = key[pick][1:] != key[pick][:-1]
    rows, cols, vals = lo[pick][first], hi[pick][first], vals[pick][first]
    a, b, wt = capped_kruskal(m + 1, rows, cols, vals, MAX_DEGREE)
    assert len(a) == m, (hub, m, len(a))
    ids = np.concatenate([[hub], kids])
    return ids[a], ids[b], wt


mh_dim = 128
HUB_LINKS = 4
MAX_DEGREE = 8


def build(index, out, hub_min, k):
    t0 = time.time()
    out.mkdir(parents=True, exist_ok=True)
    meta = json.loads((index / "meta.json").read_text())
    modnames = meta["modnames"]
    n, root = meta["n"], meta["root"]
    parent = np.load(index / "parent.npy")
    totals = np.load(index / "totals.npy").astype(np.int64)
    off = np.load(index / "tree-off.npy")
    dst = np.load(index / "tree-dst.npy")
    deg = np.diff(off)
    db = sqlite3.connect(index / "nodes.sqlite")
    names = [None] * n
    mods = np.zeros(n, np.int32)
    for i, name, mod in db.execute("SELECT id,name,module FROM nodes"):
        names[i] = name
        mods[i] = mod
    print("loaded", round(time.time() - t0), flush=True)

    hubs = np.flatnonzero(deg > hub_min)
    star = np.ones(n, bool)  # child keeps its dominator edge
    star[root] = False
    S, T, W, kind = [], [], [], []
    mh = tm.Minhash(mh_dim)
    for j, h in enumerate(hubs[np.argsort(-deg[hubs])]):
        kids = dst[off[h] : off[h + 1]].astype(np.int64)
        a, b, w = sibling_tree(int(h), kids, totals, names, mods, modnames, mh, k)
        star[kids] = False
        S.append(a); T.append(b); W.append(w)
        kind.append(((a == h) | (b == h)).astype(np.uint8))  # 1 = hub link, 0 = sibling similarity
        if j < 20 or j % 1000 == 0:
            print("hub", j, len(hubs), int(deg[h]), round(time.time() - t0), flush=True)
    kids = np.flatnonzero(star)
    S.append(parent[kids].astype(np.int64)); T.append(kids); W.append(np.ones(len(kids)))
    kind.append(np.full(len(kids), 1, np.uint8))
    S, T, W, kind = map(np.concatenate, (S, T, W, kind))
    assert len(S) == n - 1
    np.savez(out / "edges.npz", s=S, t=T, w=W, dominator=kind)
    print("edges", len(S), "similarity", int((kind == 0).sum()), round(time.time() - t0), flush=True)

    cfg = tm.LayoutConfiguration()
    cfg.k = k
    cfg.node_size = 1 / 26
    cfg.mmm_repeats = 2
    cfg.sl_extra_scaling_steps = 5
    cfg.sl_scaling_type = tm.RelativeToAvgLength
    cfg.fme_threads = 8
    edges = list(zip(S.tolist(), T.tolist(), (W * 0 + 1).tolist()))
    x, y, s, t, _ = tm.layout_from_edge_list(n, edges, cfg, create_mst=False)
    x = np.asarray(x, np.float32)
    y = np.asarray(y, np.float32)
    print("layout", round(time.time() - t0), flush=True)
    np.savez(out / "layout.npz", x=x, y=y, s=np.asarray(s), t=np.asarray(t))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("index", type=Path)
    p.add_argument("out", type=Path)
    p.add_argument("--hub-min", type=int, default=12)
    p.add_argument("--k", type=int, default=10)
    a = p.parse_args()
    build(a.index, a.out, a.hub_min, a.k)
