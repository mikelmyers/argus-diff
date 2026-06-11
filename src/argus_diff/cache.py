"""Fingerprint cache: skip the expensive parse for already-seen file bytes.

OCCT parsing is ~80% of a heavy diff's wall time (measured: 87 s parse +
21 s fingerprinting per side on a 78 MB assembly). Fingerprints are tiny
and deterministic per file content, so they cache perfectly by content
hash. Cached bodies carry no geometry (`solid=None`): anything that needs
real geometry — renders, interference, face localization — must load
fresh, and callers choose that by simply not using the cache.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from argus_diff.loader import BodyInfo, load_any

# bump when BodyInfo fields or fingerprint math change — invalidates all entries
SCHEMA_VERSION = 2


def cache_dir() -> Path:
    root = os.environ.get("ARGUS_CACHE_DIR")
    if root:
        return Path(root)
    xdg = os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))
    return Path(xdg) / "argus-diff"


def _file_sha256(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while block := fh.read(chunk):
            h.update(block)
    return h.hexdigest()


def _entry_path(digest: str) -> Path:
    return cache_dir() / f"v{SCHEMA_VERSION}" / f"{digest}.json"


def _to_jsonable(b: BodyInfo) -> dict:
    d = b.to_dict()
    d["bbox"] = [list(b.bbox[0]), list(b.bbox[1])]
    d["com"] = list(b.com)
    d["principal_moments"] = list(b.principal_moments)
    d["volume"] = b.volume
    d["area"] = b.area
    return d


def _from_jsonable(d: dict) -> BodyInfo:
    return BodyInfo(
        index=d["index"],
        name=d["name"],
        volume=d["volume"],
        area=d["area"],
        com=tuple(d["com"]),
        bbox=(tuple(d["bbox"][0]), tuple(d["bbox"][1])),
        principal_moments=tuple(d["principal_moments"]),
        n_faces=d["n_faces"],
        n_edges=d["n_edges"],
        solid=None,  # cached fingerprints carry no geometry
        kind=d["kind"],
        watertight=d["watertight"],
    )


def load_any_cached(path: str | Path) -> tuple[list[BodyInfo], bool]:
    """(bodies, hit). On miss, loads fresh (bodies WITH geometry) and stores."""
    path = Path(path)
    digest = _file_sha256(path)
    entry = _entry_path(digest)
    if entry.exists():
        try:
            data = json.loads(entry.read_text())
            return [_from_jsonable(d) for d in data["bodies"]], True
        except (json.JSONDecodeError, KeyError, TypeError):
            entry.unlink(missing_ok=True)  # corrupt entry: fall through to fresh load
    bodies = load_any(path)
    entry.parent.mkdir(parents=True, exist_ok=True)
    tmp = entry.with_suffix(".tmp")
    tmp.write_text(json.dumps({"bodies": [_to_jsonable(b) for b in bodies]}))
    tmp.replace(entry)  # atomic: concurrent CI jobs never see partial entries
    return bodies, False
