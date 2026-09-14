# Selected example playground

Select `tactical`, `arcade`, or `complete` when materializing the template. Tactical
loads a bounded 10×6 authored grid. Plan a route, compare it, cancel without changing
accepted state, plan again, and commit. Review seeks the inputs actually committed to
the Room reducer; the explanation names the selected unit, target, and occupied unit.

Arcade runs continuously while the player is still. Hold a directional control from
keyboard, pointer, touch, or a connected gamepad. Releasing its source, returning axes
to neutral, disconnecting, or losing focus clears that source. Pause freezes fixed-step
motion. Hazard entry reduces health, a second entry reaches loss, terminal input
preserves state, and restart restores the authored spawn and health.

The complete bundle shows both examples alongside the production player. Their session
and compatibility identities are separate; neither example rewrites authority state.
