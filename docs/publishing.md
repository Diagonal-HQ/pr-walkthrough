# Publish this repository

This repository is private at `Diagonal-HQ/pr-walkthrough`. A public release is a separate decision. The steps below describe that future release.

1. Review the MIT license and attribution.
2. Review the README and run the demo with a fresh dependency install.
3. Confirm the owner and name, then change visibility only when a public release is authorized.
4. Push source through your normal review process. Exclude generated media, credentials, local logs, and node_modules.
5. Link a chosen demo MP4 in the README using an approved public media host.
6. Add the public install command below to the README.

For a repository named `Diagonal-HQ/pr-walkthrough`:

```bash
npx skills add Diagonal-HQ/pr-walkthrough --skill pr-walkthrough
```

Install runtime dependencies from the installed skill directory:

```bash
npm ci --workspaces=false
npx playwright install chromium
```

Keep a copy/clone option for other agents. The complete skill directory is portable. No runtime file depends on the original Diagonal checkout. Credits link to the original team and changes.

CI keeps a rendered demo as a workflow artifact for validation. Use a stable public media URL for a launch post; CI artifacts are not permanent public hosting.

## Suggested launch post

> Our coding agents make narrated walkthrough videos for PRs.
>
> They drive the real app, generate voiceover, and assemble a demo. Backend changes get a before/after code walkthrough.
>
> We extracted the workflow into a skill for your own project. It includes a local demo with no API key: [repo link]

Adjust this to match the release. Keep the repository private until a public release is authorized. Creating the private repository does not publish any video.
