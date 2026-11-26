# Narration and cost

`narrate --provider local` uses macOS `say` or Linux `espeak-ng`/`espeak`. There is no API call. `narrate --provider silent` makes silent WAV files and timed caption files after `build`. `duration` on a line overrides its estimated length in silent mode.

For ElevenLabs:

```bash
export ELEVENLABS_API_KEY='your-key'
node "$SKILL/scripts/cli.mjs" narrate --provider elevenlabs --dry-run
node "$SKILL/scripts/cli.mjs" narrate --provider elevenlabs
```

Credentials come only from the process environment. The scripts do not read another checkout's `.env` or shell startup files. A missing or rejected key stops the command. There is no automatic fallback to another provider.

The default voice is Liam (`TX3LPaxmHKxFdv7VOQHJ`) with `eleven_multilingual_v2`. Set `voice.id`, `voice.model`, optional `voice.settings`, and `voice.seed` in `video.json`. Voice access depends on your ElevenLabs account. If that voice is unavailable, choose a voice from your account. The API returns audio and character alignment through its [speech-with-timing endpoint](https://elevenlabs.io/docs/api-reference/text-to-speech/convert-with-timestamps).

Cache: `~/.cache/pr-walkthrough/tts`, or `WALKTHROUGH_CACHE`. The key includes voice, model, settings, seed, pronunciation dictionaries, spoken text, and neighboring lines. Editing a line can regenerate its neighbors. Repeating an unchanged request uses the cache.

Budget: 6,000 characters per project path, set by `WALKTHROUGH_TTS_BUDGET`. The append-only `ledger.jsonl` records attempted paid synthesis and any returned character-cost header. The budget limits characters, not dollars; provider prices and account terms vary. Paid cache checks and budget reservations are serialized with a local file lock. Moving a project changes its budget identity. A provider request may incur cost even if the connection fails before receiving audio.

`--dry-run` does not synthesize or require a key. It estimates uncached paid characters and runtime. It can create the cache directory. A line id after the options regenerates only that line; changing script context can also invalidate adjacent lines, so rerun the full command before final capture.

ElevenLabs lines are converted to 48 kHz mono WAV, trimmed for small cut-off sounds, and faded at the edges. Local speech uses the system voice and is intended for accessible setup and iteration; it will sound different from ElevenLabs. Long spaces in provider alignment produce `PAUSE` warnings. Fix a bad reading with a `say` respelling or reword the sentence.

The final renderer mixes narration to the timeline length, preserves silence between lines, and applies two-pass loudness normalization to -16 LUFS with a -1.5 dBTP target. Silent previews skip speech loudness checks.
