#!/usr/bin/env bash
# Rebuild every static data file of the map from the pinned inputs.
#
#   scripts/build_site.sh WORK OUT
#
# WORK holds the inputs and intermediates (about 130 GB). OUT receives a standalone site.
# Pass a new directory as OUT and copy the result into site/ after review.
# PYTHON must have requirements.txt installed. TMAP_PYTHON is the python of the
# env/tmap.yml environment. Completed expensive steps are skipped on a rerun.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
WORK="$(realpath -m "${1:?usage: build_site.sh WORK OUT}")"
OUT="$(realpath -m "${2:?usage: build_site.sh WORK OUT}")"
PYTHON="${PYTHON:-python3}"
TMAP_PYTHON="${TMAP_PYTHON:?set TMAP_PYTHON to the python of the env/tmap.yml environment}"

PYTHON="$PYTHON" "$here/fetch_inputs.sh" "$WORK"
PROOF="$WORK/proof" DRIVE="$WORK/drive" GRAPH="$WORK/graph" INDEX="$WORK/index" LAYOUT="$WORK/layout"
MODDUMP="$DRIVE/tools/moddump/.lake/build/bin/moddump"

step() { echo "== $*" >&2; }
[ -f "$GRAPH/consts.tsv.zst" ] || { step graph dump; "$PYTHON" "$here/graph_dump.py" "$PROOF" "$MODDUMP" "$GRAPH"; }
[ -f "$GRAPH/baseline.pkl" ] || { step baseline; "$PYTHON" "$here/baseline.py" "$GRAPH" "$DRIVE"; }
[ -f "$INDEX/meta.json" ] || { step structure index; "$PYTHON" "$here/structure_index.py" "$GRAPH/baseline.pkl" "$DRIVE" "$INDEX"; }
[ -f "$LAYOUT/layout.npz" ] || { step TMAP layout; "$TMAP_PYTHON" "$here/tmap_layout.py" "$INDEX" "$LAYOUT"; }
step classical RH packs; "$PYTHON" "$here/pack.py" "$INDEX" "$LAYOUT" "$OUT"
step Dirichlet GRH view; "$PYTHON" "$here/endpoints.py" "$GRAPH/baseline.pkl" "$DRIVE" "$OUT"
step routes; "$PYTHON" "$here/routes.py" "$GRAPH/baseline.pkl" "$DRIVE" "$OUT"
step source spans; "$PYTHON" "$here/source_spans.py" "$OUT" "$PROOF/.lake/build/lib/lean"
step labels; "$PYTHON" "$here/labels.py" "$OUT" --index "$INDEX"
step viewer
viewer="$(realpath "$here/../site")"
if [ "$OUT" != "$viewer" ]; then
  cp "$viewer/index.html" "$viewer/reading-guide.json" "$viewer/.nojekyll" "$OUT/"
fi
"$PYTHON" "$here/labels.py" "$OUT" --check
