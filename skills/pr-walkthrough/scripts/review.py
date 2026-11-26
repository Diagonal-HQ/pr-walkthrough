#!/usr/bin/env python3
"""Collects the evidence for a check: of the footage after a capture, or of the rendered video.

usage: review.py --footage [clip ...] [--project <dir>]        after each capture
       review.py <video.mp4> [--project <dir>]   after the render

--footage lists each beat, marks a beat whose action is longer than its line, and writes
<project>/review/footage/<clip>-<beat>-mid.png and -end.png, and sheets <project>/review/footage-<clip>-<n>.png
with 4 beats each (left: middle of the beat, right: end of the beat). The end frame shows what the next line starts on.

For a rendered video

it writes to <project>/review/:
  frames/cut-*.png     one frame 0.3 s after each cut, and one before the next cut
  frames/move-*.png    for each camera move: before, at full zoom, and after
  sheet.png            a contact sheet of all frames
  facts.md             format, loudness, the motion table, and still runs
Read each frame, then fill in the checklist in references/rendering.md.
"""
import glob, json, os, re, shutil, subprocess, sys
sys.dont_write_bytecode = True  # no __pycache__ in the repository
from common import args_with_project


def run(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode:
        raise SystemExit(f"{cmd[0]} failed: {result.stderr[-1500:]}")
    return result


def grab(video, sec, out):
    run(['ffmpeg', '-y', '-loglevel', 'error', '-ss', f'{max(sec, 0):.3f}', '-i', video, '-frames:v', '1', out])


def footage(project, rest):
    """After a capture: a frame from the middle and the end of each beat, and sheets of 4 beats."""
    clips = [a for a in rest if not a.startswith('--')] or [os.path.basename(p)[:-5] for p in sorted(glob.glob(os.path.join(project, 'footage', '*.json')))]
    out = os.path.join(project, 'review', 'footage'); os.makedirs(out, exist_ok=True)
    for clip in clips:
        meta = json.load(open(os.path.join(project, 'footage', clip + '.json')))
        video = os.path.join(project, 'footage', clip + '.mp4')
        tmp = os.path.join(out, '.' + clip); shutil.rmtree(tmp, ignore_errors=True); os.makedirs(tmp)
        n = 0
        for i, b in enumerate(meta['beats']):
            late = b['acted'] > b['narration'] + 0.35
            print(f"{clip}  {b['id']:<14} {b['a']:6.1f} to {b['b']:6.1f} s  action {b['acted']:.1f} s, line {b['narration']:.1f} s{'   LONGER THAN THE LINE' if late else ''}")
            for tag, sec in (('mid', (b['a'] + b['b']) / 2), ('end', b['b'] - 0.1)):
                png = os.path.join(out, f"{clip}-{b['id']}-{tag}.png")
                subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-ss', f'{sec:.3f}', '-i', video, '-frames:v', '1', '-vf', 'scale=1920:-1', png], check=True)
                shutil.copy(png, os.path.join(tmp, f"{i:03d}-{'a' if tag == 'mid' else 'b'}.png")); n += 1
        # 4 beats on one sheet, so that each sheet is readable when you open it.
        pattern = os.path.join(project, 'review', f'footage-{clip}-%d.png')
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-pattern_type', 'glob', '-i', os.path.join(tmp, '*.png'), '-vf', 'scale=960:-1,tile=2x4:padding=8:color=white', '-start_number', '1', pattern], check=True)
        shutil.rmtree(tmp)
        for page in range(1, -(-n // 8) + 1):
            first = (page - 1) * 4
            ids = ', '.join(b['id'] for b in meta['beats'][first:first + 4])
            print(f'sheet {pattern % page}  rows: {ids}  (left: middle of the beat, right: end of the beat)')



def main():
    project, rest = args_with_project(sys.argv[1:])
    if '--footage' in rest:
        return footage(project, [a for a in rest if a != '--footage'])
    files = [a for a in rest if not a.startswith('--')]
    if not files:
        raise SystemExit(__doc__)
    video = os.path.abspath(files[0])
    points = json.load(open(os.path.join(project, 'review-points.json')))
    frames = os.path.join(project, 'review', 'frames'); os.makedirs(frames, exist_ok=True)
    for f in os.listdir(frames): os.remove(os.path.join(frames, f))
    total, cuts = points['total'], points['cuts']
    shots = []
    for i, c in enumerate(cuts):
        end = cuts[i + 1] if i + 1 < len(cuts) else total
        grab(video, c + 0.3, os.path.join(frames, f'cut-{i:02d}-a-{c + 0.3:06.1f}s.png'))
        grab(video, end - 0.2, os.path.join(frames, f'cut-{i:02d}-b-{end - 0.2:06.1f}s.png'))
        shots.append((c, end))
    for i, m in enumerate(points['moves']):
        for tag, sec in (('before', m['start'] - 0.1), ('full', m['full'] + 0.1), ('after', min(m['end'] + 0.1, total - 0.05))):
            grab(video, sec, os.path.join(frames, f'move-{i:02d}-{tag}-{sec:06.1f}s.png'))
    names = sorted(os.listdir(frames))
    cols = 4; rows = -(-len(names) // cols)
    run(['ffmpeg', '-y', '-loglevel', 'error', '-pattern_type', 'glob', '-i', os.path.join(frames, '*.png'), '-vf', f'scale=640:-1,tile={cols}x{rows}:padding=6:color=white', '-frames:v', '1', os.path.join(project, 'review', 'sheet.png')])

    probe = json.loads(run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', video]).stdout)
    v = next(s for s in probe['streams'] if s['codec_type'] == 'video')
    a = next((s for s in probe['streams'] if s['codec_type'] == 'audio'), None)
    loud = run(['ffmpeg', '-hide_banner', '-nostats', '-i', video, '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json', '-vn', '-f', 'null', '-']).stderr
    lj = json.loads(re.search(r'\{[^{}]*"input_i"[^{}]*\}', loud, re.S).group(0)) if a else {}
    # A long still run in a clip is normal. A black or frozen card is not. List the runs for the reviewer.
    freeze = run(['ffmpeg', '-hide_banner', '-nostats', '-i', video, '-vf', 'freezedetect=n=0.001:d=4', '-an', '-f', 'null', '-']).stderr
    stills = re.findall(r'freeze_start: ([\d.]+)[\s\S]*?freeze_duration: ([\d.]+)', freeze)

    dur = float(probe['format']['duration'])
    manifest_path = os.path.join(project, 'audio', 'vo', 'manifest.json')
    manifest = json.load(open(manifest_path)) if os.path.exists(manifest_path) else {}
    silent = bool(manifest) and all(row.get('provider') == 'silent' for row in manifest.values())
    checks = [
        ('1920x1080', v['width'] == 1920 and v['height'] == 1080, f"{v['width']}x{v['height']}"),
        ('H.264 + AAC', v['codec_name'] == 'h264' and bool(a) and a['codec_name'] == 'aac', f"{v['codec_name']} / {a['codec_name'] if a else 'no audio'}"),
        ('standard color (yuv420p, limited range, BT.709)', v.get('pix_fmt') == 'yuv420p' and v.get('color_range') == 'tv' and v.get('color_space') == 'bt709', f"{v.get('pix_fmt')}, range {v.get('color_range', 'not tagged')}, matrix {v.get('color_space', 'not tagged')}"),
        ('length matches the timeline', abs(dur - total) < 0.5, f'{dur:.1f} s (timeline {total:.1f} s)'),
        ('loudness -16 LUFS +/- 1 (skipped for silent mode)' if silent else 'loudness -16 LUFS +/- 1', silent or bool(lj) and abs(float(lj['input_i']) + 16) <= 1, f"{lj.get('input_i')} LUFS"),
        ('true peak <= -1 dBTP', bool(lj) and float(lj['input_tp']) <= -1.0, f"{lj.get('input_tp')} dBTP"),
    ]
    out = [f'# Review facts: {os.path.basename(video)}', '', '## Format and audio', '']
    out += [f"- {'PASS' if ok else 'FAIL'}  {name}: {val}" for name, ok, val in checks]
    out += ['', '## Shots', '', f'{len(shots)} shots. Cuts at: ' + ', '.join(f'{c:.1f}' for c in cuts) + ' s.', '']
    out += ['## Camera moves', '']
    if not points['moves']:
        out.append('None. Each shot is a static full frame.')
    for i, m in enumerate(points['moves']):
        out.append(f"- move {i:02d}  `{m['line']}`  {m['type']}  {m['start']:.1f} to {m['end']:.1f} s. Stated reason: {m['reason']}")
    out += ['', 'For each move: read its before, full, and after frames. If the full frame does not make the stated fact easier to see than the before frame, delete the move from video.json and build again.', '']
    out += ['## Still runs of 4 s or more', ''] + ([f'- from {float(s):.1f} s for {float(d):.1f} s' for s, d in stills] or ['None.'])
    path = os.path.join(project, 'review', 'facts.md')
    open(path, 'w').write('\n'.join(out) + '\n')
    print('\n'.join(out))
    print(f'\nframes: {frames}\nsheet: {os.path.join(project, "review", "sheet.png")}\nfacts: {path}')
    if not all(ok for _, ok, _ in checks):
        raise SystemExit(1)


main()
