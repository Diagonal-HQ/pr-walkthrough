# Motion rules

Static framing keeps the viewer focused on the product.

## Default

Each shot is the full 1920x1080 frame, and it does not move. The capture viewport is 1440x810 CSS pixels at device scale 2, so the UI is 1.33 times larger in the frame than on a 1920-wide screen. Most text is readable without a zoom.

The edit has no drift, no slow push, no parallax, no motion blur, and no bounce. Cards fade in and out in 8 frames; their content does not move. A cut between two clips is a hard cut.

## When a move is permitted

A move is a `zoom` or a `highlight`. One of these facts must be true, and the `reason` must state it:

| Code | Fact | Use |
| --- | --- | --- |
| READ | The narrator reads or names text that is less than 24 px tall in the 1080p frame (18 CSS px at the default viewport). | `zoom` |
| POINT | The narrator names one region that is less than 15% of the frame, and 3 or more similar elements compete with it. | `highlight` first. `zoom` only if the region also meets READ. |

Prefer a fix that needs no move:

1. Put the cursor on the element. The cursor is the pointer.
2. Make the subject larger in the product: scroll it to the middle, open the detail page, or collapse the sidebar off camera.
3. Use a `highlight`. The camera stays still.
4. Use a `zoom` last.

## These are not reasons

- To add energy, variety, or polish, or to keep the video "alive".
- Because the shot is long. A static frame while the narrator speaks is correct.
- Because the user clicked. A click is not a reason to zoom.
- Because the line changed. Framing follows the screen, not the sentence.
- Because a different video does it.

`build_timeline.py` refuses a move with no reason, or with a reason shorter than 25 characters. It cannot judge the reason. The deletion pass does that.

## How to state a reason

Write one sentence with the measured fact and what the narrator does with it:

- Good: `"The status badge is 12 px tall and the narrator reads its value."`
- Good: `"Six rows look the same; the narrator names only the Overdue row."`
- Bad: `"Draw attention to the status."` (No fact. Why does the viewer need help?)
- Bad: `"Zoom for emphasis."`

Measure before you write. In the scene, `await d.rect(find)` returns the element size in CSS pixels. Multiply by 1.33 for the size in the frame.

## Limits

`build_timeline.py` enforces each limit. Use these limits to keep movement sparse.

| Limit | Value |
| --- | --- |
| Zoom scale | 1.2 to 1.6. Use the lowest scale that makes the text readable. |
| Target size at full zoom | 88% of the frame at most |
| First move | Not before 5 s. The viewer must see the full layout first. |
| Settle before a move | 0.5 s of static frame after the line starts, and 0.2 s after the target is on the screen |
| Zoom in | 0.8 s, cubic ease in and out, no overshoot |
| Zoom out | 0.6 s, same curve. Or `"release": "cut"` when the next shot is a different clip or a card. |
| Hold at full zoom | 2.0 s at least |
| Static time between two moves | 4.0 s at least |
| Moves | 3 for each minute (`feature-clip`, `code-walkthrough`), 4 for each minute (`product-walkthrough`) |
| Runtime in motion | 10% at most |
| Page change | No move while the page changes. A move stays in one clip and does not continue through a card. |

## `move` fields

```json
"move": {
  "type": "zoom",
  "target": "status-badge",
  "scale": 1.4,
  "until": "status_2",
  "reason": "The status badge is 12 px tall and the narrator reads its value."
}
```

| Field | Meaning |
| --- | --- |
| `type` | `zoom` or `highlight` |
| `target` | A name that the scene recorded with `await d.target('<name>', find)` in the beat where the move starts. The edit frames the element from its real rectangle. Do not guess coordinates. |
| `scale` | Zoom only. Default 1.35. |
| `until` | The id of the last line of the move. Default: the same line. Use it to hold a zoom through two lines about the same region. Do not zoom out and in again. |
| `release` | `"cut"` ends the move with the cut at the end of the line. Default: zoom out before the line ends. |
| `at` | Seconds after the line starts. Default and minimum 0.5. |
| `reason` | Required. See above. |

## Deletion pass

Do the motion deletion pass of [the quality review](rendering.md#quality-review) before each render, on the stills of `render.py --stills`, and again on the rendered file. A video with zero moves is a correct result.
