# Contributing

Corrections and new labels are welcome. Open an issue for a question about the map or a pull request for a change.

## Labels

1. Find the declaration in the [map](https://riemannmap.mireklzicar.com/). The inspector shows its full name and module, and its source link gives the line.
2. Add or edit its entry in [`labels/annotations.json`](labels/annotations.json). The fields are described in the [README](README.md#editing-labels).
3. Regenerate and check the packed files:

   ```bash
   python scripts/labels.py site
   python -m unittest discover -s tests
   ```

4. Commit `labels/annotations.json`, `site/annotations.json` and `site/grh/annotations.json` together.

Write statements in plain language and keep them faithful to the Lean statement. A `role` explains what the result contributes where it is used. When a label adapts a blueprint card, give its `blueprint` id. Otherwise the viewer shows the label as a draft. A cited `caller` must be a direct compiled caller. The packer confirms it from the published data or tells you which caller it can confirm.

Endpoint statements and the titles of the final deductions are in [`site/reading-guide.json`](site/reading-guide.json). Edit that file directly.

## Code and data

- Keep generated files in `site/` in sync with the scripts that write them. Run `scripts/build_site.sh` into a new directory and compare before replacing any published data file.
- Keep inputs pinned. A new upstream revision goes into [`scripts/pins.sh`](scripts/pins.sh), the README and `CITATION.cff` together.
- Do not add Lean source archives or compiled Lean files to the repository. The viewer fetches Lean text from the pinned mirror.
- Record new upstream material in [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) with its license.

Contributions are accepted under the [MIT License](LICENSE).
