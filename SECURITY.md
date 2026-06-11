# Security policy

## Reporting

Email security reports to the address in the repo description (until the
domain mailbox exists: open a GitHub Security Advisory — preferred — or a
private vulnerability report). You will get an acknowledgment within 24
hours and an honest assessment within 72.

## Scope notes that matter for this tool

- `argus` parses untrusted CAD files with OCCT and trimesh. Treat files
  from unknown sources the way you'd treat any parser input: a malicious
  STEP/STL can at minimum hang or crash the process. Run CI diffs in the
  isolated runners you already use; the GitHub Action does this by
  default.
- `argus ci` executes `git` against the repository it's pointed at and
  writes only to paths you pass (`--render-dir`, `--markdown`,
  `--receipt-ledger`).
- No telemetry, no network calls at runtime. The only network access in
  this codebase is in `tools/validate_corpus.py` (explicit git clones you
  invoke yourself).

## Disclosure

Confirmed vulnerabilities get a fix or mitigation before public detail,
a CHANGELOG entry, and credit if you want it. We do not sue researchers.
