#!/usr/bin/env python3
"""Edits and renders the video from timeline.json with ffmpeg. Headless Chrome draws the cards.

usage: render.py [--project <dir>] [--stills] [--still <seconds> <out.png>] [--name <file name without extension>]

Output: <project>/out/<name>.mp4 at 1920x1080, 30 fps, H.264, AAC, -16 LUFS integrated, -1.5 dBTP.
--stills writes one frame from the middle of each shot and three for each move into <project>/review/stills/,
and sheets of 8 stills each (in file name order, left to right, then down).
"""
import html, json, os, re, shutil, subprocess, sys, time
sys.dont_write_bytecode = True  # no __pycache__ in the repository
from common import SCRIPTS, args_with_project, load_video, source_fingerprint

W, H = 1920, 1080
FADE = 8  # frames. A card fades over its background. Its content does not move.
EASE = 'if(lt({u},0.5),4*{u}*{u}*{u},1-pow(-2*{u}+2,3)/2)'  # cubic ease in and out, no overshoot
# Standard video color: limited range, BT.709, with tags. A full-range picture without tags looks washed out in a player.
COLOR = 'scale=out_range=limited:out_color_matrix=bt709,format=yuv420p'
ENCODE = ['-c:v', 'libx264', '-preset', 'medium', '-crf', '16', '-pix_fmt', 'yuv420p', '-color_range', 'tv', '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-an']


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        raise SystemExit(f"{cmd[0]} failed:\n{' '.join(cmd)[:600]}\n{r.stderr[-1500:]}")
    return r



def card_html(shot=None, brand=None):
    """One card as a page. Without a shot it is the empty background."""
    logo = '<span>' + html.escape((brand or {}).get('name', 'PR WALKTHROUGH')) + '</span>'
    body = ''
    if shot:
        section = shot['kind'] == 'section'
        body = (('' if section else f'<div class="logo">{logo}</div>')
                + f'<div class="heading{" section" if section else ""}">{html.escape(shot["heading"])}</div>'
                + (f'<div class="sub">{html.escape(shot["sub"])}</div>' if shot.get('sub') else ''))
    return f'''<!doctype html><html><head><meta charset="utf-8"><style>
html, body {{ margin: 0; width: {W}px; height: {H}px; overflow: hidden; }}
body {{ background-color: #f8f3ea; background-image: linear-gradient(to right, rgba(15,23,42,0.045) 1px, transparent 1px), linear-gradient(to bottom, rgba(15,23,42,0.045) 1px, transparent 1px); background-size: 84px 84px;
  display: flex; flex-direction: column; align-items: center; justify-content: center; color: #020617; text-align: center; }}
.logo {{ font: 600 22px system-ui; letter-spacing: .16em; margin-bottom: 60px; }}
.heading {{ font-family: Georgia, Cambria, "Times New Roman", Times, serif; font-size: 108px; letter-spacing: -0.04em; line-height: 0.98; max-width: 1500px; }}
.heading.section {{ font-size: 84px; }}
.sub {{ font-family: ui-sans-serif, system-ui, -apple-system, "Helvetica Neue", sans-serif; font-size: 34px; color: #314158; margin-top: 34px; line-height: 1.3; max-width: 1400px; }}
</style></head><body>{body}</body></html>'''


def draw_cards(work, shots, brand=None):
    """Screenshots each card and the empty background with headless Chrome. Returns {shot index or 'bg': png}."""
    cards = {i: s for i, s in enumerate(shots) if s['type'] == 'card'}
    out = {}
    if not cards:
        return out
    jobs = []
    for key, shot in [('bg', None)] + list(cards.items()):
        page = os.path.join(work, f'card-{key}.html')
        png = os.path.join(work, f'card-{key}.png')
        open(page, 'w').write(card_html(shot, brand))
        jobs.append(dict(page=page, png=png))
        out[key] = png
    manifest = os.path.join(work, 'cards.json')
    json.dump(jobs, open(manifest, 'w'))
    run(['node', os.path.join(SCRIPTS, 'draw-cards.mjs'), manifest])
    return out



def zoom_for(shot, moves):
    """The zoom move that is active in a shot, or None."""
    a, b = shot['start'], shot['start'] + shot['frames']
    return next((m for m in moves if m['type'] == 'zoom' and m['start'] < b and m['outStart'] + m['outFrames'] > a), None)


def zoompan(move, shot):
    """The camera of a zoom move as ffmpeg zoompan expressions. `on` is the frame number in the shot.
    The window keeps the target centered when the frame edge permits it, and never shows the area outside the footage."""
    f = f"(on+{shot['start']})"
    u_in = f"clip(({f}-{move['start']})/{move['inFrames']},0,1)"
    p_in = EASE.format(u=u_in)
    if move['outFrames']:
        u_out = f"clip(({f}-{move['outStart']})/{move['outFrames']},0,1)"
        p = f"if(lt({f},{move['outStart']}),{p_in},1-({EASE.format(u=u_out)}))"
    else:
        p = p_in
    cx, cy = move['x'], move['y']
    z = f"1+{move['scale'] - 1:.4f}*({p})"
    x = f"min({W}-{W}/zoom,max(0,{cx}-{W}/(2*zoom)))*iw/{W}"
    y = f"min({H}-{H}/zoom,max(0,{cy}-{H}/(2*zoom)))*ih/{H}"
    return f"zoompan=z='{z}':x='{x}':y='{y}':d=1:s={W}x{H}:fps=30"


def highlight_inputs(shot, moves, work, fps):
    """Extra inputs and filter steps that dim the frame around a region. The camera does not move."""
    inputs, steps = [], []
    a, b = shot['start'], shot['start'] + shot['frames']
    for k, m in enumerate(mm for mm in moves if mm['type'] == 'highlight' and mm['start'] < b and mm['outStart'] + mm['outFrames'] > a):
        r = m['rect']
        mask = os.path.join(work, f"mask-{shot['start']}-{k}.png")
        run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'lavfi', '-i', f'color=black@0.38:s={W}x{H},format=rgba',
             '-vf', f"drawbox=x={r['x']}:y={r['y']}:w={r['w']}:h={r['h']}:color=black@0:t=fill:replace=1", '-frames:v', '1', mask])
        fades = []
        if m['start'] >= a:
            fades.append(f"fade=t=in:st={(m['start'] - a) / fps:.3f}:d={m['inFrames'] / fps:.3f}:alpha=1")
        if m['outFrames'] and m['outStart'] < b:
            fades.append(f"fade=t=out:st={(m['outStart'] - a) / fps:.3f}:d={m['outFrames'] / fps:.3f}:alpha=1")
        inputs += ['-loop', '1', '-framerate', str(fps), '-i', mask]
        steps.append(','.join(['format=rgba'] + fades))
    return inputs, steps



def last_step(frame):
    """The end of a shot graph. A still keeps only frame `frame` of the shot. It skips the video color conversion,
    because the still is an RGB PNG."""
    return COLOR if frame is None else f"select='eq(n,{frame})'"


def clip_command(project, shot, moves, work, fps, frame=None):
    src = os.path.join(project, 'footage', shot['clip'] + '.mp4')
    move = zoom_for(shot, moves)
    chain = f'fps={fps},' + (zoompan(move, shot) if move else f'scale={W}:{H}:flags=lanczos') + ',setsar=1'
    extra, steps = highlight_inputs(shot, moves, work, fps)
    graph, last = f'[0:v]{chain}[v0]', 'v0'
    for i, step in enumerate(steps):
        graph += f';[{i + 1}:v]{step}[m{i}];[{last}][m{i}]overlay=shortest=0[v{i + 1}]'
        last = f'v{i + 1}'
    graph += f';[{last}]{last_step(frame)}[out]'
    return ['ffmpeg', '-y', '-loglevel', 'error', '-ss', f"{shot['a']:.3f}", '-i', src] + extra + \
        ['-filter_complex', graph, '-map', '[out]', '-frames:v', str(shot['frames']) if frame is None else '1']


def card_command(shot, cards, index, fps, total_frames, frame=None):
    length = shot['frames'] / fps
    fades = ['format=rgba']
    if shot['start'] > 0:
        fades.append(f'fade=t=in:st=0:d={FADE / fps:.3f}:alpha=1')
    if shot['start'] + shot['frames'] < total_frames:
        fades.append(f'fade=t=out:st={length - FADE / fps:.3f}:d={FADE / fps:.3f}:alpha=1')
    graph = f"[1:v]{','.join(fades)}[c];[0:v][c]overlay,fps={fps},setsar=1,{last_step(frame)}[v]"
    return ['ffmpeg', '-y', '-loglevel', 'error', '-loop', '1', '-framerate', str(fps), '-i', cards['bg'], '-loop', '1', '-framerate', str(fps), '-i', cards[index],
            '-filter_complex', graph, '-map', '[v]', '-frames:v', str(shot['frames']) if frame is None else '1']


def shot_command(project, t, cards, work, index, frame=None):
    """The ffmpeg command for one shot of the edit. With `frame`, it outputs only that frame of the shot."""
    shot = t['shots'][index]
    if shot['type'] == 'card':
        return card_command(shot, cards, index, t['fps'], t['frames'], frame)
    return clip_command(project, shot, t['moves'], work, t['fps'], frame)


def still(project, t, cards, work, frame, out):
    """One frame of the edit from the filter graph of its shot. ffmpeg runs the shot up to that frame."""
    frame = max(0, min(t['frames'] - 1, frame))
    index, shot = next((i, s) for i, s in enumerate(t['shots']) if s['start'] <= frame < s['start'] + s['frames'])
    run(shot_command(project, t, cards, work, index, frame - shot['start']) + [out])



def mix_audio(project, t, out):
    fps, total = t['fps'], t['frames'] / t['fps']
    if not t['vos']:
        run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo', '-t', str(total), out])
        return
    cmd, graph, names = ['ffmpeg', '-y', '-loglevel', 'error'], [], []
    for i, v in enumerate(t['vos']):
        cmd += ['-i', os.path.join(project, 'audio', 'vo', v['id'] + '.wav')]
        graph.append(f"[{i}:a]aresample=48000,adelay={round(v['start'] / fps * 1000)}:all=1[a{i}]")
        names.append(f'[a{i}]')
    graph.append(f"{''.join(names)}amix=inputs={len(names)}:normalize=0:dropout_transition=0,apad,atrim=0:{total:.3f},aformat=channel_layouts=stereo[out]")
    run(cmd + ['-filter_complex', ';'.join(graph), '-map', '[out]', '-c:a', 'pcm_s16le', '-ar', '48000', out])


def normalize(video, audio, final):
    """Two-pass loudness normalization. The first pass measures. The second pass applies a linear gain."""
    target = 'loudnorm=I=-16:TP=-1.5:LRA=11'
    log = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', audio, '-af', target + ':print_format=json', '-f', 'null', '-'], capture_output=True, text=True).stderr
    m = json.loads(re.search(r'\{[^{}]*"input_i"[^{}]*\}', log, re.S).group(0))
    if m['input_i'] == '-inf':
        run(['ffmpeg', '-y', '-loglevel', 'error', '-i', video, '-i', audio, '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-c:a', 'aac', '-ar', '48000', '-movflags', '+faststart', final])
        return
    af = f"{target}:measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true"
    run(['ffmpeg', '-y', '-loglevel', 'error', '-i', video, '-i', audio, '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-af', af, '-ar', '48000', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', final])


def main():
    project, rest = args_with_project(sys.argv[1:])
    path = os.path.join(project, 'timeline.json')
    if not os.path.exists(path):
        raise SystemExit('No timeline.json. Run build_timeline.py first.')
    t = json.load(open(path))
    if t.get('source_fingerprint') != source_fingerprint(project):
        raise SystemExit('Timeline inputs changed. Run build again before rendering.')
    fps = t['fps']
    work = os.path.join(project, '.edit')
    shutil.rmtree(work, ignore_errors=True); os.makedirs(work)
    os.makedirs(os.path.join(project, 'out'), exist_ok=True)
    cards = draw_cards(work, t['shots'], load_video(project).get('brand'))

    if '--still' in rest:
        i = rest.index('--still')
        out = os.path.abspath(rest[i + 2])
        still(project, t, cards, work, round(float(rest[i + 1]) * fps), out)
        print(out)
        return

    if '--stills' in rest:
        out = os.path.join(project, 'review', 'stills')
        shutil.rmtree(out, ignore_errors=True); os.makedirs(out)
        for i, s in enumerate(t['shots']):
            f = s['start'] + s['frames'] // 2
            still(project, t, cards, work, f, os.path.join(out, f"shot-{i:02d}-{s['line']}-{f / fps:05.1f}s.png"))
        for i, m in enumerate(t['moves']):
            for tag, f in (('before', m['start'] - 2), ('full', m['start'] + m['inFrames'] + 15), ('after', min(m['outStart'] + m['outFrames'] + 3, t['frames'] - 1))):
                still(project, t, cards, work, f, os.path.join(out, f'move-{i:02d}-{tag}-{f / fps:05.1f}s.png'))
        for old in [f for f in os.listdir(os.path.join(project, 'review')) if f.startswith('stills-sheet-')]:
            os.remove(os.path.join(project, 'review', old))
        run(['ffmpeg', '-y', '-loglevel', 'error', '-pattern_type', 'glob', '-i', os.path.join(out, '*.png'), '-vf', 'scale=960:-1,tile=2x4:padding=8:color=white', '-start_number', '1', os.path.join(project, 'review', 'stills-sheet-%d.png')])
        names = sorted(os.listdir(out))
        print(f'{len(names)} stills in {out} (file names give the shot, the line id, and the time)')
        for f in sorted(f for f in os.listdir(os.path.join(project, 'review')) if f.startswith('stills-sheet-')):
            print(os.path.join(project, 'review', f))
        return

    started = time.time()
    parts = []
    for i, shot in enumerate(t['shots']):
        part = os.path.join(work, f'part-{i:03d}.mp4')
        run(shot_command(project, t, cards, work, i) + ENCODE + ['-r', str(fps), part])
        got = int(run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0', '-show_entries', 'stream=nb_read_frames', '-of', 'csv=p=0', part]).stdout.strip())
        if got != shot['frames']:
            raise SystemExit(f"Shot {i} ({shot['line']}) has {got} frames, not {shot['frames']}. The footage is shorter than the timeline. Film the scene again.")
        parts.append(part)
    listing = os.path.join(work, 'parts.txt')
    open(listing, 'w').write(''.join("file '" + p.replace("'", "'\\''") + "'\n" for p in parts))
    picture = os.path.join(work, 'picture.mp4')
    run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', listing, '-c', 'copy', picture])
    sound = os.path.join(work, 'sound.wav')
    mix_audio(project, t, sound)

    name = rest[rest.index('--name') + 1] if '--name' in rest else re.sub(r'[^a-z0-9]+', '-', load_video(project).get('title', 'walkthrough').lower()).strip('-')
    if not re.fullmatch(r'[a-zA-Z0-9_-]+', name):
        raise SystemExit('Output names use letters, digits, underscores, or hyphens.')
    final = os.path.join(project, 'out', name + '.mp4')
    normalize(picture, sound, final)
    shutil.rmtree(work, ignore_errors=True)
    print(f'rendered in {time.time() - started:.0f} s')
    print(run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height,r_frame_rate', '-show_entries', 'format=duration,size', '-of', 'default=nw=1', final]).stdout.strip())
    print(final)


if __name__ == '__main__':
    main()
