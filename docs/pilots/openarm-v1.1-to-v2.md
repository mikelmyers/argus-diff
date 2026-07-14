# OpenArm v1.1 leader to v2.0: Argus pilot report

**Status:** pilot observation, not a ground-truth accuracy benchmark

**Run date:** 2026-07-14

**Tool:** argus-diff 0.1.1 plus the pilot fixes described below

## Executive result

Argus loaded and compared both public OpenArm assemblies—527 bodies in v1.1
and 607 in v2.0—and produced a structured body-level diff. The output is
useful as a major-release migration audit: it surfaces new end-effector and
cable-management families, removed rail connectors, a relocated but
geometrically identical base plate, and widespread vendor-part
simplification.

It is not yet suitable as an unattended CI verdict for this particular pair.
The v2 assembly changes coordinate frame, naming, and representation at once.
Argus therefore reports all 513 matched bodies as modified, and repeated
standard hardware makes some individual pairings ambiguous. A narrower
same-component revision would be the right next CI pilot.

## Reproducible inputs

Both files are public releases from
[`enactic/openarm_hardware`](https://github.com/enactic/openarm_hardware).
The STEP files are referenced by the repository's versioned Google Drive
manifest; they are not copied into the Argus repository.

| Revision | Repository provenance | Public file | SHA-256 |
| --- | --- | --- | --- |
| v1.1 leader | tag `1.1.0`, commit [`a2f3bfe`](https://github.com/enactic/openarm_hardware/commit/a2f3bfe5a13bb4427f0187d514a20fb95a782108) | [`OpenArm_v1.1_leader.STEP`](https://drive.google.com/uc?export=download&id=1rf8L-TygYD0FyNEFpG5yzvrz0aRzQWa_) | `cf8e92a967a3bac78e1fe7d64a0460d0586a3bc134c3e2574df1ac80c8226951` |
| v2.0 | commit [`12c0751`](https://github.com/enactic/openarm_hardware/commit/12c07510c09b2c10b7dfe48010dae5c05cbe887f) | [`OpenArm_2.0.STEP`](https://drive.google.com/uc?export=download&id=1aU-V3lt_aPrZoRM8FFx6dMQu2f28Ws0I) | `0f97a5fb308d5b09353aa67bbd32d7c08e55dc5629bcbe20c12f71c82ef13c94` |

Command:

```powershell
argus diff OpenArm_v1.1_leader.STEP OpenArm_2.0.STEP `
  --no-interference --json openarm_v1.1_to_v2.json `
  --render openarm_v1.1_to_v2.png
```

Interference checking was deliberately skipped for this first system-scale
run. No claim about interference count is made.

## Top-level observations

| Measure | v1.1 leader | v2.0 | Delta |
| --- | ---: | ---: | ---: |
| Solid bodies | 527 | 607 | +80 net |
| Matched bodies |  |  | 513 |
| Unmatched additions |  |  | 94 |
| Unmatched removals |  |  | 14 |
| Material volume | 5,925,886.7 mm³ | 7,188,578.6 mm³ | +1,262,691.8 mm³ (+21.31%) |

“Unmatched” is intentional wording. Without a human label, an unmatched body
is an addition/removal candidate, not proven design intent. The mass values in
the raw JSON use the CLI's default uniform density of 1.0 g/cm³; because the
assembly contains multiple materials, this report makes no mass claim.

### Strong signals

- **Base plate preserved but relocated.** `base_plate_2.step` matches
  `base_plate.STEP` with identical volume, area, face count, edge count, and
  principal moments. Its center moves 132.503 mm because the assembly frame
  changed. This is a high-confidence same-part/repositioned result.
- **End-effector content expanded.** The unmatched v2 set includes paired
  finger bodies (~37,153 mm³ each), covers (~10,700–12,951 mm³), J7 joints
  (~7,421 mm³), shafts (~6,018 mm³), finger-mount adapters (~6,827 mm³),
  bearings, and camera mounts. The left/right duplication is consistent with
  the two-arm assembly structure.
- **Cable management appeared.** Two instances each of `cable_holder_J4_A`
  and `cable_holder_J4_B` are unmatched additions (~10,550 mm³ per body).
- **Leader rail connectors disappeared.** Two
  `rail-connector-leader_1.step` bodies are unmatched removals
  (112,867.8 mm³ each), along with twelve small standard-hardware bodies.
- **Standard parts were simplified or re-exported.** Repeated HNTP6-6 parts
  change by ~0.50% volume and repeated CBM6-12 parts by ~2.15%, while v2 names
  explicitly add `_simplified`. These are likely representation changes that
  deserve a lower review priority than bespoke-part changes.

### Confidence and review load

- 73 matched bodies have less than 0.01% volume change, but still moved or
  changed topology/representation.
- 16 matches have a shape-and-position score at or below 0.1; these are the
  strongest automatic correspondences in this run.
- 42 matches score above 1.0 (the current match cutoff is 1.5). They should be
  treated as candidates, not authoritative correspondence.
- 76 matched pairs change volume by at least 20%. Some are real redesigns;
  others are weak matches caused by the scale of the major-version migration.

The raw report is exhaustive but noisy. The customer-facing product should
group repeated hardware, expose match confidence, and distinguish
shape-change from rigid relocation before it attempts to gate a migration of
this size.

## Product defects found and fixed by this pilot

This run improved Argus itself:

1. Two valid inward-oriented STEP solids initially produced negative OCCT
   signed-volume integrals. Argus now normalizes BREP volume and principal
   inertia to physical magnitudes, with a reversed-solid regression test.
2. The original renderer linked all three cameras, clipping v2 after its
   coordinate-frame change. Before, after, and overlay panes now fit their
   contents independently; the overlay remains the shared-coordinate view.
3. `--no-interference` formerly printed a visually misleading count of zero.
   The CLI now reports `interferences (after): skipped`.

## Recommendation

The pilot demonstrates real value, but the most useful next step is not to
install a broad gate on the v1.1-to-v2.0 migration. Ask an OpenArm maintainer
to validate the strong signals above and nominate one narrower public
before/after component revision. Use that pair to:

1. record human-reviewed body correspondence as a public benchmark case;
2. add confidence tiers and repeated-part grouping to the PR summary; and
3. submit an optional CI example PR whose output is short enough to review.

That turns this first run from an attractive demo into evidence about accuracy
and a credible CI workflow.
