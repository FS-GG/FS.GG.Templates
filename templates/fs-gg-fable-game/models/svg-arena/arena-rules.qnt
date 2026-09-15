// Generated from arena-rules.md. Run scripts/check-svg-arena-model.sh.
module SvgArenaRules {
  type State = {
    health: int,
    score: int,
    collected: bool,
    outcome: str,
    round: int,
    hazardContact: bool,
    lastAction: str,
  }

  pure val initialState = {
    health: 3,
    score: 0,
    collected: false,
    outcome: "playing",
    round: 1,
    hazardContact: false,
    lastAction: "init",
  }

  pure def collectNext(s) = { ...s, collected: true, score: s.score + 100, lastAction: "collect" }
  pure def goalNext(s) = { ...s, outcome: "won", lastAction: "win" }
  pure def hazardEntryNext(s) = { ...s, health: s.health - 1, hazardContact: true, lastAction: "hazard-entry" }
  pure def lethalHazardNext(s) = { ...s, health: 0, outcome: "lost", hazardContact: true, lastAction: "lethal-hazard-entry" }
  pure def hazardStayNext(s) = { ...s, lastAction: "hazard-stay" }
  pure def hazardExitNext(s) = { ...s, hazardContact: false, lastAction: "hazard-exit" }
  pure def restartNext(s) = { ...initialState, round: s.round + 1, lastAction: "restart" }
  pure def terminalRefusalNext(s) = { ...s, lastAction: "terminal-input-refused" }

  var state: State

  action init = state' = initialState

  action collect = all {
    state.outcome == "playing",
    not(state.collected),
    state' = collectNext(state),
  }

  action reachGoal = all {
    state.outcome == "playing",
    state.collected,
    state' = goalNext(state),
  }

  action hazardContact = all {
    state.outcome == "playing",
    not(state.hazardContact),
    state.health > 1,
    state' = hazardEntryNext(state),
  }

  action lethalHazardContact = all {
    state.outcome == "playing",
    not(state.hazardContact),
    state.health == 1,
    state' = lethalHazardNext(state),
  }

  action stayInHazard = all {
    state.outcome == "playing",
    state.hazardContact,
    state' = hazardStayNext(state),
  }

  action exitHazard = all {
    state.outcome == "playing",
    state.hazardContact,
    state' = hazardExitNext(state),
  }

  action restart = state' = restartNext(state)

  action terminalGuard = all {
    state.outcome != "playing",
    // lastAction is model instrumentation. The gameplay projection is unchanged.
    state' = terminalRefusalNext(state),
  }

  action step = any {
    collect,
    reachGoal,
    hazardContact,
    lethalHazardContact,
    stayInHazard,
    exitHazard,
    restart,
    terminalGuard,
  }

  val healthBound = state.health >= 0 and state.health <= 3
  val scoreShape = state.score == 0 or state.score == 100
  val collectedScore = not(state.collected) or state.score == 100
  val wonRequiresCollection = state.outcome != "won" or state.collected
  val terminalOutcome = state.outcome == "playing" or state.outcome == "won" or state.outcome == "lost"
  val hazardContactImpliesDamage = not(state.hazardContact) or state.health < 3

  val witnessCollect = state.collected and state.score == 100
  val witnessWin = state.outcome == "won"
  val witnessLoss = state.outcome == "lost" and state.health == 0
  val witnessRestart = state.round > 1 and state.outcome == "playing" and state.health == 3
  val witnessHazardEntry = state.lastAction == "hazard-entry"
  val witnessHazardStay = state.lastAction == "hazard-stay"
  val witnessTerminalRefusal = state.lastAction == "terminal-input-refused"
}
