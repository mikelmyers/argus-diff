# Contributing

The most valuable contribution right now is a **file pair that breaks the
tool**: two revisions of a real STEP/STL/3MF where `argus diff` crashes,
misclassifies, or lies. Open an issue with the pair attached (or a script
that generates it — see `examples/make_examples.py` for the pattern).
Every defect in our corpus (`docs/corpus/`) came from real files; yours
extends it.

## Dev setup

```bash
pip install -e ".[dev]"
xvfb-run -a pytest tests/ -v     # renders need a framebuffer on Linux
ruff check src/ tests/ examples/ tools/
```

## Ground rules

- Every behavioral claim in docs must be reproducible from a committed
  script — that includes benchmark numbers in your PR description.
- Honest degradation beats silent wrongness: if a path can't compute
  something (open mesh volume, mesh interference), it must say so in the
  output, never report a fabricated value. PRs that trade this away for
  convenience will be declined.
- Tests accompany behavior changes. A real-file regression (added to the
  corpus harness) beats a synthetic one where possible.
- Keep dependencies minimal and open: OCCT/cadquery, trimesh, numpy,
  pyvista (render extra). New runtime deps need a strong case.
