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
    # OCCT's volume integral is signed by shell orientation. Some valid STEP
    # exporters emit inward-oriented solids, but orientation is not negative
    # physical material: expose a positive volume to matching and reporting.
    signed_volume = vp.Mass()
    volume = abs(signed_volume)
    com = vp.CentreOfMass()

    sp = GProp_GProps()
    BRepGProp.SurfaceProperties_s(shape, sp)
    area = sp.Mass()

    box = Bnd_Box()
    BRepBndLib.Add_s(shape, box)
    xmin, ymin, zmin, xmax, ymax, zmax = box.Get()

    moments = vp.PrincipalProperties().Moments()
    # Normalize by volume so the fingerprint is scale-honest but unit-stable.
    norm = volume if volume > 1e-12 else 1.0
    # The inertia tensor carries the same integration sign as volume. Normalize
    # its principal values to the orientation-independent physical magnitudes.
    pm = tuple(sorted(abs(m) / norm for m in moments))

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


def _named_solids_xcaf(path: Path) -> list[tuple[str | None, cq.Solid]]:
    """Extract (product_name, located_solid) pairs via the STEP XCAF layer.

    STEP files carry product names; the plain importer discards them. Walk
    the assembly graph applying instance locations so solids land in world
    coordinates (product shapes themselves are in local frames).
    """
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPCAFControl import STEPCAFControl_Reader
    from OCP.TCollection import TCollection_ExtendedString
    from OCP.TDataStd import TDataStd_Name
    from OCP.TDF import TDF_Label, TDF_LabelSequence
    from OCP.TDocStd import TDocStd_Document
    from OCP.TopAbs import TopAbs_SOLID
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopLoc import TopLoc_Location
    from OCP.XCAFDoc import XCAFDoc_DocumentTool

    def name_of(lab):
        a = TDataStd_Name()
        if lab.FindAttribute(TDataStd_Name.GetID_s(), a):
            n = a.Get().ToExtString().strip()
            # kernel-generated placeholder, not a human part name
            if n.startswith("Open CASCADE STEP translator"):
                return None
            return n or None
        return None

    doc = TDocStd_Document(TCollection_ExtendedString("argus"))
    reader = STEPCAFControl_Reader()
    reader.SetNameMode(True)
    if reader.ReadFile(str(path)) != IFSelect_RetDone:
        raise ValueError(f"{path}: STEP read failed")
    reader.Transfer(doc)
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    roots = TDF_LabelSequence()
    st.GetFreeShapes(roots)

    out: list[tuple[str | None, cq.Solid]] = []

    def walk(lab, loc, inherited):
        nm = name_of(lab) or inherited
        if st.IsAssembly_s(lab):
            comps = TDF_LabelSequence()
            st.GetComponents_s(lab, comps)
            for j in range(1, comps.Length() + 1):
                comp = comps.Value(j)
                cloc = loc.Multiplied(st.GetLocation_s(comp))
                ref = TDF_Label()
                if st.GetReferredShape_s(comp, ref):
                    walk(ref, cloc, name_of(comp) or nm)
                else:
                    walk(comp, cloc, nm)
        else:
            shape = st.GetShape_s(lab)
            if not loc.IsIdentity():
                shape = shape.Moved(loc)
            ex = TopExp_Explorer(shape, TopAbs_SOLID)
            while ex.More():
                out.append((nm, cq.Solid(ex.Current())))
                ex.Next()

    for i in range(1, roots.Length() + 1):
        walk(roots.Value(i), TopLoc_Location(), None)
    return out


def load_step(path: str | Path) -> list[BodyInfo]:
    """Load a STEP file and return per-solid geometric fingerprints.

    Assemblies and compounds are flattened to their constituent solids.
    Product names from the STEP structure are preserved when present
    ("plate", "boss"), falling back to body_N; duplicates get #2, #3...
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    pairs: list[tuple[str | None, cq.Solid]] = []
    try:
        pairs = _named_solids_xcaf(path)
    except Exception:
        pairs = []  # XCAF path is an enhancement, never a gate
    if not pairs:
        wp = cq.importers.importStep(str(path))
        pairs = [(None, s) for s in wp.solids().vals()]
    if not pairs:
        raise ValueError(f"{path}: no solid bodies found in STEP file")
    seen: dict[str, int] = {}
    bodies = []
    for i, (nm, solid) in enumerate(pairs):
        base = nm or f"body_{i}"
        seen[base] = seen.get(base, 0) + 1
        unique = base if seen[base] == 1 else f"{base}#{seen[base]}"
        bodies.append(_props_of(solid, i, unique))
    return bodies


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
