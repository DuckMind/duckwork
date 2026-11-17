---
name: sketch-pad
description: >
  Use when the user confirmed a Sketch Pad drawing and asks what the shape is,
  or points at "the sketch". Load with skill_view("sketch-pad:sketch-pad").
---

# sketch-pad

The user draws on the Desktop **Sketch Pad** pane and presses Confirm. The PNG
is attached to their **next chat send** and saved under `$DUCKWORK_HOME/images/`
(the same folder Desktop clipboard uploads use).

## When to use

- User: "bu ne", "what did I draw", "this shape"
- Prefer the image already attached on the user message
- If you need a path: `sketch_pad_last`, then `vision_analyze` with `image_url`
  set to that `path` (a local file under `images/`, not a URL)
- Do not invent a description of a drawing you cannot see
- Do not start `http.server`, curl localhost, or rewrite the path as `http://`
