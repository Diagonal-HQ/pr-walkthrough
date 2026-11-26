"""Runs build_timeline.py on small projects and checks the timeline, the captions, and the motion rules.

usage: python3 -B -m unittest discover -s skills/pr-walkthrough/tests
"""
import json, os, re, subprocess, sys, tempfile, unittest

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts', 'build_timeline.py')
FPS = 30

FEATURE_LINES = [
    dict(id='title', on='title', heading='Saved views', text='Saved views keep a filtered list one click away.', duration=3.0),
    dict(id='open', text='Open the Businesses list. It shows every member, so the list is long and hard to scan.', duration=6.0, beat=(0.0, 6.5)),
    dict(id='filter', text='Filter the list to active members with the Membership Status filter. The table now shows only the businesses that you need today.', duration=8.0, beat=(6.5, 15.0),
         move=dict(type='highlight', target='status-filter', reason='The filter chip is small and the narration names it.')),
    dict(id='save', text='Save the view and give it a short name. It appears in the view menu for each person on your team.', duration=7.0, beat=(15.0, 22.5)),
    dict(id='end', on='end', heading='Save the views you use', text='That is all it takes to save a view.', duration=4.0),
]


def sentence(words):
    return ' '.join(['records'] * words) + '.'


def product_lines():
    """2 minutes, with two section cards between the shots of one clip."""
    return [
        dict(id='title', on='title', heading='The records list', text=sentence(14), duration=5.5),
        dict(id='orient', text=sentence(60), duration=24.5, beat=(0.0, 25.0)),
        dict(id='ch1', on='section', heading='Find a record'),
        dict(id='ch1_a', text=sentence(60), duration=24.5, beat=(25.0, 50.0),
             move=dict(type='zoom', target='search', scale=1.35, reason='The search field is 11 px tall and the narration reads it.')),
        dict(id='ch2', on='section', heading='Sort the list'),
        dict(id='ch2_a', text=sentence(60), duration=24.5, beat=(50.0, 75.0)),
        dict(id='recap', text=sentence(70), duration=29.5, beat=(75.0, 105.0)),
        dict(id='end', on='end', heading='Find any record', text=sentence(14), duration=5.5),
    ]


def write_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f)


def read_json(path):
    with open(path) as f:
        return json.load(f)


def write_project(root, preset, lines, targets, alignments=None, video_extra=None):
    """video.json, the narration manifest, and the footage metadata of one clip named "main"."""
    video_lines = [{k: v for k, v in l.items() if k not in ('duration', 'beat')} for l in lines]
    video = dict(title='Test video', preset=preset, lines=video_lines)
    video.update(video_extra or {})
    vo = os.path.join(root, 'audio', 'vo')
    os.makedirs(vo)
    os.makedirs(os.path.join(root, 'footage'))
    write_json(os.path.join(root, 'video.json'), video)
    write_json(os.path.join(vo, 'manifest.json'), {l['id']: dict(text=l['text'], duration=l['duration']) for l in lines if l.get('text')})
    for lid, alignment in (alignments or {}).items():
        write_json(os.path.join(vo, lid + '.alignment.json'), alignment)
    beats = [dict(id=l['id'], a=l['beat'][0], b=l['beat'][1]) for l in lines if 'beat' in l]
    meta = dict(name='main', viewport=dict(width=1280, height=720), beats=beats, targets=targets)
    write_json(os.path.join(root, 'footage', 'main.json'), meta)


def uniform_alignment(text, step):
    return dict(characters=list(text), character_start_times_seconds=[i * step for i in range(len(text))],
                character_end_times_seconds=[(i + 1) * step for i in range(len(text))])


def build(root, *args):
    return subprocess.run([sys.executable, '-B', SCRIPT, '--project', root, *args], capture_output=True, text=True, timeout=60)


def srt_cues(path):
    """[(start s, end s, text)] in file order."""
    def sec(stamp):
        h, m, s, ms = map(int, re.split('[:,]', stamp))
        return h * 3600 + m * 60 + s + ms / 1000
    cues = []
    with open(path) as f:
        blocks = f.read().strip().split('\n\n')
    for block in blocks:
        _, times, text = block.split('\n', 2)
        a, b = times.split(' --> ')
        cues.append((sec(a), sec(b), text))
    return cues


class FeatureClipTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, lines=FEATURE_LINES, targets=None, alignments=None, video_extra=None):
        targets = {'status-filter': dict(x=200, y=100, w=120, h=32, t=8.0)} if targets is None else targets
        write_project(self.root, 'feature-clip', lines, targets, alignments, video_extra)

    def test_builds_the_timeline_and_the_captions(self):
        open_text = FEATURE_LINES[1]['text']
        self.write(alignments={'open': uniform_alignment(open_text, 0.05)})
        r = build(self.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

        t = read_json(os.path.join(self.root, 'timeline.json'))
        # Cards are as long as their line plus lead and breath. A clip is as long as its beat.
        self.assertEqual([(s['type'], s['line'], s['start'], s['frames']) for s in t['shots']], [
            ('card', 'title', 0, 105), ('clip', 'open', 105, 195), ('clip', 'filter', 300, 255),
            ('clip', 'save', 555, 225), ('card', 'end', 780, 135)])
        self.assertEqual(t['frames'], 915)
        self.assertEqual([(v['id'], v['start'], v['frames']) for v in t['vos']],
                         [('title', 4, 90), ('open', 109, 180), ('filter', 304, 240), ('save', 559, 210), ('end', 784, 120)])
        # The target is 1.5x larger in output pixels. It is on the screen 1.5 s into the beat.
        self.assertEqual(t['moves'], [dict(type='highlight', line='filter', reason=FEATURE_LINES[2]['move']['reason'], start=351,
                                           rect=dict(x=292, y=142, w=196, h=64), inFrames=9, outFrames=9, outStart=542)])

        cues = srt_cues(os.path.join(self.root, 'out', 'captions.srt'))
        # The alignment of "open" places its second sentence at character 26, 1.3 s into the line.
        self.assertEqual(cues[:3], [
            (0.133, 3.133, 'Saved views keep a filtered list one click away.'),
            (3.633, 4.933, 'Open the Businesses list.'),
            (4.933, 9.633, 'It shows every member, so the list is long and hard to scan.')])
        self.assertEqual([c[2] for c in cues[3:]], [
            'Filter the list to active members', 'with the Membership Status filter.',
            'The table now shows only the businesses that you need today.',
            'Save the view and give it a short name.', 'It appears in the view menu for each person on your team.',
            'That is all it takes to save a view.'])
        for a, b in zip(cues, cues[1:]):
            self.assertLessEqual(a[1], b[0], f'{a} overlaps {b}')
        for vo in t['vos']:
            line = [c for c in t['captions'] if vo['start'] <= c['start'] < vo['start'] + vo['frames']]
            self.assertTrue(line, vo['id'])
            self.assertLessEqual(line[-1]['start'] + line[-1]['frames'], vo['start'] + vo['frames'], f"a caption of {vo['id']} outlasts its line")

        points = read_json(os.path.join(self.root, 'review-points.json'))
        self.assertEqual(points['total'], 30.5)
        self.assertEqual(points['cuts'], [0.0, 3.5, 10.0, 18.5, 26.0])

    def test_refuses_music_settings(self):
        for field in ('music', 'music_bed', 'music_open'):
            for value in ('audio/music.mp3', '', 0, False):
                with self.subTest(field=field, value=value), tempfile.TemporaryDirectory() as root:
                    write_project(root, 'feature-clip', FEATURE_LINES, {}, video_extra={field: value})
                    r = build(root)
                    self.assertNotEqual(r.returncode, 0)
                    self.assertIn('video.json: music is not supported. Remove music, music_bed, and music_open.', r.stderr)
                    self.assertFalse(os.path.exists(os.path.join(root, 'timeline.json')))

    def test_accepts_null_music_settings(self):
        self.write(video_extra={'music': None, 'music_bed': None, 'music_open': None})
        r = build(self.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        timeline = read_json(os.path.join(self.root, 'timeline.json'))
        for field in ('music', 'music_bed', 'music_open'):
            self.assertNotIn(field, timeline)

    def test_refuses_footage_that_is_shorter_than_its_line(self):
        lines = [dict(l) for l in FEATURE_LINES]
        lines[3]['beat'] = (15.0, 21.0)
        self.write(lines)
        r = build(self.root, '--allow-warnings')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('ERROR save: the footage is 1.5 s shorter than the line.', r.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.root, 'timeline.json')))

    def test_refuses_a_move_whose_target_is_not_in_the_footage(self):
        self.write(targets={})
        r = build(self.root, '--allow-warnings')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('ERROR filter: the move target "status-filter" is not in the footage.', r.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.root, 'timeline.json')))

    def test_refuses_narration_that_is_older_than_the_script(self):
        self.write()
        video = read_json(os.path.join(self.root, 'video.json'))
        video['lines'][2]['text'] += ' Then save it.'
        write_json(os.path.join(self.root, 'video.json'), video)
        r = build(self.root, '--allow-warnings')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('ERROR filter: the text changed after narration.', r.stdout)


class ProductWalkthroughTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def test_builds_section_cards_and_a_zoom(self):
        write_project(self.root, 'product-walkthrough', product_lines(), {'search': dict(x=400, y=80, w=240, h=36, t=26.0)})
        r = build(self.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        t = read_json(os.path.join(self.root, 'timeline.json'))
        self.assertEqual([(s['type'], s['line'], s['frames']) for s in t['shots']], [
            ('card', 'title', 180), ('clip', 'orient', 750), ('card', 'ch1', 45), ('clip', 'ch1_a', 750),
            ('card', 'ch2', 45), ('clip', 'ch2_a', 750), ('clip', 'recap', 900), ('card', 'end', 180)])
        self.assertEqual(t['frames'], 3600)
        self.assertEqual(t['shots'][2]['heading'], 'Find a record')
        zoom = t['moves'][0]
        self.assertEqual((zoom['type'], zoom['start'], zoom['x'], zoom['y'], zoom['scale']), ('zoom', 1011, 780, 147, 1.35))
        self.assertEqual((zoom['inFrames'], zoom['outFrames'], zoom['outStart']), (24, 18, 1703))
        cues = srt_cues(os.path.join(self.root, 'out', 'captions.srt'))
        for a, b in zip(cues, cues[1:]):
            self.assertLessEqual(a[1], b[0], f'{a} overlaps {b}')
        self.assertEqual(len(cues), len(t['captions']))

    def test_refuses_a_move_through_a_section_card(self):
        lines = product_lines()
        lines[3]['move'] = dict(lines[3]['move'], until='ch2_a')
        write_project(self.root, 'product-walkthrough', lines, {'search': dict(x=400, y=80, w=240, h=36, t=26.0)})
        r = build(self.root, '--allow-warnings')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('ERROR ch1_a: a move cannot continue through a card or a different clip', r.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.root, 'timeline.json')))


if __name__ == '__main__':
    unittest.main()
