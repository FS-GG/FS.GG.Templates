module SvgTacticalCorrespondence {
  import SvgTacticalRules as Rules
  var phase: int
  var observed: Rules::State
  action init = all { phase' = 0, observed' = Rules::initialState }
  action step = any {
    all { phase == 0, observed.phase == "ready", phase' = 1, observed' = Rules::planNext(observed) },
    all { phase == 1, observed.phase == "planned", observed.predictedCol != observed.acceptedCol, phase' = 2, observed' = Rules::compareNext(observed) },
    all { phase == 2, observed.phase == "compared", phase' = 3, observed' = Rules::cancelNext(observed) },
    all { phase == 3, observed.phase == "cancelled", phase' = 4, observed' = Rules::planNext(observed) },
    all { phase == 4, observed.phase == "planned", phase' = 5, observed' = Rules::commitNext(observed) },
    all { phase == 5, observed.recorded, phase' = 6, observed' = Rules::reviewNext(observed) },
    all { phase == 6, phase' = 7, observed' = Rules::initialState },
    all { phase == 7, observed.phase == "ready", phase' = 8, observed' = Rules::planNext(observed) },
    all { phase == 8, observed.phase == "planned", observed.predictedCol > observed.acceptedCol, phase' = 9, observed' = Rules::simulateNext(observed) },
    all { phase == 9, observed.phase == "simulated", observed.predictedCol > observed.acceptedCol, phase' = 10, observed' = Rules::simulateNext(observed) },
    all { phase == 10, observed.recorded, phase' = 11, observed' = Rules::reviewNext(observed) },
  }
}
