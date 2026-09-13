# SVG input generated-candidate boundary

The opt-in SVG payload now composes two product-owned profiles over Rendering's portable resolver and
browser adapter. The player entry maps three semantic game commands to retained focus and activation.
The separate Studio entry maps workspace modes, palette/help, sequences, displacement-aware rebinding,
pointer, touch and gamepad actions to `SvgStudioHost` state. Responsive dock changes remain workspace
state and do not alter scene, history, camera or selection.

`scripts/stage-rendering-input-packet.sh` packs KeyboardInput, Scene and Scene.SvgBrowser from one exact
Rendering revision using a unique `0.30.0-svg-input.1.<revision>` identity. Its manifest binds every
archive, the required input Fable interfaces, browser resources and npm lock, and the accepted Quint
model, extraction receipt and typed authority. `scripts/stage-svg-input-candidate.sh` verifies that
packet before producing the private `0.12.0-svg-input.1` template. Public Templates `0.11.0` and
Rendering `0.29.0` pins stay unchanged.

Run the installed closure with:

```bash
SVG_SCENE_ORCA_OBSERVATION=/absolute/generated-input-orca.json \
  bash tests/composition/fable-game/verify-svg-input-candidate.sh \
  /absolute/rendering-input-packet /absolute/empty-output
```

Qualification generates the direct route, SDD 1.7.0 none/default/typed routes, the pinned wizard 0.11.1
adopter and retained 0.10/0.11 receivers. It refuses managed collisions before writes, rolls interrupted
application back, restores managed bytes exactly and preserves lifecycle provenance and authored content.
The player bundle is checked for the small input adapter and against Studio, workspace and geometry
modules. Chromium, Firefox and WebKit exercise both player and Studio entries; Orca/AT-SPI operates the
mode, palette, help and rebind controls and observes their live feedback.

The generated qualification packet records the exact producer and Templates source revisions, archive,
Fable interface and payload identities, browser observations, model evidence and retained baselines.
This is the Preview-B handoff for SVG-INPUT-01; publication and default activation remain pending the
runtime and presentation features.
