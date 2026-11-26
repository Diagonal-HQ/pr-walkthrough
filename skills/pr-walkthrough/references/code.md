# Before-and-after code walkthroughs

Film readable regions of real committed source when there is no useful app surface. Code slides come from git, not working-tree edits. Use existing base/head commits or commit through the project's normal workflow first. This skill does not authorize a commit itself.

```bash
node "$SKILL/scripts/cli.mjs" init .walkthrough/backend-fix --preset code-walkthrough
export WALKTHROUGH_PROJECT="$PWD/.walkthrough/backend-fix"
```

Set `repo` in `walkthrough.json` to the target checkout. The generated value is the directory where you ran `init`. A `repo` in `code.json` takes precedence. Otherwise `code-pages` uses its current working directory.

Example `code.json`:

```json
{
  "title": "Reject invalid inputs",
  "base": "origin/main",
  "head": "HEAD",
  "slides": [
    {"id":"files","kind":"files","title":"What changed"},
    {"id":"before","ref":"base","file":"src/validate.ts","lines":"10-22"},
    {"id":"after","ref":"head","file":"src/validate.ts","lines":"10-25"},
    {"id":"test","ref":"head","file":"tests/validate.test.ts","lines":"8-20"}
  ]
}
```

The base is its merge base with head. Both refs must exist locally; no fetch runs automatically. A code slide uses `ref: base` or `head`, a file path, and an inclusive one-based range. At most 22 displayed rows fit; wrapped lines count as more rows. Changed lines are highlighted by default. `highlight: "12-15"` overrides this. A files slide accepts `exclude: ["package-lock.json"]` to omit noisy paths from that slide.

```bash
node "$SKILL/scripts/cli.mjs" code-pages
node "$SKILL/scripts/cli.mjs" narrate --provider local
node "$SKILL/scripts/cli.mjs" capture
node "$SKILL/scripts/cli.mjs" build
node "$SKILL/scripts/cli.mjs" render
```

`code-pages` writes `<project>/code/index.html`. The generated scene opens it and switches slides with `show(id)`. Edit slide ids and beat ids together. One slide can remain on screen across two related lines.

Describe only what the code and evidence establish. Showing a test file does not establish that it passed. Say whether you ran it or only inspected it. Follow the target project's test rules.
