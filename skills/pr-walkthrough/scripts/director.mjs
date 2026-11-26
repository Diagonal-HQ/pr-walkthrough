// Drives the recording browser over CDP and captures a screencast with timestamps.
// Playwright owns an isolated Chromium browser for each scene.
// Usage: import { Director, byText, byTextIn, hasText } from '<skill>/scripts/director.mjs'
// See references/capture.md for the scene contract.
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { chromium } from 'playwright';
import { readConfig, projectDir } from './project.mjs';

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const BREATH = 0.35;

// Runs in the page on every document: a visible cursor, a click ring, and CSS that hides
// developer-only chrome. It adds nothing that looks like product UI.
const PAGE_SCRIPT = `(() => {
  if (window.__demoCursor) return;
  window.__demoCursor = true;
  const css = document.createElement('style');
  css.textContent = \`
    [data-demo-hide] { display: none !important; }
    #__cur { position: fixed; left: 0; top: 0; z-index: 2147483647; pointer-events: none; width: 28px; height: 28px;
      transform: translate(-100px,-100px); will-change: transform; filter: drop-shadow(0 1px 2px rgba(0,0,0,.35)); }
    #__ring { position: fixed; left: 0; top: 0; z-index: 2147483646; pointer-events: none; width: 44px; height: 44px; margin: -22px 0 0 -22px;
      border-radius: 50%; background: rgba(23,23,23,.22); box-shadow: 0 0 0 1.5px rgba(255,255,255,.7); opacity: 0; transform: scale(.3); }
    #__ring.go { animation: __ring .45s ease-out; }
    @keyframes __ring { 0% { opacity: .9; transform: scale(.3); } 100% { opacity: 0; transform: scale(1.25); } }
    html { scrollbar-width: none; }
  \`;
  const cur = document.createElement('div');
  cur.id = '__cur';
  // Build the cursor with DOM calls. A page with a Trusted Types policy refuses innerHTML.
  const NS = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(NS, 'svg');
  svg.setAttribute('viewBox', '0 0 28 28'); svg.setAttribute('width', '28'); svg.setAttribute('height', '28');
  const arrow = document.createElementNS(NS, 'path');
  arrow.setAttribute('d', 'M5 3l0 19 5-4.6 3.3 7.4 3.2-1.4-3.3-7.3 6.8-.4z');
  arrow.setAttribute('fill', '#111'); arrow.setAttribute('stroke', '#fff'); arrow.setAttribute('stroke-width', '1.6'); arrow.setAttribute('stroke-linejoin', 'round');
  svg.appendChild(arrow); cur.appendChild(svg);
  const ring = document.createElement('div');
  ring.id = '__ring';
  const place = (x, y) => { cur.style.transform = 'translate(' + (x - 5) + 'px,' + (y - 3) + 'px)'; try { sessionStorage.setItem('__cur', x + ',' + y); } catch (e) {} };
  const mount = () => {
    if (!document.documentElement) return;
    if (!css.isConnected) document.documentElement.appendChild(css);
    if (!cur.isConnected) document.documentElement.appendChild(cur);
    if (!ring.isConnected) document.documentElement.appendChild(ring);
  };
  const hideDev = () => {
    (window.__demoHide || []).forEach((find) => { try { const r = find(); (r instanceof Element ? [r] : Array.from(r || [])).forEach((el) => el.setAttribute('data-demo-hide', '')); } catch (e) {} });
  };
  window.__demoApplyHide = hideDev;
  mount();
  try { const p = (sessionStorage.getItem('__cur') || '').split(','); if (p.length === 2) place(+p[0], +p[1]); } catch (e) {}
  window.addEventListener('mousemove', (e) => place(e.clientX, e.clientY), true);
  window.addEventListener('mousedown', (e) => {
    // Position with left and top. A translate would be scaled by the ring animation.
    ring.style.left = e.clientX + 'px'; ring.style.top = e.clientY + 'px';
    ring.classList.remove('go'); void ring.offsetWidth; ring.classList.add('go');
  }, true);
  new MutationObserver(() => { mount(); hideDev(); }).observe(document, { childList: true, subtree: true });
  document.addEventListener('DOMContentLoaded', () => { mount(); hideDev(); });
})();`;

export class Director {
  // project: the video project directory (default: $WALKTHROUGH_PROJECT).
  // viewport: CSS size and device scale factor. 1440x810 at 2x gives large, sharp UI in a 1080p frame.
  static async connect({ project = process.env.WALKTHROUGH_PROJECT, viewport, capture = true, headless } = {}) {
    if (!project && capture) throw new Error('Set WALKTHROUGH_PROJECT or pass { project }.');
    const d = new Director();
    d.project = project ? projectDir(project) : process.cwd();
    d.config = readConfig(d.project);
    d.viewport = viewport || d.config.viewport || { width: 1440, height: 810, scale: 2 };
    if (![d.viewport.width, d.viewport.height].every((n) => Number.isInteger(n) && n > 0)
        || !Number.isFinite(d.viewport.scale) || d.viewport.scale <= 0 || d.viewport.scale > 3
        || Math.abs(d.viewport.width / d.viewport.height - 16 / 9) > 0.001) {
      throw new Error('Use a 16:9 viewport with positive integer dimensions and a scale greater than 0 and at most 3.');
    }
    const { width, height, scale } = d.viewport;
    d.browser = await chromium.launch({ headless: headless ?? d.config.headless ?? true });
    try {
      d.context = await d.browser.newContext({ viewport: { width, height }, deviceScaleFactor: scale,
        ignoreHTTPSErrors: d.config.ignoreHTTPSErrors ?? false,
        ...(d.config.storageState ? { storageState: path.resolve(d.project, d.config.storageState) } : {}) });
      d.page = await d.context.newPage();
      d.cdp = await d.context.newCDPSession(d.page);
      d.footage = path.join(d.project, 'footage');
      d.narration = readNarration(d.project);
      d.beats = []; d.targets = {}; d.frames = []; d.marks = []; d.capturing = false;
      d.x = Math.round(width / 2); d.y = Math.round(height / 2);
      d.cdp.on('Page.screencastFrame', ({ data, metadata, sessionId }) => {
        d.send('Page.screencastFrameAck', { sessionId }).catch(() => {});
        if (!d.capturing) return;
        const file = path.join(d.dir, 'f' + String(d.frames.length).padStart(6, '0') + '.jpg');
        fs.writeFileSync(file, Buffer.from(data, 'base64'));
        d.frames.push({ file, t: metadata.timestamp - d.skipped });
      });
      await d.page.addInitScript({ content: PAGE_SCRIPT });
      await d.eval(PAGE_SCRIPT);
      return d;
    } catch (error) {
      await d.browser.close();
      throw error;
    }
  }

  send(method, params = {}) { return this.cdp.send(method, params); }

  async eval(expression) { return this.page.evaluate(expression); }

  async startCapture(name) {
    if (!/^[a-zA-Z0-9_-]+$/.test(name)) throw new Error('Clip names use letters, digits, underscores, or hyphens.');
    this.name = name;
    this.dir = path.join(this.footage, name + '.frames');
    fs.rmSync(this.dir, { recursive: true, force: true });
    // Remove the last take of this clip, so that a failed take cannot leave old footage for the next step.
    for (const ext of ['.mp4', '.json']) { fs.rmSync(path.join(this.footage, name + ext), { force: true }); }
    fs.mkdirSync(this.dir, { recursive: true });
    this.frames = []; this.marks = []; this.beats = []; this.targets = {}; this.skipped = 0; this.capturing = true;
    const { width, height, scale } = this.viewport;
    await this.send('Page.startScreencast', { format: 'jpeg', quality: 93, maxWidth: width * scale, maxHeight: height * scale, everyNthFrame: 1 });
    await this.nudge();
    this.mark('start');
  }

  // Forces a frame so that the capture always has a first and a last image.
  async nudge() {
    await this.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: this.x + 1, y: this.y });
    await sleep(40);
    await this.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: this.x, y: this.y });
    await sleep(60);
  }

  // Capture time in seconds. It leaves out the time that skip() removed.
  now() { return Date.now() / 1000 - (this.skipped || 0); }

  mark(label) { this.marks.push({ label, t: this.now() }); }

  // Runs a wait off camera. The footage jumps from the frame before the wait to the frame after it,
  // so a slow page load looks fast. Use it only for a wait, not for an action that the viewer must see.
  async skip(wait) {
    const from = Date.now() / 1000;
    this.capturing = false;
    try { await wait(); } finally {
      this.skipped += Date.now() / 1000 - from - 0.12;
      this.capturing = true;
      await this.nudge();
    }
  }

  async stopCapture() {
    await this.nudge();
    this.mark('end');
    await sleep(150);
    this.capturing = false;
    await this.send('Page.stopScreencast');
    const frames = this.frames;
    if (frames.length < 2) { throw new Error('no frames captured'); }
    const t0 = frames[0].t;
    const endT = this.marks.at(-1).t;
    let list = '';
    frames.forEach((f, i) => {
      const next = i + 1 < frames.length ? frames[i + 1].t : Math.max(endT, f.t + 0.05);
      list += `file '${f.file.replaceAll("'", "'\\''")}'\nduration ${Math.max(next - f.t, 0.001).toFixed(4)}\n`;
    });
    list += `file '${frames.at(-1).file.replaceAll("'", "'\\''")}'\n`;
    const listFile = path.join(this.dir, 'list.txt');
    fs.writeFileSync(listFile, list);
    const out = path.join(this.footage, this.name + '.mp4');
    execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', listFile, // The JPEG frames are full range with the BT.601 matrix. Write standard video: limited range, BT.709, with tags.
      // Without this, a player reads the full-range values as limited range, and light grays clip to white.
      '-vf', `fps=60,scale=${this.viewport.width * this.viewport.scale}:${this.viewport.height * this.viewport.scale}:flags=lanczos:in_range=full:out_range=limited:in_color_matrix=bt601:out_color_matrix=bt709,format=yuv420p`,
      '-c:v', 'libx264', '-crf', '12', '-preset', 'medium', '-color_range', 'tv', '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709', out]);
    const marks = this.marks.map((m) => ({ label: m.label, t: +(m.t - t0).toFixed(3) }));
    const beats = this.beats.map((b) => ({ ...b, a: +(b.a - t0).toFixed(3), b: +(b.b - t0).toFixed(3) }));
    const duration = +(endT - t0).toFixed(3);
    for (const target of Object.values(this.targets)) { target.t = +(target.t - t0).toFixed(3); }
    const meta = { name: this.name, viewport: this.viewport, frames: frames.length, duration, captureFps: +(frames.length / duration).toFixed(1), beats, targets: this.targets, marks };
    fs.writeFileSync(path.join(this.footage, this.name + '.json'), JSON.stringify(meta, null, 2));
    fs.rmSync(this.dir, { recursive: true, force: true });
    return meta;
  }

  async moveTo(x, y, ms) {
    const sx = this.x, sy = this.y;
    const dist = Math.hypot(x - sx, y - sy);
    if (dist < 2) { return; }
    ms ??= Math.min(900, 320 + dist * 0.75);
    // A slight arc reads as a hand, not a robot.
    const bend = Math.min(60, dist * 0.12) * (x > sx ? -1 : 1);
    const mx = (sx + x) / 2 + ((y - sy) / dist) * bend;
    const my = (sy + y) / 2 - ((x - sx) / dist) * bend;
    const start = Date.now();
    for (;;) {
      const p = Math.min(1, (Date.now() - start) / ms);
      const e = p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2;
      const cx = (1 - e) * (1 - e) * sx + 2 * (1 - e) * e * mx + e * e * x;
      const cy = (1 - e) * (1 - e) * sy + 2 * (1 - e) * e * my + e * e * y;
      await this.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: cx, y: cy });
      this.x = cx; this.y = cy;
      if (p >= 1) { break; }
      await sleep(12);
    }
  }

  // `find` is a JS expression that returns an element.
  async rect(find) {
    const r = await this.eval(`(() => { const el = ${find}; if (!el) return null; el.scrollIntoView({ block: 'nearest' }); const r = el.getBoundingClientRect(); return { x: r.x, y: r.y, w: r.width, h: r.height }; })()`);
    if (!r) { throw new Error('not found: ' + find); }
    return r;
  }

  async hover(find, opts = {}) {
    const r = await this.rect(find);
    await this.moveTo(r.x + r.w * (opts.fx ?? 0.5), r.y + r.h * (opts.fy ?? 0.5), opts.ms);
    return r;
  }

  async click(find, opts = {}) {
    await this.hover(find, opts);
    await sleep(opts.settle ?? 220);
    await this.press();
  }

  async press() {
    const p = { x: this.x, y: this.y, button: 'left', clickCount: 1 };
    await this.send('Input.dispatchMouseEvent', { type: 'mousePressed', ...p });
    await sleep(70);
    await this.send('Input.dispatchMouseEvent', { type: 'mouseReleased', ...p });
  }

  async type(text, per = 75) {
    for (const ch of text) {
      await this.send('Input.insertText', { text: ch });
      await sleep(per * (0.6 + Math.random() * 0.8));
    }
  }

  async key(key, code = key, keyCode = 0) {
    await this.send('Input.dispatchKeyEvent', { type: 'keyDown', key, code, windowsVirtualKeyCode: keyCode });
    await this.send('Input.dispatchKeyEvent', { type: 'keyUp', key, code, windowsVirtualKeyCode: keyCode });
  }

  // Scrolls the scroll container under the cursor with an eased animation, one step per frame.
  async scroll(dy, ms = 700) {
    await this.eval(`new Promise((done) => {
      let el = document.elementFromPoint(${this.x}, ${this.y});
      while (el && !(el.scrollHeight > el.clientHeight + 4 && /auto|scroll/.test(getComputedStyle(el).overflowY))) el = el.parentElement;
      el = el || document.scrollingElement;
      const from = el.scrollTop, start = performance.now();
      const tick = (now) => {
        const p = Math.min(1, (now - start) / ${ms});
        const e = p < 0.5 ? 2 * p * p : 1 - Math.pow(-2 * p + 2, 2) / 2;
        el.scrollTop = from + ${dy} * e;
        p < 1 ? requestAnimationFrame(tick) : done(true);
      };
      requestAnimationFrame(tick);
    })`);
  }

  async waitFor(expression, timeout = 15000) {
    const start = Date.now();
    while (Date.now() - start < timeout) {
      if (await this.eval(`!!(${expression})`).catch(() => false)) { return; }
      await sleep(100);
    }
    throw new Error('timeout waiting for ' + expression);
  }

  async goto(url) {
    await this.page.goto(url, { waitUntil: 'load' });
  }

  // Films one narration line. It runs the actions, then holds the frame until the line (plus a breath) is over.
  // The footage then already has the pace of the voice, so the edit plays it at normal speed.
  // Each cursor position is in CSS pixels of the viewport.
  async beat(id, actions = async () => {}) {
    const line = this.narration[id];
    if (!line) { throw new Error(`No narration for line "${id}". Run narrate.py first, and use the line ids from video.json.`); }
    const a = this.now();
    this.current = { a, duration: line.duration };
    await actions();
    const acted = this.now() - a;
    const hold = line.duration + BREATH - acted;
    if (hold > 0) { await sleep(hold * 1000); }
    this.current = null;
    await this.nudge();
    const b = this.now();
    this.beats.push({ id, a, b, narration: line.duration, acted: +acted.toFixed(3) });
    if (hold < 0) { console.error(`beat ${id}: the action takes ${(-hold).toFixed(1)} s longer than the narration`); }
  }

  // Keeps developer-only or test-residue elements out of the frame, through each re-render and page change.
  // `find` is a JS expression that returns one element or a list of elements. Do not hide product UI.
  async hide(find) {
    const source = `(window.__demoHide = window.__demoHide || []).push(() => ${find});`;
    await this.send('Page.addScriptToEvaluateOnNewDocument', { source });
    await this.eval(`${source} window.__demoApplyHide && window.__demoApplyHide(); true`);
  }

  // Records where an element is now, in CSS pixels. A zoom or highlight in video.json names it as its target,
  // so the edit frames the element from its real rectangle.
  async target(name, find) {
    const r = await this.rect(find);
    this.targets[name] = { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.w), h: Math.round(r.h), t: this.now() };
    return r;
  }

  // Inside a beat: waits until the narration line has `seconds` left. Use it before a click that changes the page,
  // so that the page changes when the line ends and not while the narrator still describes the old page.
  // A click() takes about 1.4 s (cursor move, settle, press), so the default leaves 1.5 s.
  async lineEnd(seconds = 1.5) {
    if (!this.current) { throw new Error('lineEnd() works only inside a beat.'); }
    const wait = this.current.duration - seconds - (this.now() - this.current.a);
    if (wait > 0) { await sleep(wait * 1000); }
  }

  // Scrolls on camera until the element is in the middle of its scroll container (or as near as the page permits).
  // click() and hover() jump-scroll an element that is outside the view. Call this first to show the scroll.
  async scrollTo(find, ms = 900) {
    await this.eval(`new Promise((done) => {
      const target = ${find};
      if (!target) return done(false);
      let el = target.parentElement;
      while (el && !(el.scrollHeight > el.clientHeight + 4 && /auto|scroll/.test(getComputedStyle(el).overflowY))) el = el.parentElement;
      el = el || document.scrollingElement;
      const box = el === document.scrollingElement ? { top: 0, height: innerHeight } : el.getBoundingClientRect();
      const r = target.getBoundingClientRect();
      const from = el.scrollTop;
      const to = Math.max(0, Math.min(el.scrollHeight - el.clientHeight, from + (r.top + r.height / 2) - (box.top + box.height / 2)));
      if (Math.abs(to - from) < 2) return done(true);
      const start = performance.now();
      const tick = (now) => {
        const p = Math.min(1, (now - start) / ${ms});
        const e = p < 0.5 ? 2 * p * p : 1 - Math.pow(-2 * p + 2, 2) / 2;
        el.scrollTop = from + (to - from) * e;
        p < 1 ? requestAnimationFrame(tick) : done(true);
      };
      requestAnimationFrame(tick);
    })`);
  }

  // The hook uses this.page (Playwright) to prepare authentication or fixture data off camera.
  async prepare(url = process.env.WALKTHROUGH_APP_URL || this.config.appUrl) {
    if (this.config.setup) {
      const { pathToFileURL } = await import('node:url');
      const hook = await import(pathToFileURL(path.resolve(this.project, this.config.setup)).href);
      if (typeof hook.default !== 'function') throw new Error('The setup module must export a default async function.');
      await hook.default(this);
    }
    if (url) await this.goto(url);
    for (const selector of this.config.hide || []) await this.hide(`document.querySelectorAll(${JSON.stringify(selector)})`);
  }

  sleep(ms) { return sleep(ms); }
  async close() { await this.browser.close(); }
}

// Element finders used by the scenes.
export const byText = (tag, text) => `[...document.querySelectorAll(${JSON.stringify(tag)})].find((e) => (e.textContent || '').trim() === ${JSON.stringify(text)} && e.offsetParent !== null)`;
export const byTextIn = (tag, text) => `[...document.querySelectorAll(${JSON.stringify(tag)})].find((e) => (e.textContent || '').includes(${JSON.stringify(text)}) && e.offsetParent !== null)`;
export const hasText = (text) => `document.body.innerText.includes(${JSON.stringify(text)})`;
// The input, textarea, select, or combobox button of the form field with this label.
export const byLabel = (label) => `(() => { const l = [...document.querySelectorAll('label')].find((e) => (e.textContent || '').replace(/[*\\s]+$/, '').trim() === ${JSON.stringify(label)} && e.offsetParent !== null); if (!l) return null; const c = 'input, textarea, select, button[role=combobox], [contenteditable=true]'; const t = l.htmlFor && document.getElementById(l.htmlFor); return (t && (t.matches(c) ? t : t.querySelector(c))) || l.querySelector(c) || l.parentElement.querySelector(c) || l.parentElement.parentElement.querySelector(c); })()`;
// An open dropdown or combobox option.
// An option can have a description after its name ("Number" + "Integer or decimal"). An exact match wins.
export const option = (text) => `(() => { const all = [...document.querySelectorAll('[role=option], [cmdk-item]')].filter((e) => e.offsetParent !== null); const t = (e) => (e.textContent || '').trim(); return all.find((e) => t(e) === ${JSON.stringify(text)}) || all.find((e) => t(e).startsWith(${JSON.stringify(text)})); })()`;
// A condition for waitFor: the text is on the page and no skeleton placeholder is left.
export const loaded = (text) => `(${hasText(text)} && !document.querySelector('[data-slot=skeleton], .animate-pulse'))`;

function readNarration(project) {
  const file = path.join(project, 'audio', 'vo', 'manifest.json');
  return fs.existsSync(file) ? JSON.parse(fs.readFileSync(file, 'utf8')) : {};
}
