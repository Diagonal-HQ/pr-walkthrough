# Rendering and review

Build reads the script, narration manifest, and every footage metadata JSON in `footage/`. Narration must match current text. Each filmed line needs a unique beat. Delete obsolete clips and their JSON metadata before rebuilding.

```bash
node "$SKILL/scripts/cli.mjs" review --footage
node "$SKILL/scripts/cli.mjs" build
node "$SKILL/scripts/cli.mjs" render --stills
node "$SKILL/scripts/cli.mjs" render --name my-change
node "$SKILL/scripts/cli.mjs" review "$WALKTHROUGH_PROJECT/out/my-change.mp4"
```

Inspect `review/stills/` and the still sheets before the full render. `render --still 12.5 /absolute/path/frame.png` renders a specific time through the same filter graph.

The result is 1920×1080, 30 fps, H.264 with limited-range BT.709 color, AAC at 48 kHz, and MP4 fast-start metadata. Captions are separate SRT and WebVTT files. `out/script-with-timings.md` is the transcript. Each rendered shot must have the expected frame count. Rendering refuses a timeline if its script, narration, or footage inputs changed after the build.

Review writes a contact sheet, full-size frames around cuts and camera moves, and `facts.md`. It checks resolution, codecs, color, timeline duration, speech loudness, and peak level. It returns nonzero on a failed media check. Silent previews skip speech loudness checks.

## Quality review

- Inspect the start and end of each beat. Check for loaded content and complete pages.
- Match every spoken claim to the visible action or result.
- Check that UI text and code are readable at 1080p.
- Keep customer data, passwords, tokens, and developer overlays out of the footage.
- Delete a camera move if it does not make the named fact easier to see.
- Listen for pronunciation, clipped words, pauses, and pops. State if audio was not checked.
- Confirm that the video reflects the final change. Re-record affected beats after relevant code changes.

Media checks establish format and timing. They do not prove the narration's claims or product correctness.

## Troubleshooting

| Problem | Action |
| --- | --- |
| Missing Chromium | Run `npx playwright install chromium` in the skill/tool directory. |
| Linux browser cannot launch | Run `npx playwright install --with-deps chromium`. |
| Output refused | Add `.walkthrough/` to the target repo's `.gitignore` and use a new folder inside it. |
| Duplicate footage beat | Remove obsolete clips and metadata, or use distinct ids. |
| Script changed after narration | Generate narration again and re-capture beats whose timing changed. |
| Action outlasts the line | Shorten the action, split the beat, or rewrite its narration. |
| Runtime or pace warning | Edit the script. `--allow-warnings` accepts reviewed warnings, never errors. |
| No captured frames | Keep the Mac display awake, close the scene browser, and retry once. |
| Login redirect | Implement project-specific login in the setup hook and wait for signed-in content. |
| No local speech | Install `espeak-ng` on Linux, or explicitly select another provider. |
| FFmpeg failure | Read its error. Keep FFmpeg, ffprobe, and Node on subprocess PATH too. |

Temporary renders use `.edit/` inside the ignored project. A successful full render removes it. Footage and review files remain for retries. Run one render per project at a time.
