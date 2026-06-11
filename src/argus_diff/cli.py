"""argus — CLI entry point.

Exit codes: 0 = ok (or differences within gates), 1 = a CI gate failed,
2 = usage/load error.
"""

from __future__ import annotations

import argparse
import json
import sys

from argus_diff import __version__
from argus_diff.diff import DiffResult, diff_files


def _fmt_summary(result: DiffResult, density: float) -> str:
    s = result.to_dict(density)["summary"]
    lines = [
        f"argus-diff {__version__}",
        f"  before: {result.file_a}  ({s['bodies_before']} bodies)",
        f"  after:  {result.file_b}  ({s['bodies_after']} bodies)",
        "",
        f"  + {s['added']} added   - {s['removed']} removed   "
        f"~ {s['modified']} modified   = {s['unchanged']} unchanged",
        "",
        f"  volume: {s['volume_before_mm3']:.1f} -> {s['volume_after_mm3']:.1f} mm^3 "
        f"({s['volume_delta_pct']:+.2f}%)",
        f"  mass:   {s['mass_before_g']:.2f} -> {s['mass_after_g']:.2f} g "
        f"@ {density} g/cm^3 ({s['mass_delta_g']:+.2f} g)",
        f"  interferences (after): {s['interferences_after']}",
    ]
    for p in result.modified:
        pd = p.to_dict()
        d = pd["deltas"]
        lines.append(
            f"    ~ {p.a.name} -> {p.b.name}: vol {d['volume_pct']:+.2f}%, "
            f"com shift {d['com_shift_mm']:.3f} mm"
        )
        lines.extend(f"        . {fc}" for fc in pd.get("face_changes", []))
    for p in result.added:
        lines.append(f"    + {p.b.name}: {p.b.volume:.1f} mm^3")
    for p in result.removed:
        lines.append(f"    - {p.a.name}: {p.a.volume:.1f} mm^3")
    for i in result.interferences_b:
        lines.append(
            f"    ! interference body_{i.body_i} x body_{i.body_j}: "
            f"{i.overlap_volume:.3f} mm^3 overlap"
        )
    return "\n".join(lines)


def _apply_gates(result: DiffResult, args: argparse.Namespace) -> list[str]:
    failures: list[str] = []
    s = result.to_dict(args.density)["summary"]
    if args.fail_on_interference and s["interferences_after"] > 0:
        failures.append(f"GATE interference: {s['interferences_after']} overlapping body pair(s)")
    if args.max_mass_delta_pct is not None:
        delta = abs(s["volume_delta_pct"])
        if delta > args.max_mass_delta_pct:
            failures.append(
                f"GATE mass delta: |{s['volume_delta_pct']:+.2f}%| > {args.max_mass_delta_pct}%"
            )
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="argus", description=__doc__)
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    d = sub.add_parser("diff", help="geometric diff of two STEP files")
    d.add_argument("before", help="STEP file (old revision)")
    d.add_argument("after", help="STEP file (new revision)")
    d.add_argument("--json", metavar="PATH", help="write full structured diff as JSON")
    d.add_argument("--render", metavar="PATH", help="write before/after/overlay PNG")
    d.add_argument("--density", type=float, default=1.0, help="g/cm^3 for mass figures (default 1.0)")
    d.add_argument("--no-interference", action="store_true", help="skip solid-overlap check")
    d.add_argument("--cache", action="store_true",
                   help="use the fingerprint cache (fast repeat runs; disables "
                        "interference/face detail on cache hits; ignored with --render)")
    d.add_argument("--fail-on-interference", action="store_true",
                   help="exit 1 if the new file has overlapping bodies")
    d.add_argument("--max-mass-delta-pct", type=float, default=None,
                   help="exit 1 if |mass delta %%| exceeds this")

    c = sub.add_parser("ci", help="diff all STEP files changed between two git refs")
    c.add_argument("--repo", default=".", help="git repository root (default: cwd)")
    c.add_argument("--base", required=True, help="base ref (e.g. origin/main)")
    c.add_argument("--head", default="HEAD", help="head ref (default: HEAD)")
    c.add_argument("--render-dir", metavar="DIR", help="write per-file diff PNGs here")
    c.add_argument("--markdown", metavar="PATH", help="write a PR-comment-ready report here")
    c.add_argument("--density", type=float, default=1.0, help="g/cm^3 for mass figures")
    c.add_argument("--fail-on-interference", action="store_true")
    c.add_argument("--max-mass-delta-pct", type=float, default=None)
    c.add_argument("--receipt-ledger", metavar="PATH",
                   help="append an argus-receipts execution receipt per diffed file "
                        "(requires the argus-receipts package)")

    pc = sub.add_parser("precommit", help="summarize geometric changes of staged STEP files")
    pc.add_argument("paths", nargs="*", help="STEP files (pre-commit passes these)")
    pc.add_argument("--repo", default=".")
    pc.add_argument("--density", type=float, default=1.0)

    args = parser.parse_args(argv)

    if args.command == "precommit":
        from pathlib import Path

        from argus_diff.ci import diff_worktree_file

        rc = 0
        for path in args.paths:
            try:
                result = diff_worktree_file(Path(args.repo), path)
            except Exception as exc:  # noqa: BLE001 — new/unreadable files just inform
                print(f"argus: {path}: not diffed ({type(exc).__name__}); "
                      "new file or no committed version")
                continue
            print(_fmt_summary(result, args.density))
        return rc

    if args.command == "ci":
        from pathlib import Path

        from argus_diff.ci import run_ci, to_markdown

        reports, failed = run_ci(
            Path(args.repo),
            base=args.base,
            head=args.head,
            render_dir=Path(args.render_dir) if args.render_dir else None,
            density=args.density,
            fail_on_interference=args.fail_on_interference,
            max_mass_delta_pct=args.max_mass_delta_pct,
        )
        md = to_markdown(reports, args.density)
        print(md)
        if args.markdown:
            with open(args.markdown, "w") as fh:
                fh.write(md)
        if args.receipt_ledger:
            try:
                from argus_receipts import Ledger
            except ImportError:
                print("argus: --receipt-ledger needs `pip install argus-receipts`",
                      file=sys.stderr)
                return 2
            ledger = Ledger(args.receipt_ledger)
            for r in reports:
                artifacts = [p for p in (r.render,) if p is not None]
                summary = r.result.to_dict(args.density)["summary"] if r.result else None
                ledger.record(
                    actor="argus-ci",
                    action=f"argus ci diff {r.path} ({args.base}..{args.head})",
                    exit_code=1 if (r.gate_failures or r.status == "error") else 0,
                    artifacts=artifacts,
                    meta={"status": r.status, "summary": summary,
                          "gate_failures": r.gate_failures or []},
                )
            print(f"\n  receipts: {len(reports)} appended to {args.receipt_ledger}")
        return 1 if failed else 0

    use_cache = args.cache and not args.render
    if args.cache and args.render:
        print("argus: note: --render needs real geometry; cache bypassed", file=sys.stderr)
    try:
        result = diff_files(args.before, args.after,
                            check_interference=not args.no_interference,
                            use_cache=use_cache)
    except (FileNotFoundError, ValueError) as exc:
        print(f"argus: error: {exc}", file=sys.stderr)
        return 2

    print(_fmt_summary(result, args.density))

    if args.json:
        with open(args.json, "w") as fh:
            json.dump(result.to_dict(args.density), fh, indent=2)
        print(f"\n  json:   {args.json}")

    if args.render:
        from argus_diff.render import render_diff

        out = render_diff(result, args.render)
        print(f"  render: {out}")

    failures = _apply_gates(result, args)
    if failures:
        print("\n" + "\n".join(failures), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
