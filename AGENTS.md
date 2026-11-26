# Repository guidance

This repository packages PR Video Walkthrough and its pr-walkthrough skill. Keep its runtime, examples, and references self-contained in `skills/pr-walkthrough/`. A copied skill must work outside this checkout.

Use Node.js 22+, Python 3.10+, and FFmpeg. Python runtime scripts use the standard library. Use Playwright's bundled Chromium for capture. Keep root and standalone skill lockfiles in sync when changing dependencies.

Write all video projects, audio, frames, browser auth state, and logs inside ignored `.walkthrough/` output folders. Do not commit credentials or generated media. Use synthetic data for examples.

Keep publishing and paid narration explicit. Use local speech or mocks for verification unless the task authorizes paid API calls. Never silently change providers after a failure.

Run `npm run check` after changes. Run the specific test file command that covers a behavior change. Capture or rendering changes also need the demo and visual inspection of its review frames. Follow `CONTRIBUTING.md` for the development commands. Distinguish local checks from CI and live-provider checks in the handoff.
