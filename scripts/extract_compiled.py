"""Unpack only .olean and .ilean files from the compiled build into PROOF/.lake/build/lib/lean.

The archive was produced by compiling third-party code. It is treated as data: members
outside .lake/build/lib/lean, links, devices and unusual paths are skipped, and nothing
in it is executed.
"""

import argparse
import re
import shutil
import subprocess
import tarfile
from pathlib import Path

SAFE = re.compile(r"^(?:\./)?\.lake/build/lib/lean/((?:[^/\x00]+/)*[^/\x00]+\.(?:olean|ilean))$")
EXPECTED = 175_187


def main(archive, proof):
    lib = proof / ".lake" / "build" / "lib" / "lean"
    counts = {".olean": 0, ".ilean": 0}
    skipped = 0
    unzip = subprocess.Popen(["zstd", "-dc", "--long=31", str(archive)], stdout=subprocess.PIPE)
    with tarfile.open(fileobj=unzip.stdout, mode="r|") as tar:
        for member in tar:
            match = SAFE.match(member.name)
            if not member.isreg() or not match or ".." in match.group(1).split("/"):
                skipped += not member.isdir()
                continue
            target = lib / match.group(1)
            target.parent.mkdir(parents=True, exist_ok=True)
            with tar.extractfile(member) as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst, 1 << 20)
            counts[target.suffix] += 1
            if sum(counts.values()) % 20_000 == 0:
                print(counts, flush=True)
    if unzip.wait() != 0:
        raise SystemExit("zstd failed")
    print(counts, "skipped", skipped)
    assert counts == {".olean": EXPECTED, ".ilean": EXPECTED}, counts


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("archive", type=Path)
    p.add_argument("proof", type=Path)
    a = p.parse_args()
    main(a.archive, a.proof)
