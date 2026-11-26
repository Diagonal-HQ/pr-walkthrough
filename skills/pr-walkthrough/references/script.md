# Script format

`video.json` owns the brief and spoken lines:

```json
{
  "title": "Saved views",
  "preset": "feature-clip",
  "audience": "The engineer reviewing this change",
  "message": "A filtered task list can be saved with a name.",
  "voice": {"id": "TX3LPaxmHKxFdv7VOQHJ", "model": "eleven_multilingual_v2"},
  "say": {"SSO": "S S O"},
  "lines": [
    {"id":"title","on":"title","heading":"Saved views","text":"Keep the work you need one click away."},
    {"id":"open","text":"Open the task list and select Open only."},
    {"id":"result","text":"The list shows only open tasks."},
    {"id":"end","on":"end","heading":"A view for the work","text":"The saved view is ready."}
  ]
}
```

This short excerpt explains the schema; it needs more narration to meet the preset length. The complete runnable example is in `examples/saved-views/`.

Line ids must be unique and contain only letters, digits, underscores, or hyphens. The default `on` is `capture`. A captured line needs a matching scene beat. `title`, `section`, and `end` make cards instead. Each card needs a `heading`; `sub` is optional. Omit `text` for a silent card. `duration` optionally sets a spoken line's duration in silent preview mode only.

| Preset | Target length | Structure |
| --- | --- | --- |
| `feature-clip` | 30–90 s | Result, real flow, final result |
| `code-walkthrough` | 30–120 s | Failure, before code, fix, after code, evidence |
| `product-walkthrough` | 120–240 s | Orientation, chapters with section cards, recap |

Aim for 130–160 words per finished minute. `narrate --dry-run` estimates runtime; the actual voice can differ. `build` flags out-of-range runtime and pace. One line should usually be one or two short sentences and one visible action or result. Typing needs enough narration to cover it.

Use the real screen labels. Describe only behavior you observed. A title should tell the reviewer why the change matters. An end card states the result. Avoid filler, spinners, and toast messages that disappear before the line ends.

The edit writes separate `.srt` and `.vtt` captions. Caption chunks use character timing when available, or distribute the line duration by text length. Pronunciation respellings affect speech, while captions keep the original text. Music and burned-in captions are not supported in this version.

See [motion rules](motion-rules.md) before adding `move`. Zero camera moves is a valid result.

Set `brand: {"name": "YOUR PROJECT"}` at the top level to replace the neutral wordmark on title and end cards. Plain text is escaped before rendering.
