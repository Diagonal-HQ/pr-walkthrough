# Publishing and PR integration

Local output is the default. Publishing is a separate action. Use your project's authorized uploader if it has one. Do not commit media to git to obtain a URL.

## S3-compatible upload

The optional uploader uses the AWS CLI and its normal credential chain. Install and configure that CLI separately. It supports S3 and S3-compatible hosts such as R2. Set the project's `walkthrough.json`:

```json
{
  "publish": {
    "bucket": "my-pr-videos",
    "publicBaseUrl": "https://media.example.com",
    "prefix": "walkthroughs/my-change",
    "endpoint": "https://ACCOUNT_ID.r2.cloudflarestorage.com"
  }
}
```

Omit `endpoint` for S3. Do not put keys in this file. The bucket and public routing must already exist; upload creates neither. Each video gets a unique object name and must be at most 50 MB.

```bash
node "$SKILL/scripts/cli.mjs" upload --dry-run "$WALKTHROUGH_PROJECT/out/my-change.mp4"
# Only when publishing is requested or authorized:
node "$SKILL/scripts/cli.mjs" upload "$WALKTHROUGH_PROJECT/out/my-change.mp4"
```

Upload checks the public URL with HEAD. An object can exist even if that check fails. Repair public routing before linking it. Review footage first; the uploader does not scan video for sensitive information.

## PR description

`pr-section --url https://media.example.com/video.mp4` prints Markdown without calling GitHub. Adapt it:

```markdown
## Walkthrough

[Watch the 45-second walkthrough](https://media.example.com/video.mp4)

Shows the filter, save dialog, and final saved view.
```

An externally hosted video is a link. Do not promise an inline GitHub player. GitHub-hosted attachments use your normal attachment process, outside this tool.

## Shipping workflow snippet

Add this to your shipping skill or `AGENTS.md`:

```text
After validation, use pr-walkthrough to make a 30–90 second video for the reviewer.
Show real app behavior for visible changes. Use a code walkthrough otherwise.
Use local narration unless the task authorizes ElevenLabs.
Keep output in .walkthrough/<change>/.
If this workflow authorizes publication, use our PR asset uploader and link the
video near the top of the PR description. Otherwise return the local paths.
If capture fails twice, record the blocker and continue the existing PR workflow.
Re-record affected beats if a later change alters what the video shows.
```

Adapt failure behavior and publishing authority to your project. This skill does not authorize a push, PR creation, GitHub edits, or publication.
