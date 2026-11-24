#!/usr/bin/env bash
# Fetch and verify the pinned inputs into WORK:
#   WORK/proof     Lean checkout at LEAN_REV, with the compiled build in .lake/build/lib/lean
#   WORK/drive     GRH simplification drive at DRIVE_REV, with moddump built
#   WORK/download  oleans.tar.zst (28.6 GB, checked by SHA-256)
# Needs git, curl, zstd, elan (for lake) and about 130 GB of free disk.
# Rerunning skips completed steps.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source-path=SCRIPTDIR source=pins.sh
source "$here/pins.sh"
WORK="$(realpath -m "${1:?usage: fetch_inputs.sh WORK}")"
PYTHON="${PYTHON:-python3}"
mkdir -p "$WORK/download"

checkout() {  # repo rev dir
  if [ ! -d "$3/.git" ]; then
    git init -q "$3"
    git -C "$3" remote add origin "$1"
  fi
  if [ "$(git -C "$3" rev-parse -q --verify HEAD || true)" != "$2" ]; then
    git -C "$3" fetch -q --depth 1 origin "$2"
    git -C "$3" -c advice.detachedHead=false checkout -q "$2"
  fi
}

checkout "$LEAN_REPO" "$LEAN_REV" "$WORK/proof"
test "$(git -C "$WORK/proof" rev-parse 'HEAD^{tree}')" = "$LEAN_TREE"
checkout "$DRIVE_REPO" "$DRIVE_REV" "$WORK/drive"
echo "sources at $LEAN_REV and $DRIVE_REV"

archive="$WORK/download/oleans.tar.zst"
if [ ! -f "$archive.verified" ]; then
  curl -fL --retry 5 -C - -o "$archive" "$COMPILED_URL"
  echo "$COMPILED_SHA256  $archive" | sha256sum -c -
  touch "$archive.verified"
fi

lib="$WORK/proof/.lake/build/lib/lean"
if [ ! -f "$lib/.complete" ]; then
  "$PYTHON" "$here/extract_compiled.py" "$archive" "$WORK/proof"
  touch "$lib/.complete"
fi

lake +"$LEAN_TOOLCHAIN" -d "$WORK/drive/tools/moddump" build moddump
echo "moddump: $WORK/drive/tools/moddump/.lake/build/bin/moddump"
