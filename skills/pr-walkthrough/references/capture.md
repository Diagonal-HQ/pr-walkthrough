# App setup and capture

Set `WALKTHROUGH_PROJECT` to an ignored output folder. Scenes import `Director` from the absolute skill file URL written by `init`.

## Project configuration

`<project>/walkthrough.json`:

```json
{
  "appUrl": "http://localhost:3000/tasks",
  "repo": "/absolute/path/to/your-app",
  "setup": "setup.mjs",
  "storageState": "auth.json",
  "hide": ["[data-dev-toolbar]"],
  "viewport": {"width": 1440, "height": 810, "scale": 2},
  "headless": true,
  "ignoreHTTPSErrors": false
}
```

All fields are optional. `appUrl` is needed by the standard app scene. `WALKTHROUGH_APP_URL` overrides it. Paths are relative to the video project, except an absolute path stays absolute. Omit `storageState` if there is no saved session. Use `ignoreHTTPSErrors: true` only for a local app with a self-signed certificate.

`await d.prepare()` runs your setup hook, opens the app URL, then hides configured developer-only selectors. It does not guess how to log in. The `setup` module exports an async function:

```javascript
export default async function setup(d) {
  await d.page.goto('http://localhost:3000/login');
  await d.page.getByLabel('Email').fill(process.env.DEMO_EMAIL);
  await d.page.getByLabel('Password').fill(process.env.DEMO_PASSWORD);
  await d.page.getByRole('button', { name: 'Sign in' }).click();
  await d.page.waitForURL('**/tasks');
}
```

`d.page` is a Playwright Page. Use your existing fixture API, seed command, or test helpers in the hook. Do not interpolate user input into shell commands. Seed only the intended test environment. No seed or login commands run unless your hook calls them.

To use an existing test login, create a Playwright storage state file and set `storageState` to its path. Keep it in the ignored project folder. A recording browser is isolated and closes after the scene. Interactive login is also possible with `headless: false`; the scene must wait for a known signed-in page before capture.

## Scene pattern

```javascript
import { Director, byText, hasText } from 'file:///absolute/skill/scripts/director.mjs';
const d = await Director.connect();
try {
  await d.prepare();
  await d.waitFor(hasText('Tasks'));
  await d.startCapture('main');
  await d.beat('open', async () => {
    await d.click(byText('button', 'Open only'));
    await d.waitFor(hasText('3 tasks'));
  });
  await d.beat('result');
  await d.stopCapture();
} finally {
  await d.close();
}
```

Each capture writes `footage/<clip>.mp4` and `<clip>.json`. Each beat id matches one filmed line in `video.json`. Title, section, and end cards do not need capture beats. Use unique beat ids across all scenes. Old clips are not selected by age: delete obsolete clip files and metadata before rebuilding.

## Director API

| Method | Purpose |
| --- | --- |
| `Director.connect(options)` | Launch an isolated Chromium context. Optional project, viewport, and headless settings. |
| `prepare(url?)` | Run setup, open the configured URL, hide configured developer tools. |
| `goto(url)` | Open a page and wait for load. Also wait for the specific app content you need. |
| `eval(expression)` | Evaluate trusted scene JavaScript in the page. |
| `waitFor(expression, timeout=15000)` | Wait for a page expression to become true. |
| `startCapture(name)` / `stopCapture()` | Start and finish one clip. |
| `beat(id, action?)` | Run actions, then hold until the narration line ends. |
| `click(find)` / `hover(find)` | Move the visible cursor to an element expression, then click or hover. |
| `type(text, per=75)` | Type with a short delay per character. |
| `key(key, code?, keyCode?)` | Send a keyboard key. For Escape, use `key('Escape', 'Escape', 27)`. |
| `moveTo(x,y,ms?)` | Move the visible cursor in CSS pixels. |
| `scroll(dy,ms?)` / `scrollTo(find,ms?)` | Show a scroll on camera. |
| `skip(asyncWait)` | Remove a loading wait from capture. Do not skip meaningful user actions. |
| `lineEnd(seconds=1.5)` | Hold until the line has this much time left. Useful before a page-changing click. |
| `target(name,find)` | Record a real element rectangle for an optional camera move. |
| `hide(find)` | Hide developer-only elements. Do not hide product behavior. |
| `sleep(ms)` / `close()` | Hold the frame / close the browser. Always await close in finally. |

Finders return JavaScript expressions: `byText(tag,text)`, `byTextIn(tag,text)`, `byLabel(label)`, and `option(text)`. Conditions: `hasText(text)` and `loaded(text)` (also checks for common skeletons).

The default viewport is 1440×810 CSS pixels at 2× scale. The final picture is 1920×1080. Keep the same aspect ratio if changing the viewport. Rectangles for camera targets use CSS pixels.

Warm slow pages off camera. Wait for meaningful content after each navigation. Keep the cursor away from text being read. If an action outlasts its narration, shorten the action or rewrite the line; do not speed up the footage.
