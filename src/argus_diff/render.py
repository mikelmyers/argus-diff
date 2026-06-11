"""Rendered visual comparison: before / after / overlay panes."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from argus_diff.diff import DiffResult
from argus_diff.loader import BodyInfo

COLORS = {
    "unchanged": "#9aa3ad",
    "modified_before": "#e0a14f",
    "modified": "#f59e0b",
    "removed": "#ef4444",
    "added": "#22c55e",
}


def _mesh(info: BodyInfo, tol: float = 0.2):
    import pyvista as pv

    points, tris = info.triangles(tol)
    faces = np.hstack([np.full((len(tris), 1), 3, dtype=np.int64),
                       np.asarray(tris, dtype=np.int64)])
    return pv.PolyData(points, faces)


def render_diff(result: DiffResult, out_path: str | Path, size: tuple[int, int] = (1800, 700)) -> Path:
    """Write a before/after/overlay PNG for a diff result. Needs pyvista (+ a display or xvfb)."""
    import pyvista as pv

    if hasattr(pv, "start_xvfb"):  # removed in pyvista >= 0.48; use xvfb-run instead
        try:  # headless CI: start a virtual framebuffer if no display is up
            pv.start_xvfb()
        except (OSError, RuntimeError):
            pass

    pl = pv.Plotter(off_screen=True, shape=(1, 3), window_size=list(size), border=False)

    def add(pane: int, info: BodyInfo, color: str, opacity: float = 1.0):
        pl.subplot(0, pane)
        pl.add_mesh(_mesh(info), color=color, opacity=opacity, smooth_shading=True,
                    specular=0.3, show_edges=False)

    # Pane 0: BEFORE — unchanged gray, modified amber, removed red.
    # Pane 1: AFTER  — unchanged gray, modified amber, added green.
    # Pane 2: OVERLAY — after solid, removed bodies ghosted red, modified-before ghosted.
    for p in result.pairs:
        if p.status == "unchanged":
            add(0, p.a, COLORS["unchanged"])
            add(1, p.b, COLORS["unchanged"])
            add(2, p.b, COLORS["unchanged"], opacity=0.95)
        elif p.status == "modified":
            add(0, p.a, COLORS["modified_before"])
            add(1, p.b, COLORS["modified"])
            add(2, p.a, COLORS["modified_before"], opacity=0.25)
            add(2, p.b, COLORS["modified"], opacity=0.5)
        elif p.status == "removed":
            add(0, p.a, COLORS["removed"])
            add(2, p.a, COLORS["removed"], opacity=0.85)
        elif p.status == "added":
            add(1, p.b, COLORS["added"])
            add(2, p.b, COLORS["added"], opacity=0.95)

    titles = ["BEFORE", "AFTER", "OVERLAY  (red=removed, green=added, amber=modified)"]
    for pane, title in enumerate(titles):
        pl.subplot(0, pane)
        pl.add_text(title, font_size=11, color="black")
        pl.set_background("white")
        pl.camera_position = "iso"
        # drop below the iso horizon so underside features stay visible
        pl.camera.elevation = -25

    pl.link_views()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pl.screenshot(str(out_path))
    pl.close()
    return out_path
