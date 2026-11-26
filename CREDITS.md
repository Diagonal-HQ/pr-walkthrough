# Credits

PR Walkthrough grew out of the engineering workflow at [Diagonal](https://github.com/Diagonal-HQ). This standalone repository builds on the team's original recording, narration, editing, and review tools.

Special thanks to **[Craig Paul (@craigpaul)](https://github.com/craigpaul)**, who added the original walkthrough skill and its product video pipeline. His work established the script, narration-driven capture, rendering, captions, motion rules, and quality review. He later added narration pause checks and simplified the audio workflow.

Thanks also to:

- **[Owen Conti (@owenconti)](https://github.com/owenconti)** for the PR media upload workflow, the move to Cloudflare R2, and workflow reliability fixes.
- **[Lucas (@harrisonlucaswork)](https://github.com/harrisonlucaswork)** for adding the before-and-after code walkthrough mode for changes without a visible UI.
- **The Diagonal engineering team** for using and improving the PR video workflow.

This repository adapts that work into a portable skill with project-specific setup hooks, direct Playwright capture, optional local narration, and optional publishing.

## Original work

These links point to the original Diagonal repository and require access to it.

- Craig: [Add the walkthrough skill for narrated product and feature videos](https://github.com/Diagonal-HQ/diagonal/pull/6508).
- Craig: [Replace walkthrough music and transcription with pause checks](https://github.com/Diagonal-HQ/diagonal/pull/7046).
- Owen: [Upload PR media to Cloudflare R2](https://github.com/Diagonal-HQ/diagonal/pull/4529) and [upload walkthrough videos only to R2](https://github.com/Diagonal-HQ/diagonal/pull/7091).
- Lucas: [Record a code walkthrough video for a change with no UI](https://github.com/Diagonal-HQ/diagonal/pull/7123).

These contribution descriptions come from the original git history. They identify the work this package builds on, rather than claiming to list every contributor.
