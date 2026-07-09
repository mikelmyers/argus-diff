# Argus trust benchmark

This directory is the contract for measuring whether Argus tells the truth
about a geometric change. It is deliberately separate from the compatibility
corpus: successfully loading a public file says nothing about whether the
review narrative is correct.

## What is measured

Each labeled case declares the expected body correspondence and classification:

- `unchanged`, `modified`, `added`, and `removed` body counts;
- every expected before/after body pairing; and
- provenance, license, and permission to publish the label.

`tools/score_benchmark.py` reports exact-case accuracy and the individual
misses. A case passes only when the complete correspondence set matches; a
plausible-looking partial match is a failure.

## Evidence tiers

- **Calibration**: repository-owned generated fixtures. They prevent known
  regressions but are not evidence of field accuracy.
- **Public labeled**: an externally sourced, redistributable pair with a
  human-reviewed label and recorded provenance. These can support published
  accuracy claims.
- **Private consented**: a customer-contributed pair with explicit permission
  for the stated use. Raw geometry stays private unless the contributor also
  approves publication; only an anonymized score may be reported.

The initial manifest contains one calibration case. It intentionally makes no
claim about public accuracy. Adding public data without a reviewed label, or
calling a calibration score an accuracy number, violates this benchmark's
rules.

## Add a case

1. Record provenance, license, and contributor permission in `manifest.json`.
2. Have a second reviewer validate the expected correspondence against the
   original CAD intent, not only Argus output.
3. Run `python tools/score_benchmark.py` and commit the manifest plus the
   generated report in the PR.
4. If Argus is wrong, add the case as a regression before changing the matcher.

Run the current benchmark:

```bash
python tools/score_benchmark.py --out docs/benchmark/latest_report.json
```

The schema is documented in `manifest.schema.json`.
