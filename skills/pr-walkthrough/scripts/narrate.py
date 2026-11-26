#!/usr/bin/env python3
"""Render the narration lines of video.json with ElevenLabs. One request for each line.

usage: narrate.py [--project <dir>] [--dry-run] [line_id ...]

Audio is cached by a hash of the full request: text, neighbor lines, voice, model, settings, seed, and pronunciation
dictionaries. A line is rendered again only when one of those changes.
The saved character alignment flags pauses of 0.6 s or more inside a phrase with PAUSE warnings.
The cache directory is $WALKTHROUGH_CACHE (default ~/.cache/pr-walkthrough). It can be shared between projects.
Each paid request is written to <cache>/ledger.jsonl with its project. The script stops before one project passes
$WALKTHROUGH_TTS_BUDGET characters (default 6000). Ask the user before you raise the budget.
"""
import array, base64, fcntl, hashlib, json, os, shutil, subprocess, sys, time
from pathlib import Path
sys.dont_write_bytecode = True  # no __pycache__ in the repository
from common import args_with_project, call, duration, load_video, narration_pauses

DEFAULT_VOICE = {
    'id': 'TX3LPaxmHKxFdv7VOQHJ',  # Liam
    'model': 'eleven_multilingual_v2',
    'settings': {'stability': 0.5, 'similarity_boost': 0.75, 'style': 0.0, 'use_speaker_boost': True, 'speed': 1.0},
}
CACHE = os.path.expanduser(os.environ.get('WALKTHROUGH_CACHE', '~/.cache/pr-walkthrough'))
BUDGET = int(os.environ.get('WALKTHROUGH_TTS_BUDGET', '6000'))
LEDGER = os.path.join(CACHE, 'ledger.jsonl')


PROJECT = None


def spent(everything=False):
    if not os.path.exists(LEDGER):
        return 0
    rows = [json.loads(l) for l in open(LEDGER) if l.strip()]
    return sum(r['chars'] for r in rows if everything or r.get('project') == PROJECT)


def pace(voice, add=None):
    """Measured words per minute of a voice, from the lines rendered before. `add` records (words, seconds)."""
    path = os.path.join(CACHE, 'pace.json')
    data = json.load(open(path)) if os.path.exists(path) else {}
    key = f"{voice['id']}|{voice['model']}|{voice['settings'].get('speed', 1.0)}"
    if add:
        words, seconds = data.get(key, [0, 0.0])
        data[key] = [words + add[0], round(seconds + add[1], 3)]
        os.makedirs(CACHE, exist_ok=True)
        json.dump(data, open(path, 'w'), indent=1)
    words, seconds = data.get(key, [0, 0.0])
    return (words / seconds * 60, True) if seconds > 20 else (160.0, False)  # 160 is the measured pace of the default voice


def request_body(voice, text, prev, nxt):
    """The synthesis request for one line. The cache key and the API call both use it."""
    body = {'text': text, 'model_id': voice['model'], 'voice_settings': voice['settings'], 'seed': voice.get('seed', 6754)}
    if voice.get('pronunciation_dictionary_locators'):
        body['pronunciation_dictionary_locators'] = voice['pronunciation_dictionary_locators']
    # The neighbor lines keep the prosody continuous across separate requests.
    if prev: body['previous_text'] = prev
    if nxt: body['next_text'] = nxt
    return body


def cache_key(voice, body):
    return hashlib.sha1(json.dumps([voice['id'], body], sort_keys=True).encode()).hexdigest()[:16]


def render(voice, body, out_mp3, out_json):
    text = body['text']
    with open(LEDGER, 'a') as ledger:
        ledger.write(json.dumps({'at': time.strftime('%Y-%m-%dT%H:%M:%S'), 'chars': len(text), 'project': PROJECT, 'status': 'attempted', 'voice': voice['id'], 'model': voice['model']}) + '\n')
    raw, headers = call('POST', f"/v1/text-to-speech/{voice['id']}/with-timestamps?output_format=mp3_44100_128", body)
    data = json.loads(raw)
    json.dump(data.get('alignment') or data.get('normalized_alignment') or {}, open(out_json, 'w'))
    # Write then rename, so a stopped run does not leave a partial file that looks like a cache hit.
    open(out_mp3 + '.part', 'wb').write(base64.b64decode(data['audio_base64']))
    os.replace(out_mp3 + '.part', out_mp3)
    with open(LEDGER, 'a') as f:
        # The budget counts characters sent. The header gives the credits that the account was charged.
        credits = headers.get('character-cost') or headers.get('Character-Cost')
        f.write(json.dumps({'at': time.strftime('%Y-%m-%dT%H:%M:%S'), 'chars': 0, 'credits': int(credits) if credits else None, 'project': PROJECT, 'voice': voice['id'], 'model': voice['model'], 'text': text[:40]}) + '\n')


def spoken(text, say):
    """Respells terms that the voice reads wrong. video.json: "say": {"CNAME": "C name"}. The captions keep the written text."""
    for written, sound in (say or {}).items():
        text = text.replace(written, sound)
    return text


def clean(mp3, wav):
    """Writes the line as 48 kHz WAV without edge noise. Returns what it did.

    A line that is rendered with its neighbor text can end with a short burst of the next sound, cut off at the file
    end, or start in the middle of a sound. Each is a pop in the mix. Cut a truncated burst that follows silence,
    then fade the two edges.
    """
    rate, win, quiet = 48000, 240, 200          # 5 ms windows; 200 of 32768 is about -44 dBFS
    raw = subprocess.run(['ffmpeg', '-loglevel', 'error', '-i', mp3, '-ac', '1', '-ar', str(rate), '-f', 's16le', '-'], capture_output=True, check=True).stdout
    a = array.array('h'); a.frombytes(raw)
    peaks = [max(abs(x) for x in a[i:i + win]) for i in range(0, len(a) - win, win)]
    did = []
    # Tail: sound at the last sample (cut off), with 40 ms or more of silence less than 300 ms before the end.
    if peaks and peaks[-1] >= quiet:
        k = len(peaks) - 1
        while k > 0 and peaks[k] >= quiet and len(peaks) - k <= 60: k -= 1
        run = 0
        while k - run > 0 and peaks[k - run] < quiet: run += 1
        if run >= 8 and len(peaks) - k <= 60:
            a = a[:(k - run + min(run, 12)) * win]
            did.append(f'cut a {(len(peaks) - k) * 5} ms burst and {(run - min(run, 12)) * 5} ms of silence from the end')
    fade_in, fade_out = int(0.008 * rate), int(0.03 * rate)
    for i in range(min(fade_in, len(a))): a[i] = int(a[i] * i / fade_in)
    for i in range(min(fade_out, len(a))): a[-1 - i] = int(a[-1 - i] * i / fade_out)
    a.extend([0] * int(0.05 * rate))
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 's16le', '-ar', str(rate), '-ac', '1', '-i', '-', wav], input=a.tobytes(), check=True)
    return ', '.join(did)


def cached(voice, text, prev='', nxt='', dry=False):
    """Returns (mp3, alignment json, was_rendered). Renders on a cache miss."""
    os.makedirs(os.path.join(CACHE, 'tts'), exist_ok=True)
    body = request_body(voice, text, prev, nxt)
    base = os.path.join(CACHE, 'tts', cache_key(voice, body))
    mp3, meta = base + '.mp3', base + '.json'
    if os.path.exists(mp3) and os.path.exists(meta):
        return mp3, meta, False
    if dry:
        return None, None, True
    if spent() + len(text) > BUDGET:
        raise SystemExit(f'Budget stop: {spent()} characters are spent and this line needs {len(text)}. The budget is {BUDGET}. Ask the user before you raise WALKTHROUGH_TTS_BUDGET.')
    render(voice, body, mp3, meta)
    return mp3, meta, True


def main():
    global PROJECT
    project, rest = args_with_project(sys.argv[1:])
    PROJECT = project
    dry = '--dry-run' in rest
    if '--provider' in rest and rest.index('--provider') + 1 >= len(rest):
        raise SystemExit('--provider needs elevenlabs, local, or silent.')
    provider = rest[rest.index('--provider') + 1] if '--provider' in rest else 'elevenlabs'
    if '--provider' in rest:
        i = rest.index('--provider'); del rest[i:i + 2]
    if provider not in ('elevenlabs', 'local', 'silent'):
        raise SystemExit('Provider must be elevenlabs, local, or silent.')
    video = load_video(project)
    voice = {**DEFAULT_VOICE, **video.get('voice', {})}
    voice['settings'] = {**DEFAULT_VOICE['settings'], **video.get('voice', {}).get('settings', {})}

    only = {a for a in rest if not a.startswith('--')}
    lines = [l for l in video['lines'] if l.get('text')]
    outdir = os.path.join(project, 'audio', 'vo'); os.makedirs(outdir, exist_ok=True)
    manifest, need, pause_count = {}, 0, 0
    for i, l in enumerate(lines):
        if only and l['id'] not in only:
            continue
        prev = lines[i - 1]['text'] if i else ''
        nxt = lines[i + 1]['text'] if i + 1 < len(lines) else ''
        say = video.get('say')
        if provider != 'elevenlabs':
            from local_audio import make_line
            row = make_line(project, l, provider, spoken(l['text'], say), dry)
            if row: manifest[l['id']] = row
            print(f"{l['id']:<12} {provider} {'estimate only' if dry else str(row['duration']) + ' s'}")
            continue
        os.makedirs(CACHE, exist_ok=True)
        with open(os.path.join(CACHE, 'narration.lock'), 'a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            mp3, meta, new = cached(voice, spoken(l['text'], say), spoken(prev, say), spoken(nxt, say), dry)
        if dry:
            need += len(spoken(l['text'], say)) if new else 0
            print(f"{l['id']:<12} {len(l['text']):>4} chars  {'TO RENDER' if new else 'cached'}")
            continue
        wav = os.path.join(outdir, l['id'] + '.wav')
        cleaned = clean(mp3, wav)
        Path(outdir, l['id'] + '.local.json').unlink(missing_ok=True)
        shutil.copy(meta, os.path.join(outdir, l['id'] + '.alignment.json'))
        for seconds, text_before in narration_pauses(json.load(open(meta))):
            pause_count += 1
            print(f'PAUSE {l["id"]}  {seconds:.2f} s after "{text_before}". The voice may read a label as two sentences. Add a lowercase "say" respelling of the label, or put a noun after it, then run narrate.py for this line.')
        d = round(duration(wav), 3)
        if new:
            pace(voice, (len(l['text'].split()), d))
        manifest[l['id']] = {'text': l['text'], 'spoken': spoken(l['text'], say), 'duration': d, 'chars': len(l['text']), 'rendered': new, 'provider': provider}
        print(f"{l['id']:<12} {d:>6.2f} s  {len(l['text']):>4} chars  {'rendered' if new else 'cached'}{'  (' + cleaned + ')' if cleaned else ''}", flush=True)
    if dry:
        words = sum(len(l['text'].split()) for l in lines)
        # Each line adds 0.5 s of lead and breath to the speech time.
        wpm, measured = pace(voice)
        print(f'{need} paid characters to render. {spent()} of {BUDGET} are spent. Provider: {provider}.')
        print(f'{words} words in {len(lines)} lines. Estimated video length: {words / wpm * 60 + 0.5 * len(lines):.0f} s (before any silent card or long action).')
        print(f"The estimate uses {wpm:.0f} words per minute for this voice ({'measured from earlier lines' if measured else 'not measured yet; render 2 or 3 lines, then run --dry-run again'}).")
        return
    path = os.path.join(outdir, 'manifest.json')
    old = json.load(open(path)) if os.path.exists(path) and only else {}
    old.update(manifest)
    ids = [l['id'] for l in lines]
    old = {k: old[k] for k in ids if k in old}
    json.dump(old, open(path, 'w'), indent=1)
    total = sum(v['duration'] for v in old.values())
    chars = sum(v['chars'] for v in old.values())
    words = sum(len(v['text'].split()) for v in old.values())
    print(f'narration {total:.1f} s over {len(old)} lines, {chars} characters, {words} words (the voice speaks at {words / total * 60:.0f} words per minute)')
    # Each line adds 0.5 s of lead and breath in the edit. A silent card adds its own time.
    print(f'estimated video length: {total + 0.5 * len(old):.0f} s. Check it against the preset. Change the words, not the voice speed.')
    print(f'this project spent {spent()} of {BUDGET} budget characters. All projects: {spent(True)} (ledger: {LEDGER})')

    if pause_count:
        print(f'{pause_count} PAUSE warning(s). Fix each one, or accept it and list it in the delivery report.')


if __name__ == '__main__':
    main()
