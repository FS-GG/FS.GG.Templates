# Arcade example

This editable example uses the same continuous arena reducer as the default player. Start with
`ContinuousPlayer.fs` to change movement, collision, collectibles, health, score, sound, and the
win/restart loop; package-owned engine code remains outside the authored source tree.

`scene.json` is the editable content seed shared with Studio; it describes the continuous arena,
collectible, moving hazard, goal, and commands without copying the package runtime.
