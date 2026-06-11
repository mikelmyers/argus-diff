# Changelog

## 0.1.1 — 2026-06-11

First PyPI release (Trusted Publishing). Site live at argusdiff.com.
README links the site and the live demo PR; landing page reflects the
shipped GitHub Action. No engine changes.


## 0.1.0 — unreleased (publish = first public tag)

First release. Everything here is validated against real files from real
project histories (22/22 revision pairs across Jubilee, Voron-2, SO-ARM100;
evidence in `docs/corpus/`).

- `argus diff a b`: body-level geometric diff for STEP/STL/3MF/OBJ/PLY —
  added/removed/modified/unchanged via shape-anchored fingerprint matching
  (volume, surface area, principal moments; position as capped tiebreaker).
- Face-level change localization on B-rep: "4x cylinder face: radius
  2.500 -> 3.000 mm" instead of "body changed".
- Volume/mass/bbox deltas (`--density`), solid-solid interference check
  (B-rep; meshes report it skipped, never as zero), JSON output,
  before/after/overlay PNG renders (`--render`, headless-safe).
- CI gates with exit codes: `--fail-on-interference`,
  `--max-mass-delta-pct`.
- `argus ci`: diff every CAD file changed between two git refs; markdown
  report for PR comments; optional per-diff receipts
  (`--receipt-ledger`, via argus-receipts).
- `argus precommit` + `.pre-commit-hooks.yaml`.
- GitHub Action (`action.yml`): self-updating PR comment, render artifacts,
  gate enforcement.
- Mesh change-region localization: modified mesh bodies report *where*
  they deviate — rigid translation removed first (and stated), remaining
  deviations clustered into regions with location and magnitude.
- Content-hash fingerprint cache (`--cache`): measured 480x on a 2x70 MB
  STEP pair (196.6 s cold → 0.41 s hot, identical classification). Cache
  hits carry no geometry; anything needing geometry says so and loads
  fresh.
- Honesty guarantees: open meshes report volume as unavailable rather than
  a fabricated number; degenerate shells (zero-volume slivers) fingerprint
  as not-a-solid; skipped checks are reported as skipped.
