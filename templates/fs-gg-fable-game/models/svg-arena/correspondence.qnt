module SvgArenaCorrespondence {
  import SvgArenaRules as Rules

  var phase: int
  var observed: Rules::State

  action init = all { phase' = 0, observed' = Rules::initialState }
  action step = any {
    all { phase == 0, observed.outcome == "playing", not(observed.collected), phase' = 1, observed' = Rules::collectNext(observed) },
    all { phase == 1, observed.outcome == "playing", observed.collected, phase' = 2, observed' = Rules::goalNext(observed) },
    all { phase == 2, observed.outcome != "playing", phase' = 3, observed' = Rules::terminalRefusalNext(observed) },
    all { phase == 3, phase' = 4, observed' = Rules::restartNext(observed) },
    all { phase == 4, observed.outcome == "playing", not(observed.hazardContact), observed.health > 1, phase' = 5, observed' = Rules::hazardEntryNext(observed) },
    all { phase == 5, observed.outcome == "playing", observed.hazardContact, phase' = 6, observed' = Rules::hazardStayNext(observed) },
    all { phase == 6, observed.outcome == "playing", observed.hazardContact, phase' = 7, observed' = Rules::hazardExitNext(observed) },
    all { phase == 7, observed.outcome == "playing", not(observed.hazardContact), observed.health > 1, phase' = 8, observed' = Rules::hazardEntryNext(observed) },
    all { phase == 8, observed.outcome == "playing", observed.hazardContact, phase' = 9, observed' = Rules::hazardExitNext(observed) },
    all { phase == 9, observed.outcome == "playing", not(observed.hazardContact), observed.health == 1, phase' = 10, observed' = Rules::lethalHazardNext(observed) },
    all { phase == 10, phase' = 11, observed' = Rules::restartNext(observed) },
  }
}
