# Generated neutral replay rules

The Studio rule explorer uses the same accepted/predicted split and energy dependency represented by this bounded model.

```quint energy-rules.qnt +=
module GeneratedEnergyRules {
  type State = { acceptedEnergy: int, acceptedDoorOpen: bool, predictedEnergy: int, predictedDoorOpen: bool }
  pure val initialState = { acceptedEnergy: 2, acceptedDoorOpen: false, predictedEnergy: 2, predictedDoorOpen: false }

  var state: State

  action init = state' = initialState

  action predictEnterDoor = all {
    state.predictedEnergy > 0,
    not(state.predictedDoorOpen),
    state' = { ...state, predictedEnergy: state.predictedEnergy - 1, predictedDoorOpen: true },
  }

  action cancelPrediction = state' = {
    ...state,
    predictedEnergy: state.acceptedEnergy,
    predictedDoorOpen: state.acceptedDoorOpen,
  }
}
```
