# M336 Portable Checkpoints

Each checkpoint directory is an immutable continuation bundle produced by
`experiments/m336/scripts/exact_site_checkpoint.py`. Use `certificate.json` as
the source result; its `assignment_json` and `placement` paths are resolved
relative to that certificate. `certificate.original.json` preserves the exact
certification bytes cited by the issue ledger, while `manifest.json` records
SHA-256 hashes for every bundled dependency.

Example:

```bash
python experiments/m336/scripts/exact_site_checkpoint.py \
  --result /tmp/certified.json \
  --quality-guide /tmp/quality-guide.json \
  --output-dir experiments/m336/checkpoints/M336-NNN
```

Checkpoint directories must not be overwritten. Export a new issue-numbered
directory whenever the promoted incumbent changes.
