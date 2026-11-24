# shellcheck shell=bash disable=SC2034
# Pinned inputs for the map. Source this file from bash.

# Lean formalization released by Levent Alpöge (no license file at this revision).
LEAN_REPO=https://github.com/leanprover-community/riemann-hypothesis
LEAN_REV=40e56bab026552e089d7afcfeff08d2defb9c005
LEAN_TREE=e517b335d21898fd2506ad538a1e1775c0aaa4e4    # git tree of LEAN_REV
LEAN_TOOLCHAIN=leanprover/lean4:v4.33.1
MATHLIB_REV=0df444a360eaa60ab8c11dca51a86af692955474

# Mirror whose extracted/lean tree equals LEAN_TREE. The viewer fetches Lean text from it.
MIRROR_REPO=https://github.com/1337isnot1337/riemann-hypothesis-solved
MIRROR_REV=6193bb5ef61846c045c70c51ee05824f910d50cc

# Compiled .olean/.ilean files of LEAN_REV (Jack McCarthy's build, 175,187 module pairs).
COMPILED_URL=https://huggingface.co/datasets/JackMcCarthy/riemann-hypothesis-build/resolve/9036e64326acf4acfae159b96664e9708445c1d1/oleans.tar.zst
COMPILED_SHA256=953bab5386a7849527a11960f80a2fab427c49c637d6e94cc75788dd8f40196b

# GRH simplification drive (Apache-2.0): moddump reader and graph loader (tools/cone.py).
DRIVE_REPO=https://github.com/ShivMunagala/grh-simplification-drive
DRIVE_REV=63d94cb46d52ec099d9111d55b65279c882cfecd

# Bartosz Naskręcki's illustrated blueprint (0BSD), source of the blueprint labels.
BLUEPRINT_REPO=https://github.com/nasqret/riemann-rev
BLUEPRINT_REV=ae05a37f374c31eae7e57e16722f5d7689f3e138
