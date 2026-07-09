"""Score Argus against labeled body-correspondence benchmark cases.

Only ``public_labeled`` cases may be used in published accuracy claims.
Calibration cases protect known behavior; they are deliberately excluded from
the public accuracy metric.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import tempfile
from pathlib import Path
from typing import Any

from argus_diff.diff import diff_files

VALID_TIERS = {"calibration", "public_labeled", "private_consented"}
VALID_STATUSES = {"unchanged", "modified", "added", "removed"}


def _pair_record(status: str, before: str | None, after: str | None) -> tuple[str, str | None, str | None]:
    return status, before, after


def _run_generator(root: Path, source: dict[str, Any], outdir: Path) -> tuple[Path, Path]:
    script = root / source["script"]
    spec = importlib.util.spec_from_file_location("argus_benchmark_fixture", script)
    if spec is None or spec.loader is None:
        raise ValueError(f"could not import benchmark generator {script}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    generated = getattr(module, source.get("callable", "main"))(outdir)
    if not isinstance(generated, tuple) or len(generated) != 2:
        raise ValueError(f"benchmark generator {script} must return (before, after)")
    return Path(generated[0]), Path(generated[1])


def _validate_case(case: dict[str, Any]) -> None:
    missing = {"id", "tier", "source", "provenance", "expected"} - case.keys()
    if missing:
        raise ValueError(f"benchmark case missing {sorted(missing)}")
    if case["tier"] not in VALID_TIERS:
        raise ValueError(f"{case['id']}: unsupported tier {case['tier']!r}")
    if {"license", "permission", "reviewed_by"} - case["provenance"].keys():
        raise ValueError(f"{case['id']}: incomplete provenance")
    for pair in case["expected"].get("pairs", []):
        if pair.get("status") not in VALID_STATUSES:
            raise ValueError(f"{case['id']}: invalid expected pair status")


def score_case(root: Path, case: dict[str, Any]) -> dict[str, Any]:
    _validate_case(case)
    source = case["source"]
    if source.get("kind") != "generator":
        raise ValueError(f"{case['id']}: only generated fixtures are supported yet")
    with tempfile.TemporaryDirectory(prefix="argus_benchmark_") as tmp:
        before, after = _run_generator(root, source, Path(tmp))
        result = diff_files(before, after, check_interference=False)

    actual_counts = {status: len(getattr(result, status)) for status in VALID_STATUSES}
    actual_pairs = sorted(
        _pair_record(pair.status, pair.a.name if pair.a else None, pair.b.name if pair.b else None)
        for pair in result.pairs
    )
    expected = case["expected"]
    expected_counts = expected["counts"]
    expected_pairs = sorted(
        _pair_record(pair["status"], pair.get("before"), pair.get("after"))
        for pair in expected["pairs"]
    )
    counts_match = actual_counts == expected_counts
    pairs_match = actual_pairs == expected_pairs
    return {
        "id": case["id"],
        "tier": case["tier"],
        "passed": counts_match and pairs_match,
        "counts_match": counts_match,
        "pairs_match": pairs_match,
        "expected_counts": expected_counts,
        "actual_counts": actual_counts,
        "expected_pairs": [list(pair) for pair in expected_pairs],
        "actual_pairs": [list(pair) for pair in actual_pairs],
    }


def score_manifest(root: Path, manifest_path: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("schema_version") != 1:
        raise ValueError("unsupported benchmark manifest schema")
    reports = [score_case(root, case) for case in manifest.get("cases", [])]
    public = [report for report in reports if report["tier"] == "public_labeled"]
    return {
        "schema_version": 1,
        "cases": reports,
        "summary": {
            "labeled_cases": len(reports),
            "passed_cases": sum(report["passed"] for report in reports),
            "public_labeled_cases": len(public),
            "public_exact_case_accuracy": (
                sum(report["passed"] for report in public) / len(public) if public else None
            ),
            "note": "null public accuracy means no public labeled cases exist; do not infer accuracy from calibration.",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default="docs/benchmark/manifest.json")
    parser.add_argument("--root", default=".")
    parser.add_argument("--out")
    args = parser.parse_args()
    report = score_manifest(Path(args.root).resolve(), Path(args.manifest).resolve())
    text = json.dumps(report, indent=2)
    print(text)
    if args.out:
        Path(args.out).write_text(text + "\n")
    return 0 if report["summary"]["passed_cases"] == report["summary"]["labeled_cases"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
