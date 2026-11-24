# Riemann Proof Map

[![Live map](https://img.shields.io/badge/live%20map-riemannmap.mireklzicar.com-2b6cb0)](https://riemannmap.mireklzicar.com/)
[![Label check](https://github.com/mireklzicar/riemann-proof-map/actions/workflows/labels.yml/badge.svg)](https://github.com/mireklzicar/riemann-proof-map/actions/workflows/labels.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Lean 4.33.1 at 40e56bab](https://img.shields.io/badge/Lean%204.33.1-40e56bab-5c4ee5)](https://github.com/leanprover-community/riemann-hypothesis/tree/40e56bab026552e089d7afcfeff08d2defb9c005)
[![Cite](https://img.shields.io/badge/cite-CITATION.cff-f39c12)](CITATION.cff)

**An interactive proof map by [Miroslav Lžičař](https://mireklzicar.com/).** Explore the Lean formalization of classical RH and Dirichlet GRH released by Levent Alpöge. [Open the map](https://riemannmap.mireklzicar.com/) or [walk the four declarations in the final RH deduction](https://riemannmap.mireklzicar.com/?goal=rh#via=1213476&walk=final&step=0).

The map has two views. Classical RH starts at `riemannHypothesis` and Dirichlet GRH for all characters starts at `LFunction_eq_zero_re`. Each view contains the declarations its endpoint reaches through compiled type and proof-body references, together with the immediate-dominator tree of that graph. A declaration dominates another when every reference path from the endpoint to the second passes through the first.

| | Classical RH | Dirichlet GRH |
| --- | ---: | ---: |
| Reachable declarations | 1,265,231 | 1,265,239 |
| Declarations only in this view | 6 | 14 |
| Labelled declarations | 151 | 147 |

The two views share 1,265,225 declarations and their coordinates. TMAP lays out the classical RH dominator tree. At the 11,628 dominators with more than 12 children, a degree-limited Kruskal pass connects siblings using MinHash similarity of their name tokens and module paths. Selecting a node highlights its true dominator chain and dominated subtree. The viewer also steps along actual reference paths and shows structural progress: groups of mutually referring declarations form one stage, and each stage lies one above its deepest prerequisite. The Lean text of a selected declaration is fetched on demand from a pinned source mirror.

## Run the published map locally

```bash
git clone https://github.com/mireklzicar/riemann-proof-map.git
cd riemann-proof-map
python3 -m http.server 8000 --directory site
```

Open [localhost:8000](http://localhost:8000/). The map data ship with the checkout. Opening a Lean declaration fetches its text from the pinned source online.

## Repository layout

| Path | Contents |
| --- | --- |
| [`labels/annotations.json`](labels/annotations.json) | Canonical, editable label data |
| [`site/`](site/) | The static site. `index.html` is the viewer. The viewer uses `lookups.js` and the editable [`reading-guide.json`](site/reading-guide.json). The graph and text packs are generated |
| [`scripts/`](scripts/) | Label packer and the full data pipeline |
| [`env/`](env/), [`requirements.txt`](requirements.txt) | Pinned environments |
| [`tests/`](tests/) | Label packer checks against the published data |

## Editing labels

Each label describes one declaration. Edit [`labels/annotations.json`](labels/annotations.json), then regenerate both packed label files from the published data. The packer needs only Python 3.9 or newer.

```bash
python scripts/labels.py site            # writes site/annotations.json and site/grh/annotations.json
python scripts/labels.py site --check    # fails if either file is out of date
python -m unittest discover -s tests
```

No graph rebuild is needed. The packer resolves names in `site/names.txt.gz` and `site/modules.txt.gz`, then writes the RH file keyed by RH node and the GRH file keyed by GRH node. A label on a declaration outside the GRH view appears only in the RH view. A cited caller outside the GRH view is omitted there.

| Field | Required | Meaning |
| --- | --- | --- |
| `name` | yes | Fully qualified Lean name, as shown in the map's inspector |
| `module` | yes | Module that defines the declaration |
| `title` | yes | Short name for map labels, legends, search and chains |
| `statement` | yes | What the declaration states, in plain language |
| `role` | yes | What it contributes to the proof |
| `line` | yes | First source line of the declaration in its module |
| `caption` | no | Shorter map caption. The original title remains searchable |
| `blueprint` | no | Card id in the [illustrated blueprint](https://nasqret.github.io/riemann-rev/atlas/). The viewer links to the card and marks the label as a blueprint annotation |
| `caller`, `callerModule` | no | A direct compiled caller cited by the label, with its module. Give both or neither |

Labels without `blueprint` are shown as draft annotations. The packer rejects a label when

- the revision differs from the site data, or a field is missing, empty or unknown,
- `module` and `name` do not identify exactly one declaration, or two labels name the same one,
- `line` differs from the compiled source range in `site/source-spans.bin.gz`,
- a declaration with at least 10,000 declarations strictly below it in the classical RH dominator tree has no label,
- a cited caller cannot be confirmed as a compiled reference, or
- `site/reading-guide.json` titles a declaration that is in neither view.

Without the full graph, a caller is confirmed when the published data already record the reference: as the verified caller of the current packed label, or as a step in `routes.bin.gz`. The error message names a confirmed caller when one is available. To cite any other caller, run the packer with `--index` on a structure index built by the pipeline below.

[`site/reading-guide.json`](site/reading-guide.json) holds the statements and roles of the two endpoints and titles for the final deductions. It is edited by hand and needs no regeneration.

## Rebuilding the data

The pipeline rebuilds every generated file in `site/` from pinned public inputs. It needs Linux, git, curl, zstd, [elan](https://github.com/leanprover/elan), conda and about 130 GB of free disk: 28.6 GB for the compiled archive and 99 GB once unpacked.

```bash
python3.11 -m venv .venv && .venv/bin/pip install -r requirements.txt
conda create -p .tmap-env --file env/tmap-linux-64.lock   # or: conda env create -f env/tmap.yml
PYTHON=.venv/bin/python TMAP_PYTHON=.tmap-env/bin/python scripts/build_site.sh work work/site
```

`work/` holds the inputs and intermediates. `work/site` receives the data files. Review it, then copy the files into `site/`. Completed expensive steps are skipped when the command is rerun. The steps are:

| Step | Script | Output |
| --- | --- | --- |
| Check out the Lean source and the drive, verify the Git tree, download and verify the compiled archive, unpack `.olean`/`.ilean` files, build `moddump` | [`fetch_inputs.sh`](scripts/fetch_inputs.sh), [`extract_compiled.py`](scripts/extract_compiled.py) | `work/proof`, `work/drive` |
| Read every compiled module in `git ls-files` order | [`graph_dump.py`](scripts/graph_dump.py) | `work/graph/consts.tsv.zst` |
| Load the declaration graph with the drive's loader | [`baseline.py`](scripts/baseline.py) | `work/graph/baseline.pkl` |
| RH reference graph, dominator tree, SQLite node table | [`structure_index.py`](scripts/structure_index.py) | `work/index/` |
| TMAP layout of the dominator tree | [`tmap_layout.py`](scripts/tmap_layout.py) | `work/layout/` |
| Classical RH packs | [`pack.py`](scripts/pack.py) | `manifest.json`, `graph.bin.gz`, `names.txt.gz`, `modules.txt.gz` |
| Dirichlet GRH view and endpoint comparison | [`endpoints.py`](scripts/endpoints.py) | `grh/manifest.json`, `grh/graph.bin.gz`, `grh/names.txt.gz`, `endpoints.json` |
| On-demand names, modules and initial landmark identifiers | [`text_blocks.py`](scripts/text_blocks.py) | `text/index.json`, `text/*.gz` |
| Reference paths and structural stages | [`routes.py`](scripts/routes.py) | `routes.bin.gz`, `grh/routes.bin.gz` |
| Source ranges for the Lean reader | [`source_spans.py`](scripts/source_spans.py) | `source-spans.bin.gz`, `grh/source-spans.bin.gz` |
| Labels, with every cited caller checked in the full graph | [`labels.py`](scripts/labels.py) `--index` | `annotations.json`, `grh/annotations.json` |

`build_site.sh` also copies `index.html`, `lookups.js`, `reading-guide.json` and `.nojekyll` from `site/` when the output is another directory, so the output can be served as it is. The numbering of declarations follows the module order of the graph dump. `baseline.pkl` stores objects defined by the drive's `tools/cone.py`. Only load a pickle you built yourself. The compiled archive comes from compiling third-party code. The pipeline reads it as data and never executes it.

### Verification

We re-extracted all 175,187 compiled modules and reproduced the reference graph, then rebuilt both dominator trees and the TMAP layout. All 14 original graph and annotation data files matched the published release after decompression, including coordinates, immediate dominators, reading paths, source ranges and packed annotations. The checked-in packs preserve these exact coordinates across machines.

### Pinned inputs

All pins are in [`scripts/pins.sh`](scripts/pins.sh).

| Input | Revision |
| --- | --- |
| [Lean formalization](https://github.com/leanprover-community/riemann-hypothesis/tree/40e56bab026552e089d7afcfeff08d2defb9c005) | `40e56bab026552e089d7afcfeff08d2defb9c005`, Git tree `e517b335`, Lean 4.33.1, Mathlib `0df444a3` |
| [Source mirror](https://github.com/1337isnot1337/riemann-hypothesis-solved/tree/6193bb5ef61846c045c70c51ee05824f910d50cc) used by the Lean reader | `6193bb5ef61846c045c70c51ee05824f910d50cc`. Its `extracted/lean` tree is `e517b335` |
| [Compiled build](https://huggingface.co/datasets/JackMcCarthy/riemann-hypothesis-build/tree/9036e64326acf4acfae159b96664e9708445c1d1) | `oleans.tar.zst`, SHA-256 `953bab53…40196b` |
| [GRH simplification drive](https://github.com/ShivMunagala/grh-simplification-drive/tree/63d94cb46d52ec099d9111d55b65279c882cfecd) | `63d94cb46d52ec099d9111d55b65279c882cfecd` |
| [Illustrated blueprint](https://github.com/nasqret/riemann-rev/tree/ae05a37f374c31eae7e57e16722f5d7689f3e138) | `ae05a37f374c31eae7e57e16722f5d7689f3e138` |
| Python | [`requirements.txt`](requirements.txt) for Python 3.11; [`env/tmap-linux-64.lock`](env/tmap-linux-64.lock) for the TMAP layout (Python 3.9, TMAP 1.0.6) |

## Rendering and startup

The map uses WebGL 2 for points and edges and a 2D canvas for labels. The opening view draws every declaration at its published coordinates. The first visit downloads approximately 14.5 MB for classical RH, including geometry, topology, landmark labels and navigation. Selecting an unlabelled declaration reads a small block of names. Full-name search and dependency walks fetch their respective indexes on first use. Both views reuse the same text blocks for shared declarations.

To measure a cold start on your own machine, install the optional Playwright package and its Chromium browser, then run `python scripts/benchmark_startup.py https://riemannmap.mireklzicar.com/`. Each sample uses a fresh browser context. The reported time ends when a full point draw has reached the next animation frame and the loading screen has disappeared. Use `--mbps 40` for a controlled network comparison.

## Data files

All arrays are little-endian. Node ids index `names.txt.gz` of the same view.

| File | Contents |
| --- | --- |
| `manifest.json` | Node count, root, revision, branch heads, directory and region labels, and the offset and type of every array in `graph.bin.gz` |
| `graph.bin.gz` | Coordinates, layout parent, immediate dominator, subtree size, module, depth, branch, directory and kind per node. The GRH view adds `rhId`, the RH node of each shared declaration or −1 |
| `names.txt.gz` | One fully qualified declaration name per line |
| `modules.txt.gz` | Module names, indexed by the `module` array |
| `text/` | Exact names and module paths in blocks of 8,192. GRH uses the RH node mapping plus its endpoint-specific names in `index.json` |
| `routes.bin.gz` | `int32` breadth-first caller from the endpoint, `int32` next dependency on a longest descending path, `uint16` structural stage |
| `source-spans.bin.gz` | `int32` start line, start column, end line, end column. A negative start line marks the enclosing source declaration of a generated one |
| `annotations.json` | Packed labels keyed by node id |
| `endpoints.json` | Final deduction chains of both endpoints and the declarations exclusive to each |

## Citation and credits

Miroslav Lžičař (2026). *Riemann Proof Map*, v0.2.0. [Versioned source](https://github.com/mireklzicar/riemann-proof-map/tree/v0.2.0).

Please cite the map with [`CITATION.cff`](CITATION.cff) and credit Levent Alpöge for the formalization ([announcement](https://alpo.ge/remark.pdf)). Bartosz Naskręcki's [illustrated blueprint](https://nasqret.github.io/riemann-rev/atlas/) supplies titles and explanations for the blueprint labels under the 0BSD license. The other labels are drafts. Pengowray's [proof treemap](https://pengowray.github.io/riemann-zeta-proof-visualizer/#sources) inspired the source reader. The layout uses [TMAP](https://tmap.gdb.tools/).

The code, documentation and labels written here are released under the [MIT License](LICENSE). Upstream licenses and attributions are listed in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). [Contributing](CONTRIBUTING.md)
