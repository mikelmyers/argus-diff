"""`argus ci` against a real throwaway git repo."""

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "examples"))
from make_examples import rev_a, rev_b  # noqa: E402

from argus_diff.ci import run_ci, to_markdown  # noqa: E402


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture(scope="module")
def step_repo(tmp_path_factory):
    repo = tmp_path_factory.mktemp("repo")
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "ci@argus.test")
    _git(repo, "config", "user.name", "argus ci test")
    _git(repo, "config", "commit.gpgsign", "false")  # CI sandboxes may force signing
    rev_a().export(str(repo / "bracket.step"))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "rev a")
    _git(repo, "tag", "base")
    rev_b().export(str(repo / "bracket.step"))
    (repo / "new_part.step").write_text("")  # added file, content irrelevant
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "rev b")
    return repo


def test_ci_reports_and_gates(step_repo):
    reports, failed = run_ci(step_repo, base="base", fail_on_interference=True)
    by_path = {r.path: r for r in reports}
    assert by_path["bracket.step"].status == "modified"
    assert by_path["bracket.step"].gate_failures  # the deliberate boss/gusset overlap
    assert by_path["new_part.step"].status == "added"
    assert failed

    md = to_markdown(reports)
    assert "bracket.step" in md and "GATE" in md and "new file" in md


def test_precommit_worktree_diff(step_repo):
    from argus_diff.ci import diff_worktree_file

    rev_a().export(str(step_repo / "bracket.step"))  # working tree back to rev a
    try:
        result = diff_worktree_file(step_repo, "bracket.step")  # HEAD is rev b
        assert result.modified and result.removed  # gusset gone vs HEAD
    finally:
        rev_b().export(str(step_repo / "bracket.step"))


def test_ci_clean_when_no_gates(step_repo):
    reports, failed = run_ci(step_repo, base="base")
    assert not failed
    assert {r.status for r in reports} == {"modified", "added"}


def test_ci_receipt_ledger(step_repo, tmp_path):
    pytest.importorskip("argus_receipts")
    ledger_path = tmp_path / "receipts.jsonl"
    proc = subprocess.run(
        [sys.executable, "-m", "argus_diff.cli", "ci", "--repo", str(step_repo),
         "--base", "base", "--receipt-ledger", str(ledger_path)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    from argus_receipts import Ledger

    report = Ledger(ledger_path).verify()
    assert report.ok and report.receipts == 2  # bracket.step + new_part.step
