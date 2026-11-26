---
name: pr-walkthrough
description: Create a narrated pull request walkthrough from a running web app or real before-and-after git code. Use for PR videos, feature demos, and code walkthrough videos.
---

# PR walkthrough

Deliver a short, accurate video that helps the reviewer understand the change. Film the running product for visible behavior. Use code slides for changes without a useful visible surface.

The tools are in this skill's `scripts/` folder. Set `SKILL` to the absolute directory containing this file. Invoke commands as `node "$SKILL/scripts/cli.mjs" <command>`. Run them from the target application's checkout, not from this skill's directory. `node ... --help` lists the commands.

## Start

Read the request and the PR diff. Determine the audience, the one result to show, and the requested length. Make reasonable choices for missing details. Keep user choices about narration, length, framing, and publishing.

Run `doctor`. If dependencies are missing, install this skill's packages with `npm ci --workspaces=false` from its directory. Install Chromium with `npx playwright install chromium` there. Python uses its standard library. FFmpeg and `ffprobe` must be on PATH.

Create the project with `init .walkthrough/<name> --preset feature-clip` (or `code-walkthrough`, `product-walkthrough`). Add `.walkthrough/` to the target repo's `.gitignore` first. Set `WALKTHROUGH_PROJECT` to the output directory. The tools refuse output that git tracks or does not ignore. Never commit generated media or browser session files.

## Plan and capture

For app videos, read [capture](references/capture.md). Explore the real flow before writing selectors. Configure the running app URL and any project-specific login/fixture hook in `walkthrough.json`. Use synthetic data. Do not rebuild a product UI to illustrate a claim.

For code videos, read [code walkthroughs](references/code.md). Select real git refs and the smallest readable regions that explain the cause and fix. Do not invent source code or test results.

Write `video.json` and `scenes/main.mjs`. Read [script format](references/script.md). Each spoken line needs a visible action or result. Match labels on the screen. Keep static framing unless a measured readability problem justifies a [camera move](references/motion-rules.md).

Choose narration with the user request in mind. Local speech needs no API key. ElevenLabs needs an exported key and incurs costs. Read [narration](references/narration.md). Run `narrate --provider <provider> --dry-run` before synthesis. Keep the default character budget unless the user authorizes a higher one. Do not silently switch narration providers after an error.

Generate narration before capture. Capture holds each beat for its line. Use `capture` and then `review --footage`. Inspect the generated sheets. Fix clipped pages, stale content, unwanted overlays, and actions that outlast their narration. Do not hide product errors to make a take pass.

## Render and review

Run `build`, then `render --stills`. Inspect the stills before the full render. Fix each error and warning. Use `build --allow-warnings` only after checking the warning and recording why it is acceptable. Read [rendering and review](references/rendering.md).

Run `render`, then `review <absolute-mp4-path>`. Inspect the contact sheet and relevant frames at full size. Listen to the narration when audio playback is available. State when it was not checked. Media checks do not prove that the product claims are correct.

If a recording step fails twice for the same reason, stop that step and report the blocker with the project path. Preserve the source changes and useful local artifacts. Do not keep making paid narration requests to repair capture problems.

## Deliver

Return the MP4 path, its length, caption/transcript paths, and the review result. Report paid narration use and any checks not performed. Keep files local unless the user requested publishing or the active shipping workflow authorizes it. See [publishing](references/publishing.md) for upload configuration and a PR section pattern.

When the product changes after recording, repeat the affected narration/capture and render so the video reflects the final change.
