# Third-party notices

The code, documentation and labels written for this repository are under the [MIT License](LICENSE). This file lists the upstream work the map uses and how each is used. The repository contains no Lean source archive and no compiled Lean files.

## Lean formalization

- **Work:** Lean formalization of the Riemann Hypothesis and Dirichlet GRH released by Levent Alpöge, in collaboration with Claude. [Announcement (PDF)](https://alpo.ge/remark.pdf)
- **Pinned source:** [leanprover-community/riemann-hypothesis at `40e56bab026552e089d7afcfeff08d2defb9c005`](https://github.com/leanprover-community/riemann-hypothesis/tree/40e56bab026552e089d7afcfeff08d2defb9c005). The repository has no license file at this revision.
- **Use:** The site data hold facts extracted from the compiled build: declaration and module names, references between declarations, source line ranges and quantities computed from them. The viewer requests Lean text on demand from the mirror below and displays it in the reader's browser. The text is not stored in this repository.

## Source mirror

- **Work:** [1337isnot1337/riemann-hypothesis-solved at `6193bb5ef61846c045c70c51ee05824f910d50cc`](https://github.com/1337isnot1337/riemann-hypothesis-solved/tree/6193bb5ef61846c045c70c51ee05824f910d50cc), maintained by Cinna Davis. The Git tree of its `extracted/lean` directory is `e517b335d21898fd2506ad538a1e1775c0aaa4e4`, identical to the tree of the pinned upstream revision.
- **Use:** Linked from the viewer and fetched at run time from `raw.githubusercontent.com`. The mirror asks users to cite Alpöge's announcement and link the mirror with its revision.

## Compiled build

- **Work:** [Jack McCarthy's riemann-hypothesis build](https://huggingface.co/datasets/JackMcCarthy/riemann-hypothesis-build/tree/9036e64326acf4acfae159b96664e9708445c1d1), `oleans.tar.zst`, SHA-256 `953bab5386a7849527a11960f80a2fab427c49c637d6e94cc75788dd8f40196b`.
- **Use:** Downloaded by `scripts/fetch_inputs.sh` as pipeline input. Not redistributed. The dataset declares no license.

## GRH simplification drive

- **Work:** [ShivMunagala/grh-simplification-drive at `63d94cb46d52ec099d9111d55b65279c882cfecd`](https://github.com/ShivMunagala/grh-simplification-drive/tree/63d94cb46d52ec099d9111d55b65279c882cfecd), Apache License 2.0.
- **Use:** The pipeline checks it out and runs its `tools/moddump` reader and `tools/cone.py` graph loader. `baseline.pkl` stores objects defined in `cone.py`. No file from the drive is copied into this repository.

## Illustrated blueprint

- **Work:** Bartosz Naskręcki's [riemann-rev](https://github.com/nasqret/riemann-rev/tree/ae05a37f374c31eae7e57e16722f5d7689f3e138) illustrated blueprint at `ae05a37f374c31eae7e57e16722f5d7689f3e138`. [Published blueprint](https://nasqret.github.io/riemann-rev/atlas/)
- **Use:** Labels with a `blueprint` field in `labels/annotations.json` adapt titles and explanations from the blueprint card with that id. The viewer links each to its card.
- **License:** BSD Zero Clause License, reproduced from the pinned revision.

```text
BSD Zero Clause License

Copyright (c) 2026 Bartosz Naskręcki

Permission to use, copy, modify, and/or distribute this software for any
purpose with or without fee is hereby granted.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH
REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY
AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT,
INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM
LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR
OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE
USE OR OTHER DEALINGS IN THE SOFTWARE.
```

## Mathlib

- **Work:** [Mathlib at `0df444a360eaa60ab8c11dca51a86af692955474`](https://github.com/leanprover-community/mathlib4/tree/0df444a360eaa60ab8c11dca51a86af692955474), Apache License 2.0.
- **Use:** The viewer fetches the definition of `RiemannHypothesis` from this revision on demand.

## Build tools

These are installed from their package indexes and are not redistributed here.

| Package | Version | License | Used by |
| --- | --- | --- | --- |
| [TMAP](https://github.com/reymond-group/tmap) | 1.0.6 | MIT | `tmap_layout.py`. Probst and Reymond, [J. Cheminform. 12, 12 (2020)](https://doi.org/10.1186/s13321-020-0416-x) |
| [OGDF](https://github.com/ogdf/ogdf) | 1.2.0 (TMAP conda build) | GPL 2.0 or 3.0, with exceptions | FM³ layout inside TMAP |
| [NumPy](https://numpy.org/) | 1.26.4 | BSD 3-Clause | pipeline |
| [SciPy](https://scipy.org/) | 1.16.3 | BSD 3-Clause | pipeline |
| [Numba](https://numba.pydata.org/) | 0.62.1 | BSD 2-Clause | `structure_index.py`, `routes.py` |
| [python-igraph](https://python.igraph.org/) | 1.0.0 | GPL 2.0 or later | dominator trees |
| [Lean 4](https://github.com/leanprover/lean4) | 4.33.1 | Apache 2.0 | builds `moddump` |

## Acknowledgement

Pengowray's [proof treemap](https://pengowray.github.io/riemann-zeta-proof-visualizer/#sources) inspired the source reader. No code from it is included.
