"""Checks long spaces in the spoken character alignment and narration command. Needs ffmpeg and ffprobe."""
import base64, json, os, subprocess, sys, tempfile, unittest

sys.dont_write_bytecode = True
SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts')
sys.path.insert(0, SCRIPTS)
from common import narration_pauses


def alignment(text, pauses):
    starts, ends, time = [], [], 0.0
    for i, character in enumerate(text):
        starts.append(time)
        time += pauses.get(i, 0.07)
        ends.append(time)
    return dict(characters=list(text), character_start_times_seconds=starts, character_end_times_seconds=ends)


class NarrationPausesTest(unittest.TestCase):
    def test_flags_a_pause_inside_a_label(self):
        text = "Refresh Status and Disconnect Account on this page act on the foundation's account only."
        pauses = narration_pauses(alignment(text, {text.index(' Account'): 1.11}))
        self.assertEqual(len(pauses), 1)
        seconds, before = pauses[0]
        self.assertAlmostEqual(seconds, 1.11)
        self.assertTrue(before.endswith('Disconnect'))
        self.assertLessEqual(len(before), 30)

    def test_accepts_pauses_after_punctuation(self):
        for punctuation in '.,:;?!':
            with self.subTest(punctuation=punctuation):
                text = f'Open{punctuation}  Next'
                self.assertEqual(narration_pauses(alignment(text, {5: 0.9, 6: 0.9})), [])

    def test_flags_each_space_at_or_above_the_limit(self):
        text = 'A B C D'
        pauses = narration_pauses(alignment(text, {1: 0.6, 3: 0.59, 5: 0.9}))
        self.assertEqual([before for _, before in pauses], ['A', 'A B C'])

    def test_uses_a_custom_limit(self):
        self.assertEqual(narration_pauses(alignment('A B', {1: 0.9}), limit=1.0), [])

    def test_accepts_alignment_without_timings(self):
        self.assertEqual(narration_pauses({}), [])
        self.assertEqual(narration_pauses({'characters': list('A B')}), [])


class NarrationCommandTest(unittest.TestCase):
    def test_warns_for_new_and_cached_lines_without_failing(self):
        with tempfile.TemporaryDirectory() as root:
            project = os.path.join(root, 'project')
            cache = os.path.join(root, 'cache')
            os.makedirs(project)
            lines = [dict(id='disconnect', text='Disconnect Account'), dict(id='expires', text='Reservation Expires At')]
            with open(os.path.join(project, 'video.json'), 'w') as f:
                json.dump(dict(lines=lines, say={'Reservation Expires At': 'reservation expires at'}), f)
            audio = subprocess.run(['ffmpeg', '-loglevel', 'error', '-f', 'lavfi', '-i', 'sine=frequency=220:duration=1',
                                    '-f', 'mp3', '-'], capture_output=True, check=True, timeout=30).stdout
            audio_base64 = base64.b64encode(audio).decode()
            alignments = {
                'Disconnect Account': alignment('Disconnect Account', {10: 1.11}),
                'reservation expires at': alignment('reservation expires at', {11: 0.81}),
            }
            for cached in (False, True):
                with self.subTest(cached=cached):
                    code = f'''
import json, runpy, sys
sys.path.insert(0, {SCRIPTS!r})
import common
alignments = {alignments!r}
def synthesize(method, path, body=None, headers=None, timeout=180):
    if {cached!r}:
        raise AssertionError('A cache hit must not synthesize narration.')
    print('SYNTHESIS ' + body['text'])
    return json.dumps(dict(audio_base64={audio_base64!r}, alignment=alignments[body['text']])).encode(), {{}}
common.call = synthesize
sys.argv = ['narrate.py', '--project', {project!r}]
runpy.run_path({os.path.join(SCRIPTS, 'narrate.py')!r}, run_name='__main__')
'''
                    env = dict(os.environ, WALKTHROUGH_CACHE=cache, WALKTHROUGH_TTS_BUDGET='6000')
                    result = subprocess.run([sys.executable, '-B', '-c', code], env=env, capture_output=True, text=True, timeout=30)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    warnings = [line for line in result.stdout.splitlines() if line.startswith('PAUSE ')]
                    self.assertEqual(len(warnings), 2, result.stdout)
                    self.assertIn('PAUSE disconnect  1.11 s after "Disconnect"', warnings[0])
                    self.assertIn('PAUSE expires  0.81 s after "reservation"', warnings[1])
                    self.assertIn('lowercase "say" respelling', warnings[0])
                    self.assertIn('put a noun after it', warnings[0])
                    self.assertIn('2 PAUSE warning(s).', result.stdout)
                    self.assertEqual(result.stdout.count('SYNTHESIS '), 0 if cached else 2)
                    manifest_path = os.path.join(project, 'audio', 'vo', 'manifest.json')
                    with open(manifest_path) as f:
                        manifest = json.load(f)
                    self.assertEqual({row['rendered'] for row in manifest.values()}, {not cached})
                    for line in lines:
                        with open(os.path.join(project, 'audio', 'vo', line['id'] + '.alignment.json')) as f:
                            self.assertEqual(json.load(f), alignments[manifest[line['id']]['spoken']])


if __name__ == '__main__':
    unittest.main()
