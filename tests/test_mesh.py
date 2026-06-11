"""Mesh-format (STL) diff path: same engine, trimesh kernel."""

import numpy as np
import pytest
import trimesh

from argus_diff import diff_files
from argus_diff.loader import load_any


def _scene(meshes) -> trimesh.Trimesh:
    return trimesh.util.concatenate(meshes)


@pytest.fixture(scope="module")
def stl_pair(tmp_path_factory):
    d = tmp_path_factory.mktemp("stl")
    sphere = trimesh.creation.icosphere(radius=5.0)
    sphere.apply_translation([40, 0, 0])

    box_v1 = trimesh.creation.box(extents=[20, 20, 5])
    a = d / "part_a.stl"
    _scene([box_v1, sphere.copy()]).export(a)

    box_v2 = trimesh.creation.box(extents=[20, 20, 8])  # thickened
    cyl = trimesh.creation.cylinder(radius=3, height=10)  # new body
    cyl.apply_translation([-30, 0, 0])
    b = d / "part_b.stl"
    _scene([box_v2, sphere.copy(), cyl]).export(b)
    return a, b


def test_load_mesh_bodies(stl_pair):
    a, _ = stl_pair
    bodies = load_any(a)
    assert len(bodies) == 2  # box + sphere split as connected components
    assert all(b.kind == "mesh" and b.watertight for b in bodies)
    box = max(bodies, key=lambda b: b.volume)
    assert box.volume == pytest.approx(20 * 20 * 5, rel=1e-6)


def test_stl_diff_classification(stl_pair):
    a, b = stl_pair
    result = diff_files(a, b)
    assert len(result.modified) == 1  # the thickened box
    assert len(result.unchanged) == 1  # the sphere
    assert len(result.added) == 1  # the cylinder
    assert not result.removed
    assert result.interference_checked is False  # honest skip for meshes
    assert result.to_dict()["summary"]["interference_checked"] is False


def test_mesh_change_region_localization(tmp_path):
    # a small local bump near the +x pole; the diff must localize it there.
    # (kept local so the centroid barely moves: the rigid-translation
    # alignment must not smear the bump across the whole sphere)
    base = trimesh.creation.icosphere(subdivisions=3, radius=5.0)
    bumped = base.copy()
    v = bumped.vertices.copy()
    mask = v[:, 0] > 4.5  # ~a couple dozen vertices near the +x pole
    assert 5 < mask.sum() < 80
    v[mask] *= (5.0 + 1.0) / 5.0  # push them out radially by 1 mm
    bumped.vertices = v
    a, b = tmp_path / "a.stl", tmp_path / "b.stl"
    base.export(a)
    bumped.export(b)

    result = diff_files(a, b, check_interference=False)
    assert len(result.modified) == 1
    lines = result.modified[0].face_changes()
    assert any("coincides within" in line for line in lines)
    region_lines = [line for line in lines if "changed region near" in line]
    assert region_lines, lines
    # the dominant region must sit in +x (where the bump is) at ~1 mm
    x = float(region_lines[0].split("(")[1].split(",")[0])
    assert x > 2
    dev = float(region_lines[0].split("max deviation ")[1].split(" mm")[0])
    assert 0.7 < dev < 1.3


def test_degenerate_sliver_does_not_crash(tmp_path):
    # Real-world STLs contain 2-triangle zero-volume shells that trimesh
    # flags watertight but whose inertia is non-finite (seen live in
    # Voron-2 printhead STLs). They must fingerprint as not-a-solid.
    v = np.array([[0, 0, 0], [10, 0, 0], [0, 10, 0]], dtype=float)
    sliver = trimesh.Trimesh(vertices=v, faces=[[0, 1, 2], [2, 1, 0]])
    box = trimesh.creation.box(extents=[5, 5, 5])
    box.apply_translation([30, 0, 0])
    p = tmp_path / "sliver.stl"
    _scene([sliver, box]).export(p)
    bodies = load_any(p)
    sliver_body = min(bodies, key=lambda b: b.n_faces)
    assert sliver_body.watertight is False
    assert sliver_body.volume == 0.0


def test_open_mesh_does_not_lie_about_volume(tmp_path):
    # a single triangle is not a solid: volume must be 0 + flagged, not garbage
    tri = trimesh.Trimesh(vertices=np.eye(3) * 10, faces=[[0, 1, 2]])
    p = tmp_path / "open.stl"
    tri.export(p)
    bodies = load_any(p)
    assert bodies[0].watertight is False
    assert bodies[0].volume == 0.0
