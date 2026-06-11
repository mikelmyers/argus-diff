---
name: Broken or wrong diff
about: argus crashed, misclassified, or reported numbers you can show are wrong
labels: bug
---

**The file pair** (this is the part we actually need)

Attach both files (zip them; STEP/STL/3MF up to GitHub's limit), or a
script that generates the pair, or — if the files are proprietary — the
output of `argus diff a b --json out.json` with whatever you can share.

**What argus said**

```
(paste the terminal output)
```

**What is actually true about the change**

e.g. "only one hole moved, but it reports 3 modified bodies", "these two
bodies are identical but classified added+removed".

**Versions**: `argus --version`, OS, `pip show cadquery trimesh | grep -i version`
