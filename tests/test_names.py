"""STEP product names survive into BodyInfo; fallback and dedupe behave."""

import cadquery as cq

from argus_diff.loader import load_step


def test_step_part_names_preserved(tmp_path):
    asm = cq.Assembly()
    asm.add(cq.Workplane().box(10, 10, 2), name="plate")
    asm.add(cq.Workplane().cylinder(5, 3), name="pin", loc=cq.Location((20, 0, 0)))
    p = tmp_path / "asm.step"
    asm.save(str(p))
    bodies = load_step(p)
    assert sorted(b.name for b in bodies) == ["pin", "plate"]
    # locations must be applied: the pin is offset, not at origin
    pin = next(b for b in bodies if b.name == "pin")
    assert abs(pin.com[0] - 20.0) < 1e-6


def test_bare_export_falls_back_to_body_n(tmp_path):
    # plain exports carry only the kernel's placeholder product name;
    # that must not masquerade as a part name
    p = tmp_path / "bare.step"
    cq.exporters.export(cq.Workplane().box(5, 5, 5), str(p))
    assert [b.name for b in load_step(p)] == ["body_0"]
