#!/usr/bin/env python3
"""Builds <project>/timeline.json for the edit (render.py) from video.json, the narration manifest, and the footage.

usage: build_timeline.py [--project <dir>] [--allow-warnings]

The narration drives the timeline. The director already held each beat for the length of its line, so each clip plays
at normal speed. The camera is static unless a line has a `move` with a `reason`. The script refuses a move that
breaks the motion rules in references/motion-rules.md. It also writes the captions, the script with timings, and a
motion report for the quality review.
"""
import glob, json, os, re, sys
sys.dont_write_bytecode = True  # no __pycache__ in the repository
from common import args_with_project, load_video, source_fingerprint

FPS = 30
W, H = 1920, 1080
VO_LEAD = 0.15       # silence before each line
TAIL = 0.35          # breath after each line. The director holds each beat for the same time.
CAPTION_CHARS = 64

PRESETS = {
    # seconds: accepted length. moves_per_min: upper limit of camera moves and highlights.
    'feature-clip': dict(seconds=(30, 90), moves_per_min=3),
    'product-walkthrough': dict(seconds=(120, 240), moves_per_min=4),
    'code-walkthrough': dict(seconds=(30, 120), moves_per_min=3),
}
# Motion limits. references/motion-rules.md gives the reason for each value.
SCALE = (1.2, 1.6)      # the footage is 1.5x the output size, so this range stays sharp
SETTLE = 0.5         # the frame is static for this time before a move starts
MOVE_IN = 0.8
MOVE_OUT = 0.6
MIN_HOLD = 2.0       # time at full zoom
MIN_GAP = 4.0        # static time between two moves
FIRST_MOVE = 5.0     # no move before this time
MAX_MOTION_SHARE = 0.10
MAX_FILL = 0.88      # the target covers at most this share of the frame at full zoom
MIN_REASON = 25

errors, warnings = [], []


def chunks(text):
    """Caption-sized pieces. One piece for each sentence. A long sentence is cut into parts of near-equal length."""
    out = []
    for sentence in [p.strip() for p in re.split(r'(?<=[.?!])\s+', text) if p.strip()]:
        parts = -(-len(sentence) // CAPTION_CHARS)
        goal = len(sentence) / parts
        part = ''
        for word in sentence.split():
            longer = (part + ' ' + word).strip()
            # Close the part when the next word takes it farther from the goal length.
            if part and (len(longer) > CAPTION_CHARS or abs(len(longer) - goal) > abs(len(part) - goal) and len(part) >= goal * 0.6):
                out.append(part); part = word
            else:
                part = longer
        out.append(part)
    return out


def caption_times(project, line, pieces, vd):
    """Start and end of each caption inside the line, in seconds. Uses the character alignment when it matches the text."""
    path = os.path.join(project, 'audio', 'vo', line['id'] + '.alignment.json')
    al = json.load(open(path)) if os.path.exists(path) else {}
    starts, ends = al.get('character_start_times_seconds'), al.get('character_end_times_seconds')
    exact = starts and ''.join(al.get('characters', [])) == line['text']
    out, pos, total, acc = [], 0, sum(len(p) for p in pieces), 0
    for p in pieces:
        if exact:
            i = line['text'].find(p, pos); pos = i + len(p)
            out.append((starts[i], ends[pos - 1]))
        else:
            a = acc / total * vd; acc += len(p); out.append((a, acc / total * vd))
    # Each caption stays until the next one starts. The last one ends with the line: narrate.py can cut the end of
    # the audio, so an alignment time can be after the end of the line.
    return [(min(a, vd), min(out[i + 1][0], vd) if i + 1 < len(out) else vd) for i, (a, b) in enumerate(out)]


def stamp(sec, sep=','):
    ms = round(sec * 1000)
    return f'{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d}{sep}{ms % 1000:03d}'


def main():
    project, rest = args_with_project(sys.argv[1:])
    video = load_video(project)
    preset = PRESETS.get(video.get('preset'))
    if not preset:
        raise SystemExit(f"video.json: preset must be one of {', '.join(PRESETS)}")
    if video.get('burn_captions'):
        raise SystemExit('video.json: burn_captions is not supported. The edit writes out/captions.srt and out/captions.vtt.')
    if any(video.get(k) is not None for k in ('music', 'music_bed', 'music_open')):
        raise SystemExit('video.json: music is not supported. Remove music, music_bed, and music_open.')
    vo_path = os.path.join(project, 'audio', 'vo', 'manifest.json')
    if not os.path.exists(vo_path):
        raise SystemExit('No narration. Run narrate.py first.')
    vo = json.load(open(vo_path))

    beats, targets = {}, {}
    for path in sorted(glob.glob(os.path.join(project, 'footage', '*.json'))):
        meta = json.load(open(path))
        k = W / meta['viewport']['width']
        for b in meta.get('beats', []):
            if b['id'] in beats:
                raise SystemExit(f"Duplicate footage beat: {b['id']}. Remove the obsolete clip metadata.")
            beats[b['id']] = dict(b, clip=meta['name'])
        for name, r in meta.get('targets', {}).items():
            targets[name] = dict(x=r['x'] * k, y=r['y'] * k, w=r['w'] * k, h=r['h'] * k, t=r.get('t', 0), clip=meta['name'])

    t, shots, vos, caps, moves, rows, pending = 0, [], [], [], [], [], []
    for line in video['lines']:
        lid, on = line['id'], line.get('on', 'capture')
        text = line.get('text')
        if text and lid not in vo:
            errors.append(f'{lid}: no audio. Run narrate.py.'); continue
        if text and vo[lid]['text'] != text:
            errors.append(f'{lid}: the text changed after narration. Run narrate.py again.')
        vd = vo[lid]['duration'] if text else 0
        if on in ('title', 'section', 'end'):
            card = video.get('cards', {}).get(lid if on == 'section' else on, {})
            heading = line.get('heading') or card.get('heading')
            if not heading:
                errors.append(f'{lid}: the {on} card needs a heading'); continue
            length = max(vd + VO_LEAD + TAIL, {'title': 2.0, 'section': 1.5, 'end': 3.0}[on])
            shot = dict(type='card', kind=on, heading=heading, sub=line.get('sub') or card.get('sub'), line=lid)
            if line.get('move'):
                errors.append(f'{lid}: a card cannot have a move')
        else:
            b = beats.get(lid)
            if not b:
                errors.append(f'{lid}: no footage beat. Film it with d.beat("{lid}", ...) or set "on" to a card.'); continue
            length = b['b'] - b['a']
            over = length - (vd + VO_LEAD + TAIL)
            if over > 1.5:
                warnings.append(f'{lid}: the footage is {over:.1f} s longer than the line. Shorten the action, or give the narrator more to say.')
            if over < -0.25:
                errors.append(f'{lid}: the footage is {-over:.1f} s shorter than the line. Film the beat again after narrate.py.')
            shot = dict(type='clip', clip=b['clip'], a=round(b['a'], 3), rate=1, line=lid)
        frames = round(length * FPS)
        shot.update(start=t, frames=frames)
        shots.append(shot)
        if text:
            vs = t + round(VO_LEAD * FPS)
            vos.append(dict(id=lid, start=vs, frames=round(vd * FPS)))
            pieces = chunks(text)
            for p, (a, b_) in zip(pieces, caption_times(project, line, pieces, vd)):
                # Round the end, not the length, so that a caption ends on the frame where the next one starts.
                caps.append(dict(text=p, start=vs + round(a * FPS), frames=max(round(b_ * FPS) - round(a * FPS), 1)))
        rows.append((t / FPS, lid, on, text or f"[{on} card: {shot.get('heading', '')}]"))
        if line.get('move'):
            pending.append((line, shot))
        t += frames
    total = t / FPS
    by_line = {s['line']: s for s in shots}

    for line, shot in pending:
        m, lid = line['move'], line['id']
        reason = (m.get('reason') or '').strip()
        if len(reason) < MIN_REASON:
            errors.append(f'{lid}: the move has no stated reason (at least {MIN_REASON} characters). Remove the move or state why the viewer needs it.'); continue
        if m.get('type') not in ('zoom', 'highlight'):
            errors.append(f'{lid}: move type must be zoom or highlight'); continue
        tg = targets.get(m.get('target'))
        if not tg:
            errors.append(f'{lid}: the move target "{m.get("target")}" is not in the footage. Record it with d.target("{m.get("target")}", find).'); continue
        last = by_line.get(m.get('until', lid))
        if not last or last['type'] != 'clip' or last.get('clip') != shot.get('clip') or tg['clip'] != shot.get('clip') or last['start'] < shot['start']:
            errors.append(f'{lid}: a move must start and end in the same clip as its target'); continue
        span = [s for s in shots if shot['start'] <= s['start'] <= last['start']]
        if any(s['type'] != 'clip' or s['clip'] != shot['clip'] for s in span):
            errors.append(f'{lid}: a move cannot continue through a card or a different clip'); continue
        # The move starts after the target is on the screen, and after the frame was static for the settle time.
        seen = shot['start'] + round((tg['t'] - shot['a']) * FPS)
        if not shot['start'] <= seen <= last['start'] + last['frames']:
            errors.append(f'{lid}: the target "{m["target"]}" was recorded outside the lines of this move. Record it in the beat where the move starts.'); continue
        start = max(shot['start'] + round(max(m.get('at', SETTLE), SETTLE) * FPS), seen + round(0.2 * FPS))
        end = last['start'] + last['frames']
        cut = m.get('release') == 'cut'
        mv = dict(type=m['type'], line=lid, reason=reason, start=start)
        if m['type'] == 'zoom':
            scale = m.get('scale', 1.35)
            if not SCALE[0] <= scale <= SCALE[1]:
                errors.append(f'{lid}: zoom scale {scale} is outside {SCALE[0]} to {SCALE[1]}'); continue
            pad = 24
            fill = max((tg['w'] + pad) * scale / W, (tg['h'] + pad) * scale / H)
            if fill > MAX_FILL:
                errors.append(f'{lid}: the target fills {fill:.0%} of the frame at scale {scale}. Use a smaller scale or no zoom.'); continue
            mv.update(x=round(tg['x'] + tg['w'] / 2), y=round(tg['y'] + tg['h'] / 2), scale=scale, inFrames=round(MOVE_IN * FPS), outFrames=0 if cut else round(MOVE_OUT * FPS))
        else:
            mv.update(rect=dict(x=round(tg['x'] - 8), y=round(tg['y'] - 8), w=round(tg['w'] + 16), h=round(tg['h'] + 16)), inFrames=round(0.3 * FPS), outFrames=0 if cut else round(0.3 * FPS))
        mv['outStart'] = end - mv['outFrames'] - (0 if cut else round(0.15 * FPS))
        hold = (mv['outStart'] - mv['start'] - mv['inFrames']) / FPS
        if hold < MIN_HOLD:
            errors.append(f'{lid}: the move holds for {hold:.1f} s. The minimum is {MIN_HOLD} s. Extend it with "until", or remove it.'); continue
        moves.append(mv)

    moves.sort(key=lambda m: m['start'])
    if moves and moves[0]['start'] / FPS < FIRST_MOVE:
        errors.append(f"{moves[0]['line']}: a move starts at {moves[0]['start'] / FPS:.1f} s. Show the full frame for the first {FIRST_MOVE:.0f} s.")
    for a, b in zip(moves, moves[1:]):
        gap = (b['start'] - (a['outStart'] + a['outFrames'])) / FPS
        if gap < MIN_GAP:
            errors.append(f"{a['line']} and {b['line']}: {gap:.1f} s between two moves. The minimum is {MIN_GAP} s. Remove one move.")
    in_motion = sum(m['inFrames'] + m['outFrames'] for m in moves if m['type'] == 'zoom') / FPS
    limit = max(1, round(preset['moves_per_min'] * total / 60))
    if len(moves) > limit:
        errors.append(f"{len(moves)} moves in {total:.0f} s. The {video['preset']} preset permits {limit}. Remove the moves with the weakest reasons.")
    if total and in_motion / total > MAX_MOTION_SHARE:
        errors.append(f'The camera moves for {in_motion / total:.0%} of the runtime. The limit is {MAX_MOTION_SHARE:.0%}.')
    lo, hi = preset['seconds']
    if not lo <= total <= hi:
        warnings.append(f"The video is {total:.1f} s. The {video['preset']} preset is {lo} to {hi} s.")
    words = sum(len(v['text'].split()) for v in vo.values()); speech = sum(v['duration'] for v in vo.values())
    pace = words / total * 60 if total else 0
    if not 110 <= pace <= 175:
        warnings.append(f'The video has {pace:.0f} words per finished minute. The range is 110 to 175. ' + ('Cut words or add screen time.' if pace > 175 else 'There is too much silence. Add narration or shorten the actions.'))
    for a, b in zip(shots, shots[1:]):
        if a['type'] == b['type'] == 'clip' and a['clip'] == b['clip'] and abs(a['a'] + a['frames'] / FPS - b['a']) > 0.2:
            warnings.append(f"{a['line']} to {b['line']}: {b['a'] - a['a'] - a['frames'] / FPS:.1f} s of clip {a['clip']} is cut out between these lines. Check the cut for a visible jump.")

    for w in warnings: print('WARN ', w)
    for e in errors: print('ERROR', e)
    if errors or (warnings and '--allow-warnings' not in rest):
        raise SystemExit(f'{len(errors)} error(s), {len(warnings)} warning(s). Fix each one. Use --allow-warnings only for a warning that you checked and accept.')

    timeline = dict(source_fingerprint=source_fingerprint(project), fps=FPS, frames=t, width=W, height=H, shots=shots, moves=moves, vos=vos, captions=caps)
    json.dump(timeline, open(os.path.join(project, 'timeline.json'), 'w'), indent=1)

    out = os.path.join(project, 'out'); os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, 'captions.srt'), 'w') as srt, open(os.path.join(out, 'captions.vtt'), 'w') as vtt:
        vtt.write('WEBVTT\n\n')
        for i, c in enumerate(caps, 1):
            a, b = c['start'] / FPS, (c['start'] + c['frames']) / FPS
            srt.write(f"{i}\n{stamp(a)} --> {stamp(b)}\n{c['text']}\n\n")
            vtt.write(f"{stamp(a, '.')} --> {stamp(b, '.')}\n{c['text']}\n\n")
    with open(os.path.join(out, 'script-with-timings.md'), 'w') as f:
        f.write(f"# {video.get('title', 'Walkthrough')}: script with timings\n\nPreset: {video['preset']}. Total {int(total // 60)}:{total % 60:04.1f}. Narration {speech:.1f} s, {words} words, {pace:.0f} words per finished minute.\n\n")
        for sec, lid, on, text in rows:
            f.write(f'- {int(sec // 60)}:{sec % 60:04.1f}  `{lid}`  {text}\n')
        f.write('\n## Camera moves\n\n')
        if not moves: f.write('None. Each shot is a static full frame.\n')
        for m in moves:
            f.write(f"- {m['start'] / FPS:.1f} s to {(m['outStart'] + m['outFrames']) / FPS:.1f} s  {m['type']}{' x' + str(m['scale']) if m['type'] == 'zoom' else ''}  (`{m['line']}`)  Reason: {m['reason']}\n")
    cuts = [s['start'] / FPS for s in shots]
    json.dump(dict(total=total, cuts=cuts, moves=[dict(line=m['line'], type=m['type'], start=m['start'] / FPS, full=(m['start'] + m['inFrames']) / FPS, end=(m['outStart'] + m['outFrames']) / FPS, reason=m['reason']) for m in moves]), open(os.path.join(project, 'review-points.json'), 'w'), indent=1)
    print(f"timeline: {total:.1f} s, {len(shots)} shots, {len(moves)} move(s), camera in motion {in_motion / total:.0%} of the runtime, {pace:.0f} words per finished minute")
    print(f'wrote {project}/timeline.json, out/captions.srt, out/captions.vtt, out/script-with-timings.md')


if __name__ == '__main__':
    main()
