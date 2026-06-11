"""Face-level change localization for a matched (modified) body pair.

Body-level diff says *that* a part changed; this says *what* changed on it,
in reviewer language: "cylindrical face: radius 2.5 -> 3.0 mm", "planar face
moved 2 mm", "face added (cylinder r=4.0)".
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import cadquery as cq
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepGProp import BRepGProp
from OCP.GeomAbs import GeomAbs_SurfaceType
from OCP.GProp import GProp_GProps

_SURFACE_NAMES = {
    GeomAbs_SurfaceType.GeomAbs_Plane: "plane",
    GeomAbs_SurfaceType.GeomAbs_Cylinder: "cylinder",
    GeomAbs_SurfaceType.GeomAbs_Cone: "cone",
    GeomAbs_SurfaceType.GeomAbs_Sphere: "sphere",
    GeomAbs_SurfaceType.GeomAbs_Torus: "torus",
    GeomAbs_SurfaceType.GeomAbs_BezierSurface: "bezier",
    GeomAbs_SurfaceType.GeomAbs_BSplineSurface: "bspline",
}


@dataclass
class FaceInfo:
    kind: str
    area: float
    centroid: tuple[float, float, float]
    radius: float | None  # cylinders/spheres/cones (ref radius)

    def label(self) -> str:
        r = f" r={self.radius:.3f}" if self.radius is not None else ""
        return f"{self.kind}{r} area={self.area:.2f}"


@dataclass
class FaceChange:
    status: str  # "modified" | "added" | "removed"
    before: FaceInfo | None
    after: FaceInfo | None

    def describe(self) -> str:
        if self.status == "added":
            return f"face added: {self.after.label()}"
        if self.status == "removed":
            return f"face removed: {self.before.label()}"
        a, b = self.before, self.after
        parts = []
        if a.radius is not None and b.radius is not None and _rel(a.radius, b.radius) > 1e-6:
            parts.append(f"radius {a.radius:.3f} -> {b.radius:.3f} mm")
        if _rel(a.area, b.area) > 1e-6:
            parts.append(f"area {a.area:.2f} -> {b.area:.2f} mm^2")
        shift = _dist(a.centroid, b.centroid)
        if shift > 1e-4:
            parts.append(f"moved {shift:.3f} mm")
        detail = ", ".join(parts) if parts else "changed"
        return f"{a.kind} face: {detail}"


def _rel(a: float, b: float) -> float:
    return abs(a - b) / max(abs(a), abs(b), 1e-12)


def _dist(p, q) -> float:
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(p, q)))


def face_infos(solid: cq.Solid) -> list[FaceInfo]:
    out = []
    for f in solid.Faces():
        ad = BRepAdaptor_Surface(f.wrapped)
        kind = _SURFACE_NAMES.get(ad.GetType(), "freeform")
        radius = None
        if kind == "cylinder":
            radius = ad.Cylinder().Radius()
        elif kind == "sphere":
            radius = ad.Sphere().Radius()
        elif kind == "cone":
            radius = ad.Cone().RefRadius()
        props = GProp_GProps()
        BRepGProp.SurfaceProperties_s(f.wrapped, props)
        c = props.CentreOfMass()
        out.append(FaceInfo(kind=kind, area=props.Mass(),
                            centroid=(c.X(), c.Y(), c.Z()), radius=radius))
    return out


def _face_score(a: FaceInfo, b: FaceInfo, scale: float) -> float:
    if a.kind != b.kind:
        return math.inf
    s = _rel(a.area, b.area) + _dist(a.centroid, b.centroid) / max(scale, 1e-9)
    if a.radius is not None and b.radius is not None:
        s += _rel(a.radius, b.radius)
    return s


def diff_faces(solid_a: cq.Solid, solid_b: cq.Solid, scale: float = 100.0) -> list[FaceChange]:
    """Match faces between two versions of one body; report what changed.

    Greedy lowest-score matching, same approach as body matching. Identical
    faces (score ~0) are dropped from the report — only changes are returned.
    """
    faces_a, faces_b = face_infos(solid_a), face_infos(solid_b)
    candidates = sorted(
        ((s, i, j) for i, a in enumerate(faces_a) for j, b in enumerate(faces_b)
         if (s := _face_score(a, b, scale)) is not math.inf),
        key=lambda t: t[0],
    )
    used_a, used_b = set(), set()
    changes: list[FaceChange] = []
    for score, i, j in candidates:
        if i in used_a or j in used_b or score > 1.0:
            continue
        used_a.add(i)
        used_b.add(j)
        if score > 1e-9:  # identical faces are not changes
            changes.append(FaceChange("modified", faces_a[i], faces_b[j]))
    changes.extend(FaceChange("removed", a, None)
                   for i, a in enumerate(faces_a) if i not in used_a)
    changes.extend(FaceChange("added", None, b)
                   for j, b in enumerate(faces_b) if j not in used_b)
    return changes


def mesh_change_regions(
    mesh_a, mesh_b, tol: float = 0.05, max_vertices: int = 20000, max_regions: int = 5
) -> list[str]:
    """Where did mesh B's surface deviate from mesh A's, in reviewer language.

    Measures every B vertex against A's surface, clusters deviated vertices
    into connected regions, and reports each region's location and maximum
    deviation. Large meshes are subsampled (aggregate report only, says so).
    """
    import numpy as np
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    from trimesh.proximity import ProximityQuery

    lines: list[str] = []
    # Exports routinely re-origin whole parts; deviation is only meaningful
    # after removing that rigid translation (it's already reported as the
    # body-level com shift). Rotation alignment (ICP) is future work.
    shift = np.asarray(mesh_a.centroid) - np.asarray(mesh_b.centroid)
    shift_mag = float(np.linalg.norm(shift))
    if shift_mag > tol:
        mesh_b = mesh_b.copy()
        mesh_b.apply_translation(shift)
        lines.append(f"(deviations measured after removing a {shift_mag:.1f} mm translation)")

    vb = np.asarray(mesh_b.vertices)
    subsampled = len(vb) > max_vertices
    if subsampled:
        rng = np.random.default_rng(0)
        sample_idx = rng.choice(len(vb), max_vertices, replace=False)
        points = vb[sample_idx]
    else:
        points = vb
    _, distance, _ = ProximityQuery(mesh_a).on_surface(points)

    moved = distance > tol
    frac_same = 1.0 - moved.sum() / len(distance)
    lines.append(f"{frac_same:.0%} of surface coincides within {tol} mm")
    if not moved.any():
        return lines
    if subsampled:
        lines.append(
            f"max deviation {distance.max():.2f} mm "
            f"(mesh subsampled at {max_vertices} vertices; regions not localized)"
        )
        return lines

    # cluster moved vertices into connected regions over B's edge graph
    edges = mesh_b.edges_unique
    keep = moved[edges[:, 0]] & moved[edges[:, 1]]
    e = edges[keep]
    n = len(vb)
    graph = coo_matrix((np.ones(len(e)), (e[:, 0], e[:, 1])), shape=(n, n))
    _, labels = connected_components(graph, directed=False)
    regions: dict[int, np.ndarray] = {}
    moved_idx = np.flatnonzero(moved)
    for label in np.unique(labels[moved_idx]):
        members = moved_idx[labels[moved_idx] == label]
        regions[label] = members
    ranked = sorted(regions.values(), key=lambda m: distance[m].max(), reverse=True)
    for members in ranked[:max_regions]:
        c = vb[members].mean(axis=0)
        lines.append(
            f"changed region near ({c[0]:.0f}, {c[1]:.0f}, {c[2]:.0f}) mm: "
            f"max deviation {distance[members].max():.2f} mm, {len(members)} vertices"
        )
    if len(ranked) > max_regions:
        lines.append(f"... and {len(ranked) - max_regions} more regions")
    return lines


def summarize_face_changes(changes: list[FaceChange], limit: int = 8) -> list[str]:
    """Human-readable change lines, most significant first, deduplicated.

    Identical descriptions are collapsed with a multiplier — four corner
    holes opened together read as one line: '4x cylinder face: radius ...'.
    """
    counts: dict[str, int] = {}
    for ch in changes:
        d = ch.describe()
        counts[d] = counts.get(d, 0) + 1
    lines = [f"{n}x {d}" if n > 1 else d for d, n in counts.items()]
    lines.sort(key=len)
    extra = len(lines) - limit
    return lines[:limit] + ([f"... and {extra} more face changes"] if extra > 0 else [])
