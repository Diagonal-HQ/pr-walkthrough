import { Director, byText, hasText } from '__SKILL_URL__/scripts/director.mjs';
const d = await Director.connect();
try {
  await d.prepare();
  // Replace the selectors and beats with the real flow after exploring your app.
  await d.waitFor(hasText('Tasks'));
  await d.startCapture('main');
  await d.beat('s1');
  await d.beat('s2', async () => {
    await d.click(byText('button', 'Open only'));
  });
  await d.beat('result');
  console.log(JSON.stringify(await d.stopCapture(), null, 2));
} finally {
  await d.close();
}
