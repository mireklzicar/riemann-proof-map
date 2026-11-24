"""Build the Dirichlet GRH view and verify both final routes against the compiled graph.

Reads the classical RH packs from WEB and writes WEB/grh/{manifest.json, graph.bin.gz,
names.txt.gz} and WEB/endpoints.json. Shared declarations keep their RH coordinates;
the GRH array rhId maps each GRH node to its RH node (-1 for GRH-only declarations).
"""

import argparse
import gzip
import json
import pickle
import sys
from pathlib import Path

import igraph
import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import breadth_first_order

from pack import BRANCH_PIECES, branches

TARGETS = {"rh": "riemannHypothesis", "grh": "LFunction_eq_zero_re"}
JOIN = "UpperTheory.FinalTheorems.everyCharacter"


def write_arrays(out, manifest, arrays):
    manifest["arrays"] = []
    with gzip.open(out / "graph.bin.gz", "wb", compresslevel=6) as f:
        for key, a in arrays.items():
            f.write(bytes(-f.tell() % 4))
            manifest["arrays"].append(
                dict(key=key, dtype=str(a.dtype), offset=f.tell(), length=len(a))
            )
            f.write(a.tobytes())
        manifest["bytes"] = f.tell()


def generate(graph, campaign, web):
    sys.path.insert(0, str(campaign / "tools"))
    with graph.open("rb") as f:
        g, roots, _, _ = pickle.load(f)

    def adjacency(offset, dest):
        return csr_matrix(
            (np.ones(len(dest), np.uint8), np.asarray(dest), np.asarray(offset)),
            shape=(g.n, g.n),
        )

    edges = adjacency(g.v_off, g.v_edges) + adjacency(g.t_off, g.t_edges)
    join = g.names.index(JOIN)
    routes = {}
    live = {}
    for key, name in TARGETS.items():
        visited, parent = breadth_first_order(edges, roots[name])
        live[key] = np.sort(visited)
        path = [join]
        while path[-1] != roots[name]:
            previous = int(parent[path[-1]])
            assert previous >= 0 and edges[previous, path[-1]]
            path.append(previous)
        # These body-reference chains expose the final mathematical deduction.
        tail = (
            ["rhOfAll", "Formalism.VW.rh_of_every", "Formalism.VW.rh_of_right"]
            if key == "rh"
            else ["claimAll", "Claim.strip", "Claim.prim_reflect"]
        )
        ending = [roots[name], *(g.names.index(n) for n in tail)]
        for caller, dependency in zip(ending, ending[1:]):
            assert dependency in g.v_edges[g.v_off[caller] : g.v_off[caller + 1]]
        routes[key] = dict(
            route=np.searchsorted(live[key], path[::-1]).tolist(),
            ending=np.searchsorted(live[key], ending).tolist(),
            total=len(visited),
        )
    original, active = live["rh"], live["grh"]
    common, ri, gi = np.intersect1d(original, active, return_indices=True)
    routes["shared"] = len(common)
    for key, vertices in live.items():
        difference = np.setdiff1d(vertices, common, assume_unique=True)
        local = np.searchsorted(vertices, difference)
        rows, cols = edges[difference][:, difference].nonzero()
        routes[key]["exclusive"] = local.tolist()
        routes[key]["references"] = np.column_stack([local[rows], local[cols]]).tolist()
        print(key, [g.names[i] for i in difference], flush=True)
    manifest = json.loads((web / "manifest.json").read_text())
    raw = gzip.decompress((web / "graph.bin.gz").read_bytes())
    old = {
        a["key"]: np.frombuffer(raw, a["dtype"], a["length"], a["offset"])
        for a in manifest["arrays"]
    }
    rh_names = gzip.decompress((web / "names.txt.gz").read_bytes()).decode().split("\n")
    assert all(
        g.names[idx] == name for idx, name in zip(original, rh_names, strict=True)
    )
    n = len(active)
    root = int(np.searchsorted(active, roots[TARGETS["grh"]]))
    graph = edges[active][:, active].tocsr()
    rows = np.repeat(np.arange(n, dtype=np.int32), np.diff(graph.indptr))
    dom = np.array(
        igraph.Graph(
            n, np.column_stack([rows, graph.indices]), directed=True
        ).dominator(root),
        np.int32,
    )
    dom[root] = -1
    v = np.flatnonzero(dom >= 0)
    tree = csr_matrix((np.ones(n - 1, np.uint8), (dom[v], v)), shape=(n, n))
    order = breadth_first_order(tree, root, return_predecessors=False)
    assert len(order) == n
    totals = np.ones(n, np.uint32)
    for i in order[:0:-1]:
        totals[dom[i]] += totals[i]
    assert totals[root] == n
    depth = np.zeros(n, np.uint8)
    for i in order[1:]:
        depth[i] = 1 + depth[dom[i]]
    blocks, owned = branches(root, dom, order, BRANCH_PIECES)
    branch = np.zeros(n, np.uint8)
    marker = {i: j for j, i in enumerate(blocks)}
    for i in order:
        branch[i] = marker[i] if i in marker else branch[dom[i]]

    # Keep common declarations at their RH coordinates. Only reuse horizontal
    # layout edges within a genuine GRH sibling set. All other edges follow GRH dominance.
    to_grh = np.full(len(original), -1, np.int32)
    to_grh[ri] = gi
    to_rh = np.full(n, -1, np.int32)
    to_rh[gi] = ri
    lpar = dom.copy()
    prev = old["lpar"][ri]
    p = to_grh[prev.clip(min=0)]
    same = (prev >= 0) & (p >= 0) & (dom[gi] == dom[p.clip(min=0)]) & (gi != root)
    lpar[gi[same]] = p[same]
    layout = csr_matrix((np.ones(n - 1, np.uint8), (lpar[v], v)), shape=(n, n))
    assert len(breadth_first_order(layout, root, return_predecessors=False)) == n
    x = np.zeros(n, np.float32)
    y = x.copy()
    x[gi] = old["x"][ri]
    y[gi] = old["y"][ri]
    extra = np.flatnonzero(to_rh < 0)
    # Display the additional terminal deductions near the root of the original layout.
    angles = np.arange(len(extra)) * 2.4
    x[extra] = old["x"][manifest["root"]] + 0.035 * np.cos(angles)
    y[extra] = old["y"][manifest["root"]] + 0.035 * np.sin(angles)
    mods = np.asarray(g.mods, dtype=np.uint32)[active]
    dirs = {d["name"]: j for j, d in enumerate(manifest["dirs"])}
    moddirs = np.array(
        [dirs.get(".".join(m.split(".")[:2]), 255) for m in g.modnames], np.uint8
    )
    kinds = {k: j for j, k in enumerate(manifest["kinds"])}
    authored = np.ones(n, np.uint8)
    authored[gi] = old["authored"][ri]
    for i in extra:
        name = g.names[active[i]]
        authored[i] = not (name.startswith("_") or "._" in name)
    arrays = dict(
        x=x,
        y=y,
        lpar=lpar,
        idom=dom,
        totals=totals,
        module=mods,
        domedge=(lpar == dom).astype(np.uint8),
        authored=authored,
        depth=depth,
        branch=branch,
        dir=moddirs[mods],
        kind=np.array([kinds[g.kinds[i]] for i in active], np.uint8),
        rhId=to_rh,
    )
    manifest.update(
        n=n,
        root=root,
        edges=graph.nnz,
        modules=len(np.unique(mods)),
        max_depth=int(depth.max()),
        spine=blocks,
        similarity_edges=int((lpar != dom).sum()),
        branches=[
            dict(
                id=i,
                name=g.names[active[i]].split(".")[-1],
                full=g.names[active[i]],
                size=int(owned[i]),
            )
            for i in blocks
        ],
    )
    for j, d in enumerate(manifest["dirs"]):
        d["size"] = int((arrays["dir"] == j).sum())
    out = web / "grh"
    out.mkdir(exist_ok=True)
    write_arrays(out, manifest, arrays)
    (out / "manifest.json").write_text(json.dumps(manifest))
    with gzip.open(out / "names.txt.gz", "wt", encoding="utf8") as f:
        f.write("\n".join(g.names[i] for i in active))
    (web / "endpoints.json").write_text(json.dumps(routes, indent=2))
    print(routes, flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("graph", type=Path, help="baseline.pkl")
    p.add_argument("campaign", type=Path, help="GRH simplification drive checkout")
    p.add_argument("web", type=Path, help="site directory holding the RH packs")
    a = p.parse_args()
    generate(a.graph, a.campaign, a.web)
