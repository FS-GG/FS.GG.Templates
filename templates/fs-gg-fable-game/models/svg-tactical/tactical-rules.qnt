// Generated from tactical-rules.md. Run scripts/check-svg-tactical-model.sh.
module SvgTacticalRules {
  type State = {
    phase: str,
    acceptedCol: int,
    predictedCol: int,
    committedCol: int,
    recorded: bool,
  }

  pure val initialState = { phase: "ready", acceptedCol: 1, predictedCol: 1, committedCol: 1, recorded: false }

  pure def planNext(s) = { ...s, phase: "planned", predictedCol: 5 }
  pure def compareNext(s) = { ...s, phase: "compared" }
  pure def cancelNext(s) = { ...s, phase: "cancelled", predictedCol: s.acceptedCol }
  pure def commitNext(s) = { ...s, phase: "committed", acceptedCol: s.predictedCol,
    committedCol: s.predictedCol, recorded: true }
  pure def simulateNext(s) = { ...s, phase: "simulated", acceptedCol: s.acceptedCol + 1,
    committedCol: s.acceptedCol + 1, recorded: true }
  pure def reviewNext(s) = { ...s, phase: "reviewed" }

  var state: State
  action init = state' = initialState

  action plan = state' = planNext(state)

  action compare = all {
    state.phase == "planned",
    state.predictedCol != state.acceptedCol,
    state' = compareNext(state),
  }

  action cancel = all {
    state.phase == "planned" or state.phase == "compared",
    state' = cancelNext(state),
  }

  action commit = all {
    state.phase == "planned" or state.phase == "compared",
    state' = commitNext(state),
  }

  action simulate = all {
    state.phase == "planned" or state.phase == "simulated",
    state.predictedCol > state.acceptedCol,
    state' = simulateNext(state),
  }

  action review = all {
    state.recorded,
    state' = reviewNext(state),
  }

  action reset = state' = initialState

  action step = any { plan, compare, cancel, commit, simulate, review, reset }

  val columnsInBounds = state.acceptedCol >= 0 and state.acceptedCol < 10 and
    state.predictedCol >= 0 and state.predictedCol < 10 and
    state.committedCol >= 0 and state.committedCol < 10
  val commitAgrees = state.phase != "committed" or state.acceptedCol == state.committedCol
  val cancelPreservesAccepted = state.phase != "cancelled" or state.acceptedCol == state.committedCol
  val reviewHasRecording = state.phase != "reviewed" or state.recorded
  val witnessCompare = state.phase == "compared"
  val witnessCancel = state.phase == "cancelled"
  val witnessCommit = state.phase == "committed"
  val witnessSimulate = state.phase == "simulated"
  val witnessReview = state.phase == "reviewed"
}
