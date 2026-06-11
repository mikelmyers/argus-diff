"""CAD loading and per-body geometric properties.

B-rep formats (STEP) load through OCCT via cadquery/OCP; mesh formats
(STL/3MF/OBJ/PLY) load through trimesh. Both produce the same BodyInfo
fingerprint so the diff engine doesn't care which world a body came from.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cadquery as cq
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps

BREP_SUFFIXES = {".step", ".stp"}
MESH_SUFFIXES = {".stl", ".3mf", ".obj", ".ply"}
CAD_SUFFIXES = BREP_SUFFIXES | MESH_SUFFIXES


@dataclass
class BodyInfo:
    """Geometric fingerprint of one solid body in a CAD file."""

    index: int
    name: str
    volume: float  # mm^3 (0.0 for open meshes — see `watertight`)
    area: float  # mm^2
    com: tuple[float, float, float]  # center of mass, mm
    bbox: tuple[tuple[float, float, float], tuple[float, float, float]]  # (min, max)
    principal_moments: tuple[float, float, float]  # sorted, volume-normalized
    n_faces: int
    n_edges: int
    solid: Any = field(repr=False, compare=False)  # cq.Solid | trimesh.Trimesh
    kind: str = "brep"  # "brep" | "mesh"
    watertight: bool = True

    @property
    def bbox_size(self) -> tuple[float, float, float]:
        lo, hi = self.bbox
        return (hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2])

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "name": self.name,
            "kind": self.kind,
            "watertight": self.watertight,
            "volume_mm3": round(self.volume, 6),
            "area_mm2": round(self.area, 6),
            "center_of_mass_mm": [round(c, 6) for c in self.com],
            "bbox_min_mm": [round(c, 6) for c in self.bbox[0]],
            "bbox_max_mm": [round(c, 6) for c in self.bbox[1]],
            "principal_moments_norm": [round(m, 9) for m in self.principal_moments],
            "n_faces": self.n_faces,
            "n_edges": self.n_edges,
        }

    def triangles(self, tol: float = 0.2):
        """(vertices Nx3, faces Mx3) for rendering, whatever the source kernel."""
        import numpy as np

        if self.kind == "mesh":
            return np.asarray(self.solid.vertices), np.asarray(self.solid.faces)
        verts, tris = self.solid.tessellate(tol)
        return np.array([(v.x, v.y, v.z) for v in verts]), np.array(tris)


def _props_of(solid: cq.Solid, index: int, name: str) -> BodyInfo:
    shape = solid.wrapped

    vp = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, vp)
    volume = vp.Mass()
    com = vp.CentreOfMass()

    sp = GProp_GProps()
    BRepGProp.SurfaceProperties_s(shape, sp)
    area = sp.Mass()

    box = Bnd_Box()
    BRepBndLib.Add_s(shape, box)
    xmin, ymin, zmin, xmax, ymax, zmax = box.Get()

    moments = vp.PrincipalProperties().Moments()
    # Normalize by volume so the fingerprint is scale-honest but unit-stable.
    norm = abs(volume) if abs(volume) > 1e-12 else 1.0
    pm = tuple(sorted(m / norm for m in moments))

    return BodyInfo(
        index=index,
        name=name,
        volume=volume,
        area=area,
        com=(com.X(), com.Y(), com.Z()),
        bbox=((xmin, ymin, zmin), (xmax, ymax, zmax)),
        principal_moments=pm,  # type: ignore[arg-type]
        n_faces=len(solid.Faces()),
        n_edges=len(solid.Edges()),
        solid=solid,
    )


def load_step(path: str | Path) -> list[BodyInfo]:
    """Load a STEP file and return per-solid geometric fingerprints.

    Assemblies and compounds are flattened to their constituent solids.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    wp = cq.importers.importStep(str(path))
    solids = wp.solids().vals()
    if not solids:
        raise ValueError(f"{path}: no solid bodies found in STEP file")
    return [_props_of(s, i, f"body_{i}") for i, s in enumerate(solids)]


def _props_of_mesh(m, index: int) -> BodyInfo:
    import numpy as np

    # Real exports contain degenerate shells (e.g. 2-triangle zero-volume
    # slivers) that trimesh flags watertight but whose mass properties are
    # non-finite. Trust nothing: validate every derived number.
    watertight = bool(m.is_watertight)
    volume, com, pm = 0.0, None, (0.0, 0.0, 0.0)
    if watertight:
        try:
            with np.errstate(invalid="ignore", divide="ignore"):
                if m.volume < 0:  # inverted winding: fix rather than report nonsense
                    m.invert()
                vol = float(m.volume)
                inertia = np.linalg.eigvalsh(m.moment_inertia)
                cm = m.center_mass
            if vol > 1e-9 and np.isfinite(inertia).all() and np.isfinite(cm).all():
                volume = vol
                com = tuple(float(c) for c in cm)
                pm = tuple(sorted(float(v) / vol for v in inertia))
            else:
                watertight = False  # degenerate: report as not-a-solid
        except np.linalg.LinAlgError:
            watertight = False
    if com is None or not watertight:
        com = tuple(float(c) for c in m.centroid)
    lo, hi = m.bounds
    return BodyInfo(
        index=index,
        name=f"body_{index}",
        volume=volume,
        area=float(m.area),
        com=com,  # type: ignore[arg-type]
        bbox=(tuple(map(float, lo)), tuple(map(float, hi))),  # type: ignore[arg-type]
        principal_moments=pm,  # type: ignore[arg-type]
        n_faces=len(m.faces),
        n_edges=len(m.edges_unique),
        solid=m,
        kind="mesh",
        watertight=watertight,
    )


def load_mesh(path: str | Path) -> list[BodyInfo]:
    """Load a mesh file (STL/3MF/OBJ/PLY); bodies = connected components."""
    import trimesh

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    loaded = trimesh.load(str(path), force=None)
    if isinstance(loaded, trimesh.Scene):
        meshes = [g for g in loaded.dump() if isinstance(g, trimesh.Trimesh)]
    else:
        meshes = [loaded]
    bodies = []
    for m in meshes:
        parts = m.split(only_watertight=False)
        bodies.extend(parts if len(parts) else [m])
    if not bodies:
        raise ValueError(f"{path}: no mesh bodies found")
    return [_props_of_mesh(m, i) for i, m in enumerate(bodies)]


def load_any(path: str | Path) -> list[BodyInfo]:
    """Dispatch by extension: STEP through OCCT, meshes through trimesh."""
    suffix = Path(path).suffix.lower()
    if suffix in BREP_SUFFIXES:
        return load_step(path)
    if suffix in MESH_SUFFIXES:
        return load_mesh(path)
    raise ValueError(f"{path}: unsupported format {suffix!r} "
                     f"(supported: {sorted(CAD_SUFFIXES)})")
