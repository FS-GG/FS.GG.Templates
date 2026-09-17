module FableGameWorkspaceNamespace.SvgFoundation.TacticalRuleModel

let modelId = "svg-tactical-rules/v1"
let modelSha256 = "a335ae4e9d4d7c494da06402be962053dec585150af208a365970186c683711e"
let tool = "quint"
let toolVersion = "0.32.0"

let invariants =
    [
        "columnsInBounds"
        "commitAgrees"
        "cancelPreservesAccepted"
        "reviewHasRecording"
    ]

let implementationBinding =
    "SvgFoundation/TacticalExample.fs:Planning+Room+Replay+RuleCatalog"
