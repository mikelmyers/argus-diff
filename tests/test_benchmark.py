"""The trust-benchmark contract must execute and stay honest about its evidence."""

import importlib.util
import json
from pathlib import Path


def _load_scorer():
    root = Path(__file__).parent.parent
    spec = importlib.util.spec_from_file_location("score_benchmark", root / "tools" / "score_benchmark.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_calibration_benchmark_passes_without_claiming_public_accuracy():
    root = Path(__file__).parent.parent
    report = _load_scorer().score_manifest(root, root / "docs" / "benchmark" / "manifest.json")

    assert report["summary"]["labeled_cases"] == 1
    assert report["summary"]["passed_cases"] == 1
    assert report["summary"]["public_labeled_cases"] == 0
    assert report["summary"]["public_exact_case_accuracy"] is None


def test_committed_benchmark_report_matches_the_executable_manifest():
    root = Path(__file__).parent.parent
    actual = _load_scorer().score_manifest(root, root / "docs" / "benchmark" / "manifest.json")
    committed = json.loads((root / "docs" / "benchmark" / "latest_report.json").read_text())

    assert committed == actual
