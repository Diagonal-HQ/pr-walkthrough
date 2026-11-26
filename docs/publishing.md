# Public release

PR Video Walkthrough is public at [Diagonal-HQ/pr-walkthrough](https://github.com/Diagonal-HQ/pr-walkthrough) under the MIT license.

## Install the skill

```bash
npx skills add Diagonal-HQ/pr-walkthrough --skill pr-walkthrough
```

Install runtime dependencies from the installed skill directory:

```bash
npm ci --workspaces=false
npx playwright install chromium
```

You can also clone the public repository and copy the complete skill directory. It is self-contained. No runtime file depends on the original Diagonal checkout. Credits link to the original team and changes; links to the original Diagonal repository require access to that separate repository.

## Release updates

Keep the README, MIT license, and contributor credits current. Run the local checks for changed areas before pushing. Keep generated videos, credentials, browser sessions, logs, and node_modules out of git.

CI keeps a rendered demo as a workflow artifact for validation. Use a stable public media URL for a launch post; CI artifacts are not permanent public hosting. Making this source repository public does not upload or publish locally generated videos.

## Suggested launch post

> Our coding agents make narrated walkthrough videos for PRs.
>
> They drive the real app, generate voiceover, and assemble a demo. Backend changes get a before/after code walkthrough.
>
> We extracted the workflow into a skill for your own project. It includes a local demo with no API key: https://github.com/Diagonal-HQ/pr-walkthrough

Adjust the post to match the released features and chosen example.
