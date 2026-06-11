"""Fingerprint cache: identical results, geometry-free hits, honest degradation."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "examples"))
from make_examples import main as make_examples  # noqa: E402

from argus_diff import diff_files  # noqa: E402
from argus_diff.cache import load_any_cached  # noqa: E402


@pytest.fixture()
def cached_env(tmp_path_factory, monkeypatch):
    cache = tmp_path_factory.mktemp("cache")
    monkeypatch.setenv("ARGUS_CACHE_DIR", str(cache))
    a, b = make_examples(tmp_path_factory.mktemp("step"))
    return a, b


def test_cache_roundtrip_summary_identical(cached_env):
    a, b = cached_env
    fresh = diff_files(a, b, check_interference=False).to_dict()
    warm = diff_files(a, b, check_interference=False, use_cache=True)  # populates
    hot = diff_files(a, b, check_interference=False, use_cache=True)  # hits

    for r in (warm.to_dict(), hot.to_dict()):
        assert r["summary"]["added"] == fresh["summary"]["added"]
        assert r["summary"]["removed"] == fresh["summary"]["removed"]
        assert r["summary"]["modified"] == fresh["summary"]["modified"]
        assert r["summary"]["unchanged"] == fresh["summary"]["unchanged"]
        assert r["summary"]["volume_delta_mm3"] == fresh["summary"]["volume_delta_mm3"]


def test_cache_hit_has_no_geometry_and_degrades_honestly(cached_env):
    a, b = cached_env
    bodies, hit = load_any_cached(a)
    assert not hit and all(x.solid is not None for x in bodies)
    bodies2, hit2 = load_any_cached(a)
    assert hit2 and all(x.solid is None for x in bodies2)

    load_any_cached(b)  # warm b too, so the diff below is a full cache hit
    result = diff_files(a, b, check_interference=True, use_cache=True)
    # geometry-free: interference must report as NOT checked, never as zero-checked
    assert result.interference_checked is False
    # face localization degrades to empty, not to an error
    assert all(p.face_changes() == [] for p in result.modified)


def test_corrupt_cache_entry_self_heals(cached_env, monkeypatch):
    a, _ = cached_env
    load_any_cached(a)  # populate
    from argus_diff import cache as c

    entry = c._entry_path(c._file_sha256(Path(a)))
    entry.write_text("{not json")
    bodies, hit = load_any_cached(a)  # corrupt -> fresh load, re-store
    assert not hit and bodies and bodies[0].solid is not None
    bodies2, hit2 = load_any_cached(a)
    assert hit2
