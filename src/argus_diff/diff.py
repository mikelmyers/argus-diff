"""Body matching and geometric diff between two STEP files."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps

from argus_diff.loader import BodyInfo, load_any

# A matched pair whose every metric agrees within this relative tolerance is
# "unchanged". STEP round-trips are exact enough that 1e-6 holds in practice.
UNCHANGED_RTOL = 1e-6
# Above this match score, two bodies are no longer "the same body, modified" —
# they are treated as one removed and one added. Calibrated on the example
# bracket pair and the Jubilee/Voron real-world corpus: true matches (incl.
# a boss with +50% volume, and a re-origined identical part) score <= 0.83;
# the best false match scores >= 2.3 (shape-dominated).
MODIFIED_SCORE_CUTOFF = 1.5


@dataclass
class BodyPair:
    """A body from file A matched (or not) to a body from file B."""

    status: str  # "unchanged" | "modified" | "added" | "removed"
    a: BodyInfo | None
    b: BodyInfo | None
    score: float = 0.0

    def to_dict(self) -> dict:
        d: dict = {"status": self.status, "match_score": round(self.score, 6)}
        if self.a is not None:
            d["before"] = self.a.to_dict()
        if self.b is not None:
            d["after"] = self.b.to_dict()
        if self.status == "modified" and self.a and self.b:
            d["deltas"] = {
                "volume_mm3": round(self.b.volume - self.a.volume, 6),
                "volume_pct": _pct(self.a.volume, self.b.volume),
                "area_mm2": round(self.b.area - self.a.area, 6),
                "com_shift_mm": round(_dist(self.a.com, self.b.com), 6),
            }
            d["face_changes"] = self.face_changes()
        return d

    def face_changes(self, max_faces: int = 500) -> list[str]:
        """Reviewer-language face-level localization for a modified pair (B-rep only)."""
        if self.status != "modified" or self.a is None or self.b is None:
            return []
        if self.a.solid is None or self.b.solid is None:
            return []  # cached fingerprints carry no geometry
        if self.a.kind == "mesh" and self.b.kind == "mesh":
            from argus_diff.faces import mesh_change_regions

            return mesh_change_regions(self.a.solid, self.b.solid)
        if self.a.kind != "brep" or self.b.kind != "brep":
            return []  # mixed kinds: no comparable face story
        if self.a.n_faces > max_faces or self.b.n_faces > max_faces:
            return ["(face diff skipped: body has >500 faces)"]
        from argus_diff.faces import diff_faces, summarize_face_changes

        lo, hi = self.b.bbox
        scale = _dist(lo, hi)
        return summarize_face_changes(diff_faces(self.a.solid, self.b.solid, scale))


@dataclass
class Interference:
    body_i: int
    body_j: int
    overlap_volume: float

    def to_dict(self) -> dict:
        return {
            "bodies": [self.body_i, self.body_j],
            "overlap_volume_mm3": round(self.overlap_volume, 6),
        }


@dataclass
class DiffResult:
    file_a: str
    file_b: str
    pairs: list[BodyPair]
    interferences_b: list[Interference] = field(default_factory=list)
    interference_checked: bool = True

    @property
    def added(self) -> list[BodyPair]:
        return [p for p in self.pairs if p.status == "added"]

    @property
    def removed(self) -> list[BodyPair]:
        return [p for p in self.pairs if p.status == "removed"]

    @property
    def modified(self) -> list[BodyPair]:
        return [p for p in self.pairs if p.status == "modified"]

    @property
    def unchanged(self) -> list[BodyPair]:
        return [p for p in self.pairs if p.status == "unchanged"]

    @property
    def volume_a(self) -> float:
        return sum(p.a.volume for p in self.pairs if p.a)

    @property
    def volume_b(self) -> float:
        return sum(p.b.volume for p in self.pairs if p.b)

    def mass_g(self, density_g_cm3: float) -> tuple[float, float]:
        """(mass_a, mass_b) in grams for a uniform density in g/cm^3."""
        return (
            self.volume_a / 1000.0 * density_g_cm3,
            self.volume_b / 1000.0 * density_g_cm3,
        )

    def bbox_union(self, which: str) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
        infos = [getattr(p, which) for p in self.pairs if getattr(p, which)]
        los = [i.bbox[0] for i in infos]
        his = [i.bbox[1] for i in infos]
        return (
            tuple(min(c[k] for c in los) for k in range(3)),  # type: ignore[return-value]
            tuple(max(c[k] for c in his) for k in range(3)),
        )

    def to_dict(self, density_g_cm3: float = 1.0) -> dict:
        mass_a, mass_b = self.mass_g(density_g_cm3)
        bb_a, bb_b = self.bbox_union("a"), self.bbox_union("b")
        return {
            "tool": "argus-diff",
            "before": self.file_a,
            "after": self.file_b,
            "summary": {
                "bodies_before": sum(1 for p in self.pairs if p.a),
                "bodies_after": sum(1 for p in self.pairs if p.b),
                "added": len(self.added),
                "removed": len(self.removed),
                "modified": len(self.modified),
                "unchanged": len(self.unchanged),
                "volume_before_mm3": round(self.volume_a, 6),
                "volume_after_mm3": round(self.volume_b, 6),
                "volume_delta_mm3": round(self.volume_b - self.volume_a, 6),
                "volume_delta_pct": _pct(self.volume_a, self.volume_b),
                "density_g_cm3": density_g_cm3,
                "mass_before_g": round(mass_a, 6),
                "mass_after_g": round(mass_b, 6),
                "mass_delta_g": round(mass_b - mass_a, 6),
                "bbox_before_mm": [list(bb_a[0]), list(bb_a[1])],
                "bbox_after_mm": [list(bb_b[0]), list(bb_b[1])],
                "interference_checked": self.interference_checked,
                "interferences_after": len(self.interferences_b),
            },
            "bodies": [p.to_dict() for p in self.pairs],
            "interferences_after": [i.to_dict() for i in self.interferences_b],
        }


def _pct(a: float, b: float) -> float:
    if abs(a) < 1e-12:
        return float("inf") if abs(b) > 1e-12 else 0.0
    return round((b - a) / a * 100.0, 4)


def _dist(p: tuple[float, float, float], q: tuple[float, float, float]) -> float:
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(p, q)))


def _rel(a: float, b: float) -> float:
    denom = max(abs(a), abs(b), 1e-12)
    return abs(a - b) / denom


def match_score(a: BodyInfo, b: BodyInfo, scale: float) -> float:
    """0 = geometrically identical, grows with dissimilarity.

    Identity is SHAPE (volume, area, principal moments — all translation
    invariant); position enters only as a weak, capped tiebreaker so that
    identical fasteners pair with their nearest counterpart. Position must
    not anchor identity: real-world exports re-origin parts wholesale
    (seen live: a Voron-2 STL re-exported 370 mm away, shape delta <3%),
    and a moved-but-same part should classify as modified-with-shift, not
    removed+added.
    """
    s_vol = _rel(a.volume, b.volume)
    s_area = _rel(a.area, b.area)
    s_mom = sum(_rel(x, y) for x, y in zip(a.principal_moments, b.principal_moments)) / 3.0
    s_com = min(_dist(a.com, b.com) / max(scale, 1e-9), 1.0) * 0.25
    return s_vol + s_area + s_mom + s_com


def _is_unchanged(a: BodyInfo, b: BodyInfo) -> bool:
    return (
        _rel(a.volume, b.volume) < UNCHANGED_RTOL
        and _rel(a.area, b.area) < UNCHANGED_RTOL
        and _dist(a.com, b.com) < 1e-4
        and a.n_faces == b.n_faces
        and a.n_edges == b.n_edges
    )


def match_bodies(bodies_a: list[BodyInfo], bodies_b: list[BodyInfo]) -> list[BodyPair]:
    """Greedy lowest-score-first matching of bodies between two files."""
    scale = 1.0
    for info in bodies_a + bodies_b:
        lo, hi = info.bbox
        scale = max(scale, _dist(lo, hi))

    candidates = sorted(
        ((match_score(a, b, scale), a, b) for a in bodies_a for b in bodies_b),
        key=lambda t: t[0],
    )
    used_a: set[int] = set()
    used_b: set[int] = set()
    pairs: list[BodyPair] = []
    for score, a, b in candidates:
        if a.index in used_a or b.index in used_b:
            continue
        if score > MODIFIED_SCORE_CUTOFF:
            break  # remaining candidates are all worse; treat as add/remove
        used_a.add(a.index)
        used_b.add(b.index)
        status = "unchanged" if _is_unchanged(a, b) else "modified"
        pairs.append(BodyPair(status=status, a=a, b=b, score=score))

    pairs.extend(
        BodyPair(status="removed", a=a, b=None) for a in bodies_a if a.index not in used_a
    )
    pairs.extend(
        BodyPair(status="added", a=None, b=b) for b in bodies_b if b.index not in used_b
    )
    return pairs


def _bbox_overlap(a: BodyInfo, b: BodyInfo, margin: float = 1e-6) -> bool:
    (alo, ahi), (blo, bhi) = a.bbox, b.bbox
    return all(alo[k] <= bhi[k] + margin and blo[k] <= ahi[k] + margin for k in range(3))


def find_interferences(bodies: list[BodyInfo], min_volume: float = 1e-3) -> list[Interference]:
    """Pairwise solid-solid overlap check (boolean common) on one file's bodies."""
    out: list[Interference] = []
    for i in range(len(bodies)):
        for j in range(i + 1, len(bodies)):
            if not _bbox_overlap(bodies[i], bodies[j]):
                continue
            op = BRepAlgoAPI_Common(bodies[i].solid.wrapped, bodies[j].solid.wrapped)
            op.Build()
            if not op.IsDone():
                continue
            props = GProp_GProps()
            BRepGProp.VolumeProperties_s(op.Shape(), props)
            vol = props.Mass()
            if vol > min_volume:
                out.append(Interference(bodies[i].index, bodies[j].index, vol))
    return out


def diff_files(
    path_a: str | Path,
    path_b: str | Path,
    check_interference: bool = True,
    use_cache: bool = False,
) -> DiffResult:
    """Diff two CAD files (STEP or mesh): match bodies, classify, check interference.

    The interference check needs exact booleans, so it runs only when the
    new file is B-rep; mesh files skip it (reported as skipped, not as 0).

    With ``use_cache=True``, fingerprints are read/written from the content-
    hash cache; cache-hit bodies carry no geometry, so the interference
    check is skipped and face localization degrades gracefully. Use it for
    gate/summary runs, not for renders.
    """
    if use_cache:
        from argus_diff.cache import load_any_cached

        bodies_a, _ = load_any_cached(path_a)
        bodies_b, hit_b = load_any_cached(path_b)
    else:
        bodies_a = load_any(path_a)
        bodies_b = load_any(path_b)
        hit_b = False
    pairs = match_bodies(bodies_a, bodies_b)
    can_check = check_interference and not hit_b and all(b.kind == "brep" for b in bodies_b)
    interferences = find_interferences(bodies_b) if can_check else []
    return DiffResult(
        file_a=str(path_a), file_b=str(path_b), pairs=pairs, interferences_b=interferences,
        interference_checked=can_check,
    )
