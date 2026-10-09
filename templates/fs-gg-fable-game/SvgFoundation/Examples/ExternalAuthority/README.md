# External command outcomes

The opt-in deterministic reference separates command receipts from presentation
snapshots. It uses an unauthenticated mock gateway and the shared Rendering input
and presentation hosts. It grants no native engine authority.

Mount the reference and connect the sample authority. **Lose next command receipt**
makes the next accepted increment take effect once while its receipt becomes
unknown. The visible status explains why commands are suspended. Projection
completion and reconnect neither settle that receipt nor replay the command.

**Reconcile unknown command** inspects the mock's original accepted reply within
its current authority epoch and generation. **Abandon unknown command** leaves the
outcome unknown. Either action requires **Rearm sample commands** before another
command can run. The new command receives a fresh correlation; the original
unknown receipt remains in the evidence ledger. Rearming alone cannot dismiss an
unresolved outcome.

**Complete delayed command receipt** delivers the captured mock reply without
applying the command again. After authority replacement, an old epoch or generation
cannot reconcile the current recovery state. Abandonment remains explicit.
Disposal clears owned pending replies and makes retained controls inert while
preserving receipt evidence.

The [browser cases](../../../Browser.Tests/external-command-outcomes.spec.ts)
exercise the real page entry, controls, keyboard input, recovery and disposal.
They are declared only when the complete external reference composition is
selected. Source preparation does not establish browser qualification, publication,
installed workspace acceptance or SC2/BAR native receipt semantics.
