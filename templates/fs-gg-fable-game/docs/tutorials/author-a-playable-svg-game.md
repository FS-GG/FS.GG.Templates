# Author and run a playable SVG game

Build the workspace with `bash ./build.sh`, then serve Studio from `SvgFoundation/Studio`
using its Vite configuration. Choose **Start blank game**, then **Draw playable vector
shapes**. The document is still visual-only at this point.

Choose **Assign gameplay roles** to bind arena, collectible, hazard, goal, barrier, and
player roles. Choose **Define interaction and win rules** to accept the supported rule
strings. **Play edited arena step** freezes the accepted document and metadata as one
immutable schema-3 definition. Use the directional and interaction controls to collect,
reach the goal, and restart. Arrange-mode edits cancel the transient preview.

Choose **Save scene in browser**, open a new page, and wait for **Persisted scene
loaded**. Choose **Export playable arena content** and start the published authority:

```bash
ArenaContentPath=/absolute/path/arena-content.v3.json \
  dotnet artifacts/authority-server/Server.dll --urls http://127.0.0.1:5300
```

Two browsers at that origin receive the same content identity and full V3 snapshot.
V2 clients explicitly refuse schema-3 content and may reconnect with V3; V1 remains
the independent legacy position-only contract.
