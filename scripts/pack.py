"""Pack the TMAP layout and structure index into the classical RH static files.

Writes SITE/manifest.json, graph.bin.gz, names.txt.gz and modules.txt.gz. The Dirichlet
GRH view, routes, source spans and labels are added by later steps (see README).
"""

import argparse
import gzip
import heapq
import json
import sqlite3
from collections import Counter
from pathlib import Path

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import breadth_first_order

BRANCH_PIECES = 26
PALETTE_DIRS = 15


# Organisational path components that carry no mathematical topic.
GENERIC = {
    "Proofs", "Foundations", "Definitions", "CoreStatements", "Imports", "Basic", "Defs",
    "Aux", "Internal", "Common", "Core", "Setup", "Statement", "Statements", "Main",
}
REGION_LEVELS = [(8, 6000), (24, 800), (72, 120)]  # (grid cells per side, minimum declarations)


def topics(module):
    """Mathematical topic path of a module, dropping its top-level directory."""
    return [c for c in module.split(".")[1:] if c not in GENERIC]


def regions(x, y, node_topics):
    """Map-style area names: the dominant topic per grid cell, merged across adjacent cells."""
    out = []
    for level, (g, least) in enumerate(REGION_LEVELS):
        names = {}
        tid = np.array([names.setdefault(t[level], len(names)) if len(t) > level else -1 for t in node_topics], np.int64)
        gx = np.clip(((x + 1) / 2 * g).astype(np.int64), 0, g - 1)
        gy = np.clip(((y + 1) / 2 * g).astype(np.int64), 0, g - 1)
        ok = tid >= 0
        key = ((gy * g + gx) * len(names) + tid)[ok]
        uniq, inv, cnt = np.unique(key, return_inverse=True, return_counts=True)
        sx = np.bincount(inv, x[ok]); sy = np.bincount(inv, y[ok])
        cell, top = uniq // len(names), uniq % len(names)
        total = np.bincount(cell, cnt, minlength=g * g)
        best = {}
        for k in np.argsort(-cnt, kind="stable"):
            c = int(cell[k])
            if c not in best and cnt[k] >= 0.3 * total[c]:
                best[c] = k
        # Union adjacent cells that share their dominant topic.
        parent = {c: c for c in best}
        def find(c):
            while parent[c] != c:
                parent[c] = parent[parent[c]]
                c = parent[c]
            return c
        for c, k in best.items():
            for d in (c + 1, c + g, c + g + 1, c + g - 1):
                if d in best and top[best[d]] == top[k] and abs(d % g - c % g) <= 1:
                    parent[find(d)] = find(c)
        groups = {}
        for c, k in best.items():
            a = groups.setdefault(find(c), [0, 0.0, 0.0, int(top[k])])
            a[0] += int(cnt[k]); a[1] += sx[k]; a[2] += sy[k]
        inverse = {v: k for k, v in names.items()}
        for size, ax, ay, t in groups.values():
            if size >= least:
                out.append([level, round(ax / size, 5), round(ay / size, 5), inverse[t], size])
    return out


def branches(root, idom, torder, count):
    """Partition the dominator tree bottom-up into connected pieces of about n/count.

    A declaration starts a new piece once the not-yet-claimed part of its dominated
    subtree reaches the threshold, so nested pieces are allowed and every vertex is covered.
    """
    n = len(idom)
    threshold = n / count
    rem = np.ones(n, np.int64)
    heads = []
    for v in torder[::-1]:
        if rem[v] >= threshold or v == root:
            heads.append(int(v))
            claimed = rem[v]
            rem[v] = 0
        else:
            claimed = 0
        if v != root:
            rem[idom[v]] += rem[v]
        rem[v] = claimed
    heads.sort(key=lambda v: -rem[v])
    return heads, rem


def main(index, layout, out):
    out.mkdir(parents=True, exist_ok=True)
    meta = json.loads((index / "meta.json").read_text())
    modnames = meta["modnames"]
    n, root = meta["n"], meta["root"]
    idom = np.load(index / "parent.npy").astype(np.int32)
    totals = np.load(index / "totals.npy").astype(np.int64)
    off = np.load(index / "tree-off.npy")
    dst = np.load(index / "tree-dst.npy")
    lay = np.load(layout / "layout.npz")
    e = np.load(layout / "edges.npz")
    x, y = lay["x"].astype(np.float64), lay["y"].astype(np.float64)
    # Normalise to a unit box around the central mass.
    cx, cy = np.median(x), np.median(y)
    r = max(np.percentile(np.abs(x - cx), 99.9), np.percentile(np.abs(y - cy), 99.9))
    x, y = ((x - cx) / r).astype(np.float32), ((y - cy) / r).astype(np.float32)

    # Layout parent: orient the TMAP edges away from RH.
    s, t, dom = e["s"], e["t"], e["dominator"]
    a = coo_matrix((np.ones(len(s)), (s, t)), shape=(n, n)).tocsr()
    a = (a + a.T).tocsr()
    order, lpar = breadth_first_order(a, root, directed=False)
    assert len(order) == n
    lpar = lpar.astype(np.int32)
    lpar[root] = -1
    # Is the layout edge into each vertex an actual dominator edge?
    domedge = (lpar == idom).astype(np.uint8)
    domedge[root] = 1

    depth = np.zeros(n, np.int32)
    torder = breadth_first_order(
        coo_matrix((np.ones(len(dst)), (np.repeat(np.arange(n), np.diff(off)), dst)), shape=(n, n)).tocsr(),
        root,
        return_predecessors=False,
    )
    for v in torder[1:]:
        depth[v] = depth[idom[v]] + 1

    def children(u):
        return dst[off[u] : off[u + 1]]

    roots, owned = branches(root, idom, torder, BRANCH_PIECES)
    assert len(roots) <= 255 and owned[roots].sum() == n
    spine = roots
    head = np.full(n, -1, np.int32)
    head[roots] = np.arange(len(roots))
    branch = np.zeros(n, np.uint8)
    for v in torder:
        branch[v] = head[v] if head[v] >= 0 else branch[idom[v]]

    db = sqlite3.connect(index / "nodes.sqlite")
    shorts = [""] * n
    names = [""] * n
    mods = np.zeros(n, np.uint32)
    kinds = np.zeros(n, np.uint8)
    kind_names = ["thm", "def", "ind", "ctor", "rec"]
    authored = np.zeros(n, np.uint8)
    for i, name, short, mod, kind, auth in db.execute("SELECT id,name,short,module,kind,authored FROM nodes"):
        authored[i] = auth
        shorts[i] = short.replace("\n", " ")
        names[i] = name.replace("\n", " ")
        mods[i] = mod
        kinds[i] = kind_names.index(kind)
    top2 = [".".join(m.split(".")[:2]) for m in modnames]
    counts = Counter(top2[m] for m in mods.tolist())
    dir_names = [d for d, _ in counts.most_common(PALETTE_DIRS)]
    lookup = {d: k for k, d in enumerate(dir_names)}
    mod_dir = np.array([lookup.get(d, 255) for d in top2], np.uint8)
    dirs = mod_dir[mods]

    mod_topics = [topics(m) for m in modnames]
    region_labels = regions(x.astype(np.float64), y.astype(np.float64), [mod_topics[m] for m in mods.tolist()])
    arrays = dict(
        x=x, y=y, lpar=lpar, idom=idom, totals=totals.astype(np.uint32), module=mods,
        domedge=domedge, authored=authored, depth=np.minimum(depth, 255).astype(np.uint8), branch=branch, dir=dirs, kind=kinds,
    )
    manifest = dict(
        n=n, root=root, revision=meta["revision"], edges=meta["edges"], modules=meta["modules"],
        similarity_edges=int((domedge == 0).sum()), max_depth=int(depth.max()),
        arrays=[], kinds=kind_names,
        branches=[dict(id=int(b), name=shorts[b], full=names[b], size=int(owned[b])) for b in roots],
        spine=[int(u) for u in spine],
        regions=region_labels,
        dirs=[dict(name=d, size=int((dirs == k).sum())) for k, d in enumerate(dir_names)],
    )
    offset = 0
    with gzip.open(out / "graph.bin.gz", "wb", compresslevel=6) as f:
        for key, arr in arrays.items():
            arr = np.ascontiguousarray(arr)
            pad = (-offset) % 4
            f.write(b"\0" * pad)
            offset += pad
            manifest["arrays"].append(dict(key=key, dtype=str(arr.dtype), offset=offset, length=len(arr)))
            f.write(arr.tobytes())
            offset += arr.nbytes
    manifest["bytes"] = offset
    with gzip.open(out / "names.txt.gz", "wt", encoding="utf-8") as f:
        f.write("\n".join(names))
    with gzip.open(out / "modules.txt.gz", "wt", encoding="utf-8") as f:
        f.write("\n".join(modnames))
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False))
    print(json.dumps({k: v for k, v in manifest.items() if k not in ("arrays", "spine", "regions")}, indent=1)[:3000])
    from collections import Counter as C
    print("regions", C(r[0] for r in region_labels), [r[3] for r in region_labels if r[0] == 0])


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("index", type=Path, help="structure index directory")
    p.add_argument("layout", type=Path, help="directory with layout.npz and edges.npz")
    p.add_argument("out", type=Path, help="site output directory")
    a = p.parse_args()
    main(a.index, a.layout, a.out)
