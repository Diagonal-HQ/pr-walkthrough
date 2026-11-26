#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { spawnSync } from 'node:child_process';
import { projectDir } from './project.mjs';

const scripts = path.dirname(fileURLToPath(import.meta.url));
const skill = path.dirname(scripts);
const [command = 'help', ...input] = process.argv.slice(2);
function run(program, args, options = {}) {
  const result = spawnSync(program, args, { stdio: 'inherit', ...options });
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(`${path.basename(program)} exited with ${result.status ?? result.signal}.`);
}
const python = process.env.PYTHON || 'python3';
function py(name, args = input) { run(python, ['-B', path.join(scripts, name), ...args]); }
function takeProject(args) {
  const remaining = [...args];
  const index = remaining.indexOf('--project');
  const raw = index >= 0 ? remaining.splice(index, 2)[1] : process.env.WALKTHROUGH_PROJECT;
  return { project: projectDir(raw), remaining };
}
try {
  switch (command) {
    case 'init': py('init_project.py'); break;
    case 'doctor': run(process.execPath, [path.join(scripts, 'doctor.mjs'), ...input]); break;
    case 'narrate': py('narrate.py'); break;
    case 'build': py('build_timeline.py'); break;
    case 'render': py('render.py'); break;
    case 'review': py('review.py'); break;
    case 'upload': py('upload.py'); break;
    case 'capture': {
      const { project, remaining } = takeProject(input);
      if (remaining.length > 1) throw new Error('capture takes one optional scene path.');
      const scene = path.resolve(remaining[0] || path.join(project, 'scenes/main.mjs'));
      run(process.execPath, [scene], { env: { ...process.env, WALKTHROUGH_PROJECT: project } });
      break;
    }
    case 'code-pages': {
      const { project } = takeProject(input);
      run(process.execPath, [path.join(scripts, 'code-pages.mjs')], { env: { ...process.env, WALKTHROUGH_PROJECT: project } });
      break;
    }
    case 'demo': {
      const outputIndex = input.indexOf('--project');
      const project = projectDir(outputIndex >= 0 ? input[outputIndex + 1] : path.join(process.cwd(), '.walkthrough/demo'));
      const providerIndex = input.indexOf('--provider');
      const provider = providerIndex >= 0 ? input[providerIndex + 1] : 'local';
      if (!['local', 'silent', 'elevenlabs'].includes(provider)) throw new Error('Unknown narration provider.');
      const example = path.join(skill, 'examples/saved-views');
      if (fs.existsSync(project) && fs.readdirSync(project).length) throw new Error('Demo output must be a new or empty directory. Choose another --project.');
      fs.mkdirSync(project, { recursive: true });
      fs.copyFileSync(path.join(example, 'video.json'), path.join(project, 'video.json'));
      fs.mkdirSync(path.join(project, 'scenes'), { recursive: true });
      const scene = fs.readFileSync(path.join(example, 'scene.mjs'), 'utf8').replaceAll('__SKILL_URL__', pathToFileURL(skill).href).replaceAll('__DEMO_URL__', pathToFileURL(path.join(example, 'app.html')).href);
      fs.writeFileSync(path.join(project, 'scenes/main.mjs'), scene);
      py('narrate.py', ['--project', project, '--provider', provider]);
      run(process.execPath, [path.join(project, 'scenes/main.mjs')], { env: { ...process.env, WALKTHROUGH_PROJECT: project } });
      py('review.py', ['--project', project, '--footage']);
      py('build_timeline.py', ['--project', project]);
      py('render.py', ['--project', project, '--name', 'saved-views']);
      const video = path.join(project, 'out/saved-views.mp4');
      py('review.py', ['--project', project, video]);
      console.log(`\nDemo complete: ${video}\nCaptions: ${project}/out/captions.srt\nReview: ${project}/review/sheet.png\nNo media was uploaded.`);
      break;
    }
    case 'pr-section': {
      const urlIndex = input.indexOf('--url');
      if (urlIndex < 0 || !input[urlIndex + 1]) throw new Error('pr-section needs --url <public-video-url>.');
      const url = new URL(input[urlIndex + 1]);
      if (!['http:', 'https:'].includes(url.protocol)) throw new Error('Use an HTTP or HTTPS video URL.');
      console.log(`## Walkthrough\n\n[Watch the walkthrough](<${url.href}>)\n\nShows the change and its visible result.\n`);
      break;
    }
    case 'help': case '--help': case '-h':
      console.log(`PR Walkthrough\n\nUsage: pr-walkthrough <command> [options]\n\n  doctor                     Check tools and Chromium (no paid requests)\n  init <directory>            Create a feature video project\n    --preset <preset>         feature-clip, product-walkthrough, code-walkthrough\n  narrate --project <dir>     Render speech; --provider elevenlabs|local|silent\n    --dry-run                 Estimate length and cost without synthesis\n  capture --project <dir>     Run scenes/main.mjs (or one supplied scene path)\n  code-pages --project <dir>  Create code slides from real git revisions\n  build --project <dir>       Build the timeline, captions, and transcript\n  render --project <dir>      Render 1080p MP4; --stills for review frames\n  review --project <dir> <mp4> Check media and generate a contact sheet\n    --footage                 Inspect capture beats before editing\n  upload --project <dir>      Optional S3-compatible publishing; --dry-run\n  pr-section --url <url>      Print Markdown for a PR (does not edit GitHub)\n  demo                       Run the bundled example using free local speech\n    --provider silent         No-credential preview without spoken audio\n\nSet WALKTHROUGH_PROJECT instead of passing --project each time.\nInstall Chromium once: npx playwright install chromium`);
      break;
    default: throw new Error(`Unknown command: ${command}. Run --help.`);
  }
} catch (error) {
  console.error(`Error: ${error.message}`);
  process.exitCode = 1;
}
