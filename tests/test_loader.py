"""Regression coverage for CAD-kernel property normalization."""

import cadquery as cq
import pytest

from argus_diff.loader import _props_of


def test_reversed_brep_orientation_has_physical_properties():
    """Inward shell orientation must not produce negative material values."""
    outward = cq.Solid.makeBox(10, 20, 30)
    inward = cq.Solid(outward.wrapped.Reversed())

    reference = _props_of(outward, 0, "outward")
    reversed_props = _props_of(inward, 1, "inward")

    assert reversed_props.volume == pytest.approx(6000.0)
    assert reversed_props.volume == pytest.approx(reference.volume)
    assert reversed_props.com == pytest.approx(reference.com)
    assert reversed_props.principal_moments == pytest.approx(reference.principal_moments)
    assert all(moment >= 0 for moment in reversed_props.principal_moments)
