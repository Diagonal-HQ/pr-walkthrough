# Contributing

Keep the skill self-contained under `skills/pr-walkthrough/`. A copied skill directory must work without files from this repository's root. Runtime dependencies belong in its `package.json`. Keep both lockfiles in sync when dependencies change.

The recording tools target macOS and Linux. Use Node.js 22+, Python 3.10+, and FFmpeg. Python code uses the standard library. Browser work uses Playwright's bundled Chromium. Reference APIs in the [Playwright documentation](https://playwright.dev/docs/api/class-browsercontext).

Use the scripts named in the README to check syntax, timeline behavior, audio mixing, narration caching, and project contracts. Run `npm run demo -- --project .walkthrough/<new-name>` when changing capture, rendering, or narration. Inspect its review sheet. Test paid providers with mocks unless a task explicitly authorizes paid calls.

Do not include generated media, auth state, or credentials in a contribution. Keep output in an ignored folder. Preserve failure signals: a failed recording or render must not be reported as a successful video.

Describe changes in terms of what the reviewer will see and how you checked it. Keep framework-specific app setup in project hooks. Do not add a framework dependency to the core recording pipeline.
