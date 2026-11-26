# Cover image prompt

Use this prompt in an image generator to make a README cover for **PR Video Walkthrough**. The title already appears in the README, so the image does not need generated lettering.

## Copy this prompt

~~~text
Create a wide editorial cover illustration for “PR Video Walkthrough”, a developer tool that turns a code change into a narrated video of the real app.

Art direction: a calm, premium technical publication. Warm ivory background (#F8F3EA), deep forest green (#21382E), muted sage (#B8C8AE), and slate (#314158). Fine architectural grid lines, precise spacing, soft daylight, subtle paper grain, crisp edges, and restrained dimensional depth.

Compose three connected objects across the frame: on the left, a small code-diff card with a simple branching git line; in the center, a short audio waveform aligned to a film timeline; on the right, a larger browser-shaped video frame with a clear play symbol and an abstract, beautifully typeset application interface. A single forest-green path connects the change, the voice, and the finished walkthrough. The browser/video frame is the main focal point. Use abstract interface marks rather than legible source code or product data.

Make the result feel crafted for engineers: confident, quiet, useful, and human. Keep the composition spacious with generous negative space and a balanced silhouette. Use a shallow orthographic perspective and gentle shadows. No people, mascots, robots, corporate logos, watermarks, or decorative text.

Output: 2400 × 1000 pixels, landscape. Keep the important objects within the central 80% so the illustration also crops cleanly to a 1200 × 630 social preview. Deliver only the illustration, with no lettering.
~~~

## Use it in the repository

Save the selected, reviewed image as `docs/assets/cover.png`. Add this above the centered README title only after that file exists:

~~~html
<p align="center">
  <img src="docs/assets/cover.png" alt="A code change flows through narration into an app video" width="100%">
</p>
~~~

For a GitHub social preview, export a separate 1200 × 630 crop. Keep the repo title in the surrounding GitHub UI, or add typography in a design tool for precise lettering. A social preview is separate from the README cover.
