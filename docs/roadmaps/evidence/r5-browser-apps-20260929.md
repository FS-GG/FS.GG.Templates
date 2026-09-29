# Four independent browser apps: source qualification

Clean code checkpoint: `4181f1a6dacf92151fff7f6217d045137d4546cc`. Original items: TODO-01.1, TTT-01.1, SNAKE-01.1 and HELLO-01.1, prospectively selected before outcomes at `2026-09-29T06:31:33Z`. Each whole app has its own owning roadmap. This report records source qualification; native delivery and protected readback remain the authority for completion.

The locked root harness stages browser-native HTML/ESM/CSS without transpilation. Every staged asset was compared byte-for-byte with this clean git revision and its SHA-256 manifest. No template/package/default content changes. Actual local Node 26, Playwright 1.63 and Chromium 153 qualification used an isolated loopback server on port4207, one worker and real staged app entry points.

| App | Domain checks | Actual browser checks |
| --- | ---: | --- |
| Todo | 4 | 4: complete task management, persistence/reload, filters, keyboard/narrow layout, literal HTML, invalid saved data and rejected storage |
| Tic-tac-toe | 4 | 2: pointer X/O wins and refusal/restart; complete keyboard draw and narrow layout |
| Snake | 10 | 6: deterministic food/growth/score, queued reversal, pause/blur/no catch-up, wall/self collision, terminal/restart, keyboard/narrow layout and real-clock timer |
| Hello-world | No mirrored trivial unit test | 2: actual module-rendered accessible entry, served assets, reload, desktop/narrow view and zero browser errors |

All 18 domain checks and 14 browser cases passed through the common locked harness. The tic-tac-toe reachable-state oracle checks independent win/draw behavior. Snake uses controls-driven seeded journeys and a retained real-clock smoke; its browser clock control qualifies deterministic timer behavior without hidden game-state injection. Todo's normal persistence journey creates and edits tasks through controls; storage injection is limited to negative corruption/failure cases.

The first joined run found a shared route mismatch for Snake and unhandled favicon requests under strict browser error checks. The integrated route and server fixes are included in this checkpoint; the full staged-output run then passed. These repairs retain the original items and costs.

This is clean source-sample evidence. No installed generated receiver, retained-workspace upgrade, publication, native usage counter or economics claim follows. Native checks and source readback must still pass on the admitted final head, and the applicable ordinary-V2 post-merge settlement is observed separately.
