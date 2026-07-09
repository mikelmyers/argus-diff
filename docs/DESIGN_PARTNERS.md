# Argus design-partner program

Argus is looking for hardware teams with a real CAD revision that was hard to
review: a confusing STEP/STL change, a suspected interference, a mass/envelope
change, or an export that made normal Git diffs useless.

## What you get

We run the two revisions through Argus and return the raw JSON, terminal
summary, and visual diff. We also explain any ambiguity or limitation we find.
This is free during alpha. It is not a certification, release approval, or
substitute for an engineer's review.

## Choose your data policy before sending files

1. **Process and delete** — the files are used only to return your report and
   are deleted after delivery. Do not attach proprietary files to a public
   GitHub issue; use the private contact route on argusdiff.com.
2. **Private improvement** — we may retain the pair privately to reproduce a
   bug or improve Argus. It is never published or used to make a public
   accuracy claim.
3. **Public benchmark** — you permit publication of the pair and its
   human-reviewed ground-truth label under the documented license. This is the
   only route that can contribute to Argus's reproducible public benchmark.

For every contribution, tell us what actually changed according to the design
intent. A useful label is specific: “the four M3 holes moved 2 mm; all other
bodies are unchanged,” not simply “the file changed.”

## Public projects

For a public repository, open the **Benchmark case / design partner** issue
template and link the exact base and head commits. Attach no credentials and
do not paste non-public geometry. We will confirm the proposed evidence tier
before recording or publishing anything.

## What we measure

The [trust benchmark](benchmark/) scores exact body correspondence and
classification. Calibration cases prevent regressions; only externally sourced,
human-reviewed public cases can support public accuracy claims.
