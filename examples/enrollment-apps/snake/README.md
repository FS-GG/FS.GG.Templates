# Snake browser sample

Open `index.html` through a static web server, select **Start**, and steer with the arrow keys or W A S D. Space or P pauses and resumes. The app is browser-native ESM and has no runtime dependencies or backend.

The board is a fixed 32 × 18 grid. Every run starts with a three-cell snake at `(16,9)`, a fixed seed of `633`, a score of zero, and a 180 ms step. Food adds one cell and 10 points; each food reduces the step by 6 ms to a 60 ms floor. The explicit seed and row-major free-cell selection make restart and input traces reproducible.

Run the pure reducer suite from this directory:

```console
node --test domain.test.mjs
```

The shared enrollment-app harness owns the static server and Playwright configuration. It serves this directory at `/snake/`; `snake.spec.mjs` loads that real entry point and uses only visible controls and keyboard input. It includes a retained real-clock timer smoke plus deterministic clock-driven journeys for growth, turn buffering, pause, collision, restart, self-collision, and a small viewport.
