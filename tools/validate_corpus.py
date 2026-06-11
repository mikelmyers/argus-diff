"""Mine public git repos for real STEP-file revisions and diff every pair.

This is the robustness harness: every (before, after) pair of a STEP file
that was actually modified in a real project's history gets run through
argus_diff, and the outcome (ok / load failure / crash, timings, body
counts) is recorded. The output table is the honest compatibility evidence
for the README — and every failure is a bug report against ourselves.

Usage:
    python tools/validate_corpus.py https://github.com/org/repo [--max-pairs N]
                                     [--max-mb 25] [--out corpus.json]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
import time
from pathlib import Path

STEP_GLOBS = ["*.step", "*.stp", "*.STEP", "*.STP", "*.Step",
              "*.stl", "*.STL", "*.3mf", "*.3MF"]


def _git(repo: Path, *args: str, binary: bool = False):
    out = subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)
    return out.stdout if binary else out.stdout.decode(errors="replace")


def clone_blobless(url: str, dest: Path) -> Path:
    subprocess.run(
        ["git", "clone", "--filter=blob:none", "--no-checkout", "--quiet", url, str(dest)],
        check=True,
    )
    return dest


def modified_step_pairs(repo: Path) -> list[tuple[str, str]]:
    """(commit, path) pairs where a STEP file was modified (not added)."""
    log = _git(
        repo, "log", "--all", "--name-status", "--diff-filter=M",
        "--pretty=C %H", "--", *STEP_GLOBS,
    )
    pairs, commit = [], None
    for line in log.splitlines():
        if line.startswith("C "):
            commit = line[2:].strip()
        elif line.startswith("M\t") and commit:
            pairs.append((commit, line.split("\t", 1)[1]))
    return pairs


def run_corpus(url: str, max_pairs: int, max_mb: float, timeout_s: int) -> dict:
    results = {"repo": url, "pairs": [], "summary": {}}
    with tempfile.TemporaryDirectory(prefix="argus_corpus_") as tmp:
        repo = clone_blobless(url, Path(tmp) / "repo")
        pairs = modified_step_pairs(repo)
        results["modified_step_revisions_found"] = len(pairs)
        for commit, path in pairs[:max_pairs]:
            rec = {"commit": commit[:10], "path": path}
            suffix = Path(path).suffix.lower()  # load dispatch is by extension
            old_f, new_f = Path(tmp) / f"old{suffix}", Path(tmp) / f"new{suffix}"
            try:
                old_f.write_bytes(_git(repo, "show", f"{commit}^:{path}", binary=True))
                new_f.write_bytes(_git(repo, "show", f"{commit}:{path}", binary=True))
                size_mb = max(old_f.stat().st_size, new_f.stat().st_size) / 1e6
                rec["max_size_mb"] = round(size_mb, 2)
                if size_mb > max_mb:
                    rec["status"] = "skipped_size"
                    results["pairs"].append(rec)
                    continue
                t0 = time.time()
                proc = subprocess.run(
                    ["python3", "-c",
                     "import sys, json; from argus_diff.diff import diff_files; "
                     "r = diff_files(sys.argv[1], sys.argv[2], check_interference=False); "
                     "print(json.dumps(r.to_dict()['summary']))",
                     str(old_f), str(new_f)],
                    capture_output=True, text=True, timeout=timeout_s,
                )
                rec["seconds"] = round(time.time() - t0, 1)
                if proc.returncode == 0:
                    rec["status"] = "ok"
                    rec["summary"] = json.loads(proc.stdout)
                else:
                    rec["status"] = "diff_error"
                    rec["error"] = proc.stderr.strip().splitlines()[-1][:200] if proc.stderr else "?"
            except subprocess.TimeoutExpired:
                rec["status"] = "timeout"
            except subprocess.CalledProcessError as exc:
                rec["status"] = "git_error"
                rec["error"] = str(exc)[:200]
            results["pairs"].append(rec)

    counted = [r for r in results["pairs"]]
    by = {}
    for r in counted:
        by[r["status"]] = by.get(r["status"], 0) + 1
    results["summary"] = by
    return results


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("repo_url")
    ap.add_argument("--max-pairs", type=int, default=10)
    ap.add_argument("--max-mb", type=float, default=25.0)
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    results = run_corpus(args.repo_url, args.max_pairs, args.max_mb, args.timeout)
    text = json.dumps(results, indent=2)
    print(text)
    if args.out:
        Path(args.out).write_text(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
