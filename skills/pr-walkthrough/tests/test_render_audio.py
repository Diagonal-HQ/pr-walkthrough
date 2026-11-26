"""Checks that render.py mixes narration to the timeline length, with silence between lines and after speech.
Needs ffmpeg and ffprobe.

usage: python3 -B -m unittest discover -s skills/pr-walkthrough/tests -p test_render_audio.py
"""
import json, os, re, signal, subprocess, sys, tempfile, unittest

SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts')
FPS = 30
FRAMES = 180
VOS = [dict(id='one', start=15, frames=30), dict(id='two', start=90, frames=30)]


def ffmpeg(*args):
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', *args], check=True, timeout=60)


def mix(project):
    """Runs render.mix_audio in a child process with a time limit, and returns the path of the mix."""
    out = os.path.join(project, 'sound.wav')
    timeline = dict(fps=FPS, frames=FRAMES, vos=VOS)
    code = f'import sys; sys.path.insert(0, {SCRIPTS!r}); import render; render.mix_audio({project!r}, {timeline!r}, {out!r})'
    # A new process group, so that a timeout also stops the ffmpeg process that mix_audio starts.
    child = subprocess.Popen([sys.executable, '-B', '-c', code], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
    try:
        _, err = child.communicate(timeout=30)
    except subprocess.TimeoutExpired:
        os.killpg(child.pid, signal.SIGKILL)
        child.communicate()
        raise
    if child.returncode != 0:
        raise AssertionError(f'mix_audio failed: {err}')
    return out


def mean_volume(path, start, end):
    log = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-ss', str(start), '-to', str(end), '-i', path, '-af', 'volumedetect', '-f', 'null', '-'],
                         capture_output=True, text=True, timeout=60).stderr
    return float(re.search(r'mean_volume: (-?[\d.]+|-inf) dB', log).group(1))


class NarrationMixTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = self.tmp.name
        vo = os.path.join(self.project, 'audio', 'vo')
        os.makedirs(vo)
        for v in VOS:
            ffmpeg('-f', 'lavfi', '-i', 'sine=frequency=220:duration=1', '-ar', '48000', '-ac', '1', os.path.join(vo, v['id'] + '.wav'))

    def tearDown(self):
        self.tmp.cleanup()

    def test_mixes_narration_to_the_timeline_length(self):
        out = mix(self.project)
        probe = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration:stream=sample_rate,channels', '-of', 'json', out],
                                          capture_output=True, text=True, check=True).stdout)
        self.assertAlmostEqual(float(probe['format']['duration']), FRAMES / FPS, places=3)
        self.assertEqual((probe['streams'][0]['sample_rate'], probe['streams'][0]['channels']), ('48000', 2))
        self.assertGreater(mean_volume(out, 0.5, 1.5), -50)
        self.assertGreater(mean_volume(out, 3.0, 4.0), -50)
        self.assertLess(mean_volume(out, 2.0, 2.9), -90)
        self.assertLess(mean_volume(out, 4.5, 6.0), -90)


if __name__ == '__main__':
    unittest.main()
