"""Pack labels/annotations.json into both endpoint views without rebuilding the graph.

The packer resolves each label against the published static data in a site directory.
It reads the classical RH packs, resolves every (module, declaration) pair to one node,
checks bottleneck coverage and source lines, and writes

  SITE/annotations.json      keyed by classical RH node id
  SITE/grh/annotations.json  keyed by Dirichlet GRH node id

The script uses only the Python standard library. With --index it also checks every
cited caller against the full reference graph from scripts/structure_index.py. Without
--index, a cited caller is accepted only when the published packs already contain
that compiled reference: a caller already verified in SITE/annotations.json, or a
reference step in routes.bin.gz.
"""

import argparse
import gzip
import json
import os
import sys
from array import array
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LABELS = ROOT / "labels" / "annotations.json"
BOTTLENECK = 10_000  # Declarations strictly below a node in the classical RH dominator tree.
REQUIRED = ("name", "module", "title", "statement", "role", "line")
OPTIONAL = ("caption", "blueprint", "caller", "callerModule")
TYPECODES = {"uint8": "B", "uint16": "H", "int32": "i", "uint32": "I", "float32": "f"}


class LabelError(ValueError):
    pass


def read_gz(path):
    with gzip.open(path, "rb") as f:
        return f.read()


def typed(raw, dtype, offset=0, length=None):
    a = array(TYPECODES[dtype])
    size = a.itemsize
    if length is None:
        length = (len(raw) - offset) // size
    a.frombytes(raw[offset : offset + length * size])
    if len(a) != length:
        raise LabelError(f"Truncated {dtype} array at offset {offset}")
    if sys.byteorder != "little":
        a.byteswap()
    return a


class View:
    """The arrays one endpoint view needs for label packing."""

    def __init__(self, folder, keys):
        self.folder = folder
        self.manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        raw = read_gz(folder / "graph.bin.gz")
        if len(raw) != self.manifest["bytes"]:
            raise LabelError(f"{folder / 'graph.bin.gz'} does not match its manifest")
        fields = {a["key"]: a for a in self.manifest["arrays"]}
        self.n = self.manifest["n"]
        self.arrays = {}
        for key in keys:
            a = fields[key]
            if a["length"] != self.n:
                raise LabelError(f"Array {key} has {a['length']} entries for {self.n} nodes")
            self.arrays[key] = typed(raw, a["dtype"], a["offset"], a["length"])


def load_names(path, n):
    names = read_gz(path).decode("utf-8").split("\n")
    if len(names) != n:
        raise LabelError(f"{path} has {len(names)} names for {n} nodes")
    return names


class RouteEdges:
    """Test recorded caller/dependency pairs without expanding millions of Python tuples."""

    def __init__(self, folder, n):
        payload = read_gz(folder / "routes.bin.gz")
        if len(payload) != 10 * n:
            raise LabelError("Unexpected route index size")
        self.up = typed(payload, "int32", 0, n)
        self.down = typed(payload, "int32", 4 * n, n)

    def __contains__(self, edge):
        caller, dependency = edge
        return self.up[dependency] == caller or self.down[caller] == dependency


def source_lines(folder, n):
    path = folder / "source-spans.bin.gz"
    if not path.exists():
        return None
    spans = typed(read_gz(path), "int32")
    if len(spans) != 4 * n:
        raise LabelError(f"{path} does not have the expected size")
    return spans[0::4]


class IndexEdges:
    """Incoming references from a structure index (users-off.npy, users-dst.npy)."""

    def __init__(self, index, view, names):
        import numpy as np

        meta = json.loads((index / "meta.json").read_text(encoding="utf-8"))
        if meta["n"] != view.n or meta["root"] != view.manifest["root"]:
            raise LabelError("The structure index and the site packs describe different graphs")
        if meta["revision"] != view.manifest["revision"]:
            raise LabelError("The structure index and the site packs use different revisions")
        self.offsets = np.load(index / "users-off.npy", mmap_mode="r")
        self.callers = np.load(index / "users-dst.npy", mmap_mode="r")

    def __contains__(self, edge):
        caller, target = edge
        users = self.callers[self.offsets[target] : self.offsets[target + 1]]
        return bool((users == caller).any())


def resolve(glossary, rh, names, modnames, witnesses, lines, up=None):
    """Return {RH node id: packed entry} in glossary order."""
    if glossary.get("revision") != rh.manifest["revision"]:
        raise LabelError(
            f"labels revision {glossary.get('revision')} differs from the site revision "
            f"{rh.manifest['revision']}"
        )
    module_ids = {m: i for i, m in enumerate(modnames)}
    node_module = rh.arrays["module"]
    wanted = set()
    for record in glossary["entries"]:
        wanted.add(record["name"])
        if "caller" in record:
            wanted.add(record["caller"])
    found = {}
    for i, name in enumerate(names):
        if name in wanted:
            found.setdefault((name, node_module[i]), []).append(i)

    def lookup(name, module, context):
        if module not in module_ids:
            raise LabelError(f"{context}: unknown module {module}")
        ids = found.get((name, module_ids[module]), [])
        if len(ids) != 1:
            raise LabelError(f"{context}: expected one declaration {name} in {module}, found {len(ids)}")
        return ids[0]

    errors = []
    entries = {}
    for k, record in enumerate(glossary["entries"]):
        context = f"entry {k} ({record.get('name', '?')})"
        missing = [f for f in REQUIRED if f not in record]
        unknown = [f for f in record if f not in REQUIRED + OPTIONAL]
        if missing or unknown:
            errors.append(f"{context}: missing fields {missing}, unknown fields {unknown}")
            continue
        if ("caller" in record) != ("callerModule" in record):
            errors.append(f"{context}: caller and callerModule must be given together")
            continue
        if not all(isinstance(record[f], str) and record[f].strip() for f in REQUIRED if f != "line"):
            errors.append(f"{context}: text fields must be non-empty strings")
            continue
        if type(record["line"]) is not int or record["line"] < 1:
            errors.append(f"{context}: line must be a positive integer")
            continue
        try:
            entry = record.copy()
            i = lookup(entry["name"], entry["module"], context)
            if i in entries:
                raise LabelError(f"{context}: duplicate label for node {i}")
            if lines is not None and lines[i] and abs(lines[i]) != entry["line"]:
                raise LabelError(
                    f"{context}: line {entry['line']} differs from the compiled source line {abs(lines[i])}"
                )
            if "caller" in entry:
                caller = lookup(entry.pop("caller"), entry.pop("callerModule"), context + " caller")
                if (caller, i) not in witnesses:
                    hint = ""
                    if up is not None and up[i] >= 0:
                        hint = (f" A verified caller is {names[up[i]]} in "
                                f"{modnames[node_module[up[i]]]}.")
                    raise LabelError(
                        f"{context}: cannot confirm the compiled reference {names[caller]} → {names[i]}. "
                        f"Cite a verified caller or rerun with --index from the full pipeline.{hint}"
                    )
                entry["caller"] = caller
            entries[i] = entry
        except LabelError as e:
            errors.append(str(e))
    exclusive = rh.arrays["totals"]
    uncovered = [names[i] for i in range(rh.n) if exclusive[i] - 1 >= BOTTLENECK and i not in entries]
    if uncovered:
        errors.append(f"{len(uncovered)} bottlenecks have no label: {', '.join(uncovered[:20])}")
    if errors:
        raise LabelError("\n".join(errors))
    return entries


def check_guide(site, names):
    """The hand-written site/reading-guide.json may title only declarations in either view."""
    path = site / "reading-guide.json"
    if not path.exists():
        return
    guide = json.loads(path.read_text(encoding="utf-8"))
    titles = guide.get("titles", {})
    if not titles:
        return
    known = set(names).union(load_names(site / "grh" / "names.txt.gz", View(site / "grh", []).n))
    missing = sorted(set(titles).difference(known))
    if missing:
        raise LabelError(f"{path} titles unknown declarations: {', '.join(missing)}")


class Witnesses:
    def __init__(self, *sources):
        self.sources = sources

    def __contains__(self, edge):
        return any(edge in s for s in self.sources)


def packed_callers(path):
    if not path.exists():
        return set()
    packed = json.loads(path.read_text(encoding="utf-8"))
    return {(e["caller"], int(i)) for i, e in packed["entries"].items() if "caller" in e}


def render(site, labels, index=None):
    """Return the RH and GRH annotation files as strings."""
    glossary = json.loads(labels.read_text(encoding="utf-8"))
    rh = View(site, ["module", "totals"])
    grh = View(site / "grh", ["rhId"])
    names = load_names(site / "names.txt.gz", rh.n)
    modnames = read_gz(site / "modules.txt.gz").decode("utf-8").split("\n")
    routes = RouteEdges(site, rh.n) if (site / "routes.bin.gz").exists() else None
    if index is not None:
        witnesses = IndexEdges(index, rh, names)
    else:
        witnesses = Witnesses(packed_callers(site / "annotations.json"), *([routes] if routes else []))
    up = routes.up if routes else None
    entries = resolve(glossary, rh, names, modnames, witnesses, source_lines(site, rh.n), up)
    check_guide(site, names)
    revision = rh.manifest["revision"]
    rh_text = json.dumps(
        {"revision": revision, "entries": entries}, ensure_ascii=False, separators=(",", ":")
    )

    to_grh = [-1] * rh.n
    for j, i in enumerate(grh.arrays["rhId"]):
        if i >= 0:
            to_grh[i] = j
    mapped = {}
    for i, entry in entries.items():
        j = to_grh[i]
        if j < 0:
            continue
        entry = entry.copy()
        if "caller" in entry:
            c = to_grh[entry["caller"]]
            if c >= 0:
                entry["caller"] = c
            else:
                del entry["caller"]
        mapped[j] = entry
    grh_text = json.dumps({"revision": revision, "entries": mapped}, ensure_ascii=False)
    return rh_text, grh_text, len(entries), len(mapped)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("site", type=Path, help="site directory with the published packs (usually site/)")
    p.add_argument("--labels", type=Path, default=DEFAULT_LABELS, help="glossary (default: labels/annotations.json)")
    p.add_argument("--out", type=Path, help="write the two files under this directory instead of SITE")
    p.add_argument("--index", type=Path, help="structure index for full caller-edge verification")
    p.add_argument("--check", action="store_true", help="only verify that SITE already holds the packed labels")
    a = p.parse_args()
    try:
        rh_text, grh_text, n_rh, n_grh = render(a.site, a.labels, a.index)
    except (LabelError, OSError, KeyError, json.JSONDecodeError) as e:
        sys.exit(f"labels: {e}")
    targets = [("annotations.json", rh_text), ("grh/annotations.json", grh_text)]
    if a.check:
        stale = [name for name, text in targets
                 if not (a.site / name).exists() or (a.site / name).read_text(encoding="utf-8") != text]
        if stale:
            sys.exit(f"labels: {', '.join(stale)} out of date. Run python scripts/labels.py {a.site}")
        print(f"labels: {n_rh} RH and {n_grh} GRH annotations are up to date")
        return
    out = a.out or a.site
    for name, text in targets:
        write(out / name, text)
    print(f"labels: wrote {n_rh} RH and {n_grh} GRH annotations to {out}")


if __name__ == "__main__":
    main()
