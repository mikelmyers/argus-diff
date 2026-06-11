"""Boot contract for argus-diff: load, match, classify, gate."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "examples"))
from make_examples import main as make_examples  # noqa: E402

from argus_diff import diff_files, load_step  # noqa: E402


@pytest.fixture(scope="session")
def example_pair(tmp_path_factory):
    return make_examples(tmp_path_factory.mktemp("step"))


def test_load_step(example_pair):
    a, b = example_pair
    bodies_a = load_step(a)
    bodies_b = load_step(b)
    assert len(bodies_a) == 4  # plate, boss, locating_pin, dowel
    assert len(bodies_b) == 4  # plate, boss, gusset, dowel
    assert all(i.volume > 0 for i in bodies_a + bodies_b)


def test_identical_files_diff_clean(example_pair):
    a, _ = example_pair
    result = diff_files(a, a, check_interference=False)
    assert len(result.unchanged) == 4
    assert not result.added and not result.removed and not result.modified


def test_revision_diff_classification(example_pair):
    a, b = example_pair
    result = diff_files(a, b, check_interference=False)
    assert len(result.added) == 1  # gusset
    assert len(result.removed) == 1  # locating_pin
    assert len(result.modified) == 2  # plate, boss
    assert len(result.unchanged) == 1  # dowel
    # plate got thicker and boss got bigger: net volume must increase
    assert result.volume_b > result.volume_a


def test_face_level_localization(example_pair):
    a, b = example_pair
    result = diff_files(a, b, check_interference=False)
    all_lines = [line for p in result.modified for line in p.face_changes()]
    # the four corner holes opened from d5 to d6
    assert any("radius 2.500 -> 3.000" in line and line.startswith("4x") for line in all_lines)
    # the boss OD grew from 20 to 24
    assert any("radius 10.000 -> 12.000" in line for line in all_lines)


def test_cli_json_and_gates(example_pair, tmp_path):
    a, b = example_pair
    out = tmp_path / "diff.json"
    proc = subprocess.run(
        [sys.executable, "-m", "argus_diff.cli", "diff", str(a), str(b),
         "--json", str(out), "--max-mass-delta-pct", "5"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 1, proc.stderr  # >5% mass growth trips the gate
    data = json.loads(out.read_text())
    assert data["summary"]["added"] == 1
    assert data["summary"]["volume_delta_pct"] > 5

    proc_ok = subprocess.run(
        [sys.executable, "-m", "argus_diff.cli", "diff", str(a), str(b)],
        capture_output=True, text=True,
    )
    assert proc_ok.returncode == 0, proc_ok.stderr
    assert "1 added" in proc_ok.stdout and "1 removed" in proc_ok.stdout
