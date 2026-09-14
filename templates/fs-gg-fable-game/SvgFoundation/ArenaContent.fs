module FableGameWorkspaceNamespace.ArenaContent

/// Editable product content shared by the production player and Studio.
let arenaWidth = 220.0
let arenaHeight = 120.0
let playerStartX = 12.0
let playerStartY = 54.0
let collectibleX = 60.0
let collectibleY = 27.0
let hazardBaseX = 80.0
let hazardY = 78.0
let goalX = 175.0
let goalY = 48.0

let movingHazardX revision =
    hazardBaseX + float (int (revision % 40UL) - 20) * 0.75
