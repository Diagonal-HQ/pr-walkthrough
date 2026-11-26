import fs from 'node:fs';
import { spawnSync } from 'node:child_process';
import { chromium } from 'playwright';
let failed = false;
for (const [program, args] of [['node', ['--version']], [process.env.PYTHON || 'python3', ['--version']], ['ffmpeg', ['-version']], ['ffprobe', ['-version']], ['git', ['--version']]]) {
  const result = spawnSync(program, args, { encoding: 'utf8' });
  const ok = result.status === 0;
  console.log(`${ok ? 'PASS' : 'FAIL'} ${program}: ${ok ? result.stdout.split('\n')[0] : 'not available on PATH'}`);
  failed ||= !ok;
}
if (fs.existsSync(chromium.executablePath())) {
  try {
    const browser = await chromium.launch();
    await browser.close();
    console.log('PASS Chromium: launches successfully');
  } catch (error) {
    failed = true;
    console.log(`FAIL Chromium: ${error.message}`);
  }
} else {
  failed = true;
  console.log('FAIL Chromium: run npx playwright install chromium (on Linux: npx playwright install --with-deps chromium)');
}
const local = ['say', 'espeak-ng', 'espeak'].find((program) => spawnSync('which', [program]).status === 0);
console.log(`INFO Local narration: ${local || 'install espeak-ng, or choose --provider silent'}`);
console.log(`INFO ElevenLabs: ${process.env.ELEVENLABS_API_KEY ? 'key exported; no request made' : 'optional; export ELEVENLABS_API_KEY to use it'}`);
process.exitCode = failed ? 1 : 0;
