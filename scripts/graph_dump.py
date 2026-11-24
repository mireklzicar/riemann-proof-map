"""Dump every compiled module's declarations and references with the drive's pinned moddump.

Modules are read in `git ls-files` order in chunks of 350, which fixes the declaration
numbering used by baseline.pkl and all packs. Finished chunks are kept, so an interrupted
run resumes. The result is GRAPH/consts.tsv.zst.
"""

import argparse
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

EXPECTED = 175_187
CHUNK = 350


def main(proof, moddump, out, jobs):
    out.mkdir(parents=True, exist_ok=True)
    files = subprocess.check_output(
        ["git", "-C", proof, "-c", "core.quotePath=false", "ls-files", "src/*.lean"], text=True
    ).splitlines()
    modules = [f.removeprefix("src/").removesuffix(".lean") for f in files]
    assert len(modules) == EXPECTED, len(modules)
    lib = proof / ".lake" / "build" / "lib" / "lean"

    def walk(chunk):
        i, ms = chunk
        dst = out / f"{i:04d}.zst"
        if dst.is_file():
            return
        data = "".join(f"{m.replace('/', '.')}\t{lib}/{m}.olean\n" for m in ms).encode()
        cp = subprocess.run([str(moddump), "--nosize"], input=data, stdout=subprocess.PIPE, check=True)
        lines = cp.stdout.splitlines()
        assert sum(line.startswith(b"E\t") for line in lines) == len(ms), (i, cp.stdout[-300:])
        assert b"\nX\t" not in cp.stdout, (i, cp.stdout[-300:])
        tmp = f"{dst}.tmp"
        subprocess.run(["zstd", "-q", "-3", "-f", "-o", tmp], input=cp.stdout, check=True)
        os.replace(tmp, dst)

    chunks = [(i // CHUNK, modules[i : i + CHUNK]) for i in range(0, len(modules), CHUNK)]
    with ThreadPoolExecutor(jobs) as pool:
        for k, _ in enumerate(pool.map(walk, chunks)):
            if k % 50 == 0:
                print(k, len(chunks), flush=True)
    tmp = out / "consts.tsv.zst.tmp"
    with tmp.open("wb") as w:
        for i, _ in chunks:
            w.write((out / f"{i:04d}.zst").read_bytes())
    tmp.replace(out / "consts.tsv.zst")
    print("complete", flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("proof", type=Path, help="Lean checkout with .lake/build/lib/lean")
    p.add_argument("moddump", type=Path, help="drive/tools/moddump/.lake/build/bin/moddump")
    p.add_argument("graph", type=Path, help="output directory")
    p.add_argument("-j", "--jobs", type=int, default=8)
    a = p.parse_args()
    main(a.proof.resolve(), a.moddump.resolve(), a.graph, a.jobs)
