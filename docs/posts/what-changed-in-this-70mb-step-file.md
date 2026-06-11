# What changed in this 70 MB STEP file? Now you can actually know.

*Every number below is real tool output; reproduction commands at the end.*

In October 2021, the [Jubilee toolchanger](https://github.com/machineagency/jubilee)
project — one of the best-run open-source hardware projects there is — updated
the STEP export of its Orbiter extruder tool. The commit message says,
in full:

> updating STEP Files to be in sync with Solidworks files

That's not a criticism of the maintainers. It's the state of the art. A STEP
file is a 70 MB wall of `CARTESIAN_POINT` lines; `git diff` shows you tens of
thousands of changed lines that mean nothing. There is no `git diff` for
geometry — so even careful maintainers can only tell you *that* the file
changed, not *what* changed. Reviewers open both files side by side and
squint, or trust the exporter.

We're building argus-diff (this repo) to fix this. Here's what it
says about that exact commit (`9c8f1d4`, files at `9c8f1d4^` vs `9c8f1d4`):

```
$ argus diff orbiter_old.step orbiter_new.step --no-interference

  before: orbiter_old.step  (65 bodies)
  after:  orbiter_new.step  (67 bodies)

  + 2 added   - 0 removed   ~ 7 modified   = 58 unchanged

  volume: 93527.5 -> 92404.1 mm^3 (-1.20%)
    ~ body_17..body_20: vol ±0.00%, com shift 0.385 mm
    ~ body_56 -> body_64: vol +0.00%, com shift 23.692 mm
    ~ body_55 -> body_63: vol +0.00%, com shift 32.680 mm
    ~ body_54 -> body_62: vol -61.09%, com shift 34.442 mm
    + body_65: 83.2 mm^3
    + body_66: 83.2 mm^3
```

So "in sync with Solidworks" actually meant:

- **58 of 65 bodies: untouched.** Byte noise in the export, zero geometric change.
- **Four fasteners moved exactly 0.385 mm** — a mounting interface shifted.
- **Two parts were repositioned wholesale** (23.7 mm and 32.7 mm) with
  identical geometry — relocated, not redesigned.
- **One part lost 61% of its volume and moved 34 mm** — an actual redesign.
- **Two small identical parts (83.2 mm³ each) appeared** — new hardware, by
  the size of it.

One terminal command, 3 minutes 18 seconds on a laptop-class machine for
two 70 MB assemblies, and a change that was "trust me" is now a reviewable
list. That's the whole product idea: when a mechanical PR changes geometry,
the PR should *show* the geometry change — rendered, quantified, and gated
(mass budget, envelope, interference) like any other CI check.

`argus-diff` is MIT-licensed, built on the open OCCT kernel
(cadquery/OCP) — STEP in, structured JSON + render out, with a GitHub Action
that comments diffs on your PRs. Alpha; body-level today, face-level
localization next.

## Reproduce every number

```bash
pip install "argus-diff[render]"
git clone --filter=blob:none --no-checkout https://github.com/machineagency/jubilee.git
cd jubilee
P='tools/jubilee_tools/tools/extruders/baby_bullet_extruder/cads/Step/orbiter_tool.STEP'
git show "9c8f1d4^:$P" > /tmp/orbiter_old.step
git show "9c8f1d4:$P"  > /tmp/orbiter_new.step
argus diff /tmp/orbiter_old.step /tmp/orbiter_new.step --no-interference
```

*Jubilee is open-source hardware by Machine Agency (University of
Washington); we picked it because its history is public and exemplary —
the gap shown here is the ecosystem's, not theirs.*
