"""`argus ci` — diff every STEP file changed between two git refs.

Designed for CI: writes a markdown report (PR comment / step summary), renders
per-file visual diffs, and exits nonzero if a gate fails on any file.
"""

from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from argus_diff.diff import DiffResult, diff_files
from argus_diff.loader import CAD_SUFFIXES


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout


@dataclass
class FileReport:
    path: str
    status: str  # "modified" | "added" | "removed" | "error"
    result: DiffResult | None = None
    render: Path | None = None
    error: str = ""
    gate_failures: list[str] | None = None


def changed_step_files(repo: Path, base: str, head: str = "HEAD") -> list[tuple[str, str]]:
    """(git status letter, path) for CAD files changed between base and head."""
    out = _git(repo, "diff", "--name-status", f"{base}...{head}")
    changes = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        status, path = parts[0], parts[-1]
        if Path(path).suffix.lower() in CAD_SUFFIXES:
            changes.append((status[0], path))
    return changes


def _extract(repo: Path, ref: str, path: str, dest: Path) -> None:
    blob = subprocess.run(
        ["git", "-C", str(repo), "show", f"{ref}:{path}"], check=True, capture_output=True
    ).stdout
    dest.write_bytes(blob)


def run_ci(
    repo: Path,
    base: str,
    head: str = "HEAD",
    render_dir: Path | None = None,
    density: float = 1.0,
    fail_on_interference: bool = False,
    max_mass_delta_pct: float | None = None,
) -> tuple[list[FileReport], bool]:
    """Diff all changed STEP files. Returns (reports, any_gate_failed)."""
    reports: list[FileReport] = []
    any_failed = False
    with tempfile.TemporaryDirectory(prefix="argus_ci_") as tmp:
        tmpdir = Path(tmp)
        for i, (letter, path) in enumerate(changed_step_files(repo, base, head)):
            if letter == "A":
                reports.append(FileReport(path=path, status="added"))
                continue
            if letter == "D":
                reports.append(FileReport(path=path, status="removed"))
                continue
            suffix = Path(path).suffix.lower()  # keep it: load dispatch is by extension
            old = tmpdir / f"{i}_old{suffix}"
            new = tmpdir / f"{i}_new{suffix}"
            try:
                _extract(repo, base, path, old)
                _extract(repo, head, path, new)
                result = diff_files(old, new)
                result.file_a, result.file_b = f"{path}@{base}", f"{path}@{head}"
                report = FileReport(path=path, status="modified", result=result)
                failures = []
                s = result.to_dict(density)["summary"]
                if fail_on_interference and s["interferences_after"] > 0:
                    failures.append(f"interference: {s['interferences_after']} pair(s)")
                if max_mass_delta_pct is not None and abs(s["volume_delta_pct"]) > max_mass_delta_pct:
                    failures.append(
                        f"mass delta {s['volume_delta_pct']:+.2f}% exceeds ±{max_mass_delta_pct}%"
                    )
                report.gate_failures = failures
                any_failed = any_failed or bool(failures)
                if render_dir is not None:
                    from argus_diff.render import render_diff

                    out = Path(render_dir) / (path.replace("/", "__") + ".png")
                    report.render = render_diff(result, out)
                reports.append(report)
            except Exception as exc:  # noqa: BLE001 — one bad file must not kill the report
                reports.append(FileReport(path=path, status="error", error=str(exc)))
                any_failed = True
    return reports, any_failed


def diff_worktree_file(repo: Path, path: str, ref: str = "HEAD") -> DiffResult:
    """Diff a working-tree CAD file against its committed version."""
    with tempfile.TemporaryDirectory(prefix="argus_pc_") as tmp:
        old = Path(tmp) / f"old{Path(path).suffix.lower()}"
        _extract(repo, ref, path, old)
        result = diff_files(old, repo / path, check_interference=False)
    result.file_a, result.file_b = f"{path}@{ref}", f"{path} (working tree)"
    return result


def to_markdown(reports: list[FileReport], density: float = 1.0) -> str:
    if not reports:
        return "**argus-diff:** no STEP files changed.\n"
    lines = ["## argus-diff — geometric changes\n"]
    for r in reports:
        if r.status == "added":
            lines.append(f"### `{r.path}` — new file\n")
            continue
        if r.status == "removed":
            lines.append(f"### `{r.path}` — deleted\n")
            continue
        if r.status == "error":
            lines.append(f"### `{r.path}` — ⚠️ could not diff: {r.error}\n")
            continue
        s = r.result.to_dict(density)["summary"]
        lines.append(f"### `{r.path}`\n")
        lines.append(
            f"| bodies | volume | mass @ {density} g/cm³ | interference |\n"
            f"|---|---|---|---|\n"
            f"| +{s['added']} −{s['removed']} ~{s['modified']} ={s['unchanged']} "
            f"| {s['volume_delta_pct']:+.2f}% "
            f"| {s['mass_delta_g']:+.2f} g "
            f"| {s['interferences_after']} |\n"
        )
        if r.gate_failures:
            lines.append("\n".join(f"- ❌ **GATE** {f}" for f in r.gate_failures) + "\n")
        if r.render:
            lines.append(f"\n*render: `{r.render.name}` (workflow artifact)*\n")
    return "\n".join(lines)
