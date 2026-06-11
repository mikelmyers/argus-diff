"""Generate the example part pair used in tests, docs, and the demo render.

A sensor-mount bracket between two revisions — the kind of change a mechanical
PR actually contains:

rev A -> rev B:
  * plate thickened 6 -> 8 mm, corner holes opened 5 -> 6 mm   (modified)
  * boss grows 20 -> 24 mm OD and moves +6 mm in X             (modified)
  * gusset rib added under the boss                            (added)
  * locating pin deleted                                       (removed)
  * dowel unchanged                                            (unchanged)

Run:  python examples/make_examples.py [outdir]
"""

from __future__ import annotations

import sys
from pathlib import Path

import cadquery as cq


def plate(thickness: float, hole_d: float) -> cq.Workplane:
    return (
        cq.Workplane("XY")
        .box(90, 60, thickness, centered=(True, True, False))
        .faces(">Z")
        .workplane()
        .rect(74, 44, forConstruction=True)
        .vertices()
        .hole(hole_d)
        .edges("|Z")
        .fillet(6)
    )


def boss(od: float, x: float, base_z: float) -> cq.Workplane:
    return (
        cq.Workplane("XY", origin=(x, 0, base_z))
        .circle(od / 2)
        .extrude(14)
        .faces(">Z")
        .workplane()
        .hole(8)
    )


def gusset(x: float, base_z: float) -> cq.Workplane:
    pts = [(0, 0), (18, 0), (0, 12)]
    return (
        cq.Workplane("XZ", origin=(x + 10, 2.5, base_z))
        .polyline(pts)
        .close()
        .extrude(5)
    )


def pin(x: float, y: float) -> cq.Workplane:
    # Press-fit dowel protruding from the plate underside; absolute position,
    # unaffected by plate thickness, so it diffs as truly unchanged.
    return cq.Workplane("XY", origin=(x, y, 0)).circle(2).extrude(-8)


def rev_a() -> cq.Assembly:
    t = 6.0
    asm = cq.Assembly(name="bracket")
    asm.add(plate(t, 5.0), name="plate")
    asm.add(boss(20.0, 0.0, t), name="boss")
    asm.add(pin(-30.0, 15.0), name="locating_pin")
    asm.add(pin(30.0, -15.0), name="dowel")
    return asm


def rev_b() -> cq.Assembly:
    t = 8.0
    asm = cq.Assembly(name="bracket")
    asm.add(plate(t, 6.0), name="plate")
    asm.add(boss(24.0, 6.0, t), name="boss")
    # NB: the gusset is modeled overlapping the boss by ~109 mm^3 — left in
    # deliberately so the demo exercises the interference check.
    asm.add(gusset(6.0, t), name="gusset")
    asm.add(pin(30.0, -15.0), name="dowel")
    return asm


def main(outdir: str | Path = ".") -> tuple[Path, Path]:
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    a = outdir / "bracket_rev_a.step"
    b = outdir / "bracket_rev_b.step"
    rev_a().export(str(a))
    rev_b().export(str(b))
    print(f"wrote {a}\nwrote {b}")
    return a, b


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
