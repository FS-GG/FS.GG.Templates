module FableGameWorkspaceNamespace.SoldierWorkload

open FS.GG.UI.Scene

[<RequireQualifiedAccess>]
type Faction = Blue | Amber
[<RequireQualifiedAccess>]
type Pose = Ready | March | Kneel

type Soldier =
    { Id: string; Faction: Faction; Pose: Pose; Health: int
      Position: Point; FacingDegrees: float }

type Workload =
    { Version: int; Seed: int; AuthorityRevision: int; DefinitionRevision: int
      Soldiers: Soldier list }

type Presentation =
    { Revision: int; Camera: SvgAffine; Selected: string option; Focused: string option }

type State = { Workload: Workload; Presentation: Presentation }

[<RequireQualifiedAccess>]
type Command =
    | Move of id: string * position: Point * facingDegrees: float
    | ChangePose of id: string * pose: Pose
    | ChangeAppearance of id: string * faction: Faction * health: int
    | Spawn of Soldier
    | Remove of id: string
    | ReviseDefinitions of revision: int
    | Select of id: string option
    | Focus of id: string option
    | Camera of SvgAffine

let version = 1
let seed = 1729
let maxSoldiers = 2000
let maxCommands = 128
let visibleCounts = [ 1; 100; 250; 500; 1000 ]
let updatePercentages = [ 10; 50; 100 ]
let cameraRoute = [ (0., 0.); (320., 0.); (320., 240.); (0., 240.); (0., 0.) ]
let private finite value = not (System.Double.IsNaN value || System.Double.IsInfinity value)
let private coordinate value = finite value && abs value <= 1000000.
let private validId (id: string) =
    not (System.String.IsNullOrEmpty id) && id.Length <= 48
    && (id |> Seq.forall (fun c ->
        (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c = '-'))

let validateSoldier (soldier: Soldier) =
    [ if not (validId soldier.Id) then "invalid-id"
      if soldier.Health < 0 || soldier.Health > 100 then "invalid-health"
      if not (coordinate soldier.Position.X && coordinate soldier.Position.Y) then "invalid-position"
      if not (finite soldier.FacingDegrees) || abs soldier.FacingDegrees > 360000. then "invalid-facing" ]

let validate (workload: Workload) =
    // Bounded traversal refuses excessive input before geometry/projection work.
    let bounded = workload.Soldiers |> List.truncate (maxSoldiers + 1)
    [ if workload.Version <> version then "unsupported-version"
      if workload.Seed < 0 || workload.Seed > 1000000 then "invalid-seed"
      if workload.AuthorityRevision < 0 then "invalid-authority-revision"
      if workload.DefinitionRevision < 1 || workload.DefinitionRevision > 2 then "invalid-definition-revision"
      if bounded.Length > maxSoldiers then "too-many-soldiers"
      if (bounded |> List.map _.Id |> Set.ofList |> Set.count) <> bounded.Length then "duplicate-id"
      for soldier in bounded do yield! validateSoldier soldier ]

let initial visibleCount worldCount =
    if not (List.contains visibleCount visibleCounts || visibleCount = 200)
       || worldCount < visibleCount || worldCount > maxSoldiers then Error [ "invalid-counts" ]
    else
        let soldiers =
            [ for index in 0 .. worldCount - 1 do
                let visible = index < visibleCount
                let local = if visible then index else index - visibleCount
                yield
                    { Id = sprintf "soldier-%04d" index
                      Faction = if index % 2 = 0 then Faction.Blue else Faction.Amber
                      Pose = Pose.Ready; Health = 100 - index % 51
                      Position = { X = (if visible then 64. else 10000.) + float (local % 25) * 64.
                                   Y = 64. + float (local / 25) * 80. }
                      FacingDegrees = float ((index * 37 + seed) % 360) } ]
        Ok { Workload = { Version = version; Seed = seed; AuthorityRevision = 0
                          DefinitionRevision = 1; Soldiers = soldiers }
             Presentation = { Revision = 0; Camera = SvgAffine.identity; Selected = None; Focused = None } }

let private validPresentation (state: State) =
    let ids = state.Workload.Soldiers |> List.map _.Id |> Set.ofList
    let known value = value |> Option.forall (fun id -> Set.contains id ids)
    state.Presentation.Revision >= 0 && known state.Presentation.Selected && known state.Presentation.Focused
    && (SvgAffine.tryInverse state.Presentation.Camera |> Result.isOk)

let validateState state =
    let issues = validate state.Workload
    if not issues.IsEmpty then issues
    elif validPresentation state then [] else [ "invalid-presentation" ]

let tryApply command state =
    let refuse issues = state, Some issues
    let accept candidate =
        match validateState candidate with
        | [] -> candidate, None
        | issues -> refuse issues
    let authority workload =
        if state.Workload.AuthorityRevision = System.Int32.MaxValue then refuse [ "revision-overflow" ]
        else accept { state with Workload = { workload with AuthorityRevision = state.Workload.AuthorityRevision + 1 } }
    let presentation value =
        if state.Presentation.Revision = System.Int32.MaxValue then refuse [ "revision-overflow" ]
        else accept { state with Presentation = { value with Revision = state.Presentation.Revision + 1 } }
    let update id change =
        if state.Workload.Soldiers |> List.exists (fun soldier -> soldier.Id = id) then
            authority { state.Workload with Soldiers = state.Workload.Soldiers |> List.map (fun s -> if s.Id = id then change s else s) }
        else refuse [ "unknown-id" ]
    match validateState state with
    | issue :: issues -> refuse (issue :: issues)
    | [] ->
        match command with
        | Command.Move(id, position, facing) -> update id (fun s -> { s with Position = position; FacingDegrees = facing })
        | Command.ChangePose(id, pose) -> update id (fun s -> { s with Pose = pose })
        | Command.ChangeAppearance(id, faction, health) -> update id (fun s -> { s with Faction = faction; Health = health })
        | Command.Spawn soldier -> authority { state.Workload with Soldiers = state.Workload.Soldiers @ [ soldier ] }
        | Command.Remove id ->
            if not (state.Workload.Soldiers |> List.exists (fun s -> s.Id = id)) then refuse [ "unknown-id" ]
            elif state.Workload.AuthorityRevision = System.Int32.MaxValue || state.Presentation.Revision = System.Int32.MaxValue then refuse [ "revision-overflow" ]
            else
                let survivors = state.Workload.Soldiers |> List.filter (fun s -> s.Id <> id)
                let focus = if state.Presentation.Focused = Some id then survivors |> List.tryHead |> Option.map _.Id else state.Presentation.Focused
                accept { Workload = { state.Workload with Soldiers = survivors; AuthorityRevision = state.Workload.AuthorityRevision + 1 }
                         Presentation = { state.Presentation with Revision = state.Presentation.Revision + 1
                                                                  Focused = focus
                                                                  Selected = if state.Presentation.Selected = Some id then None else state.Presentation.Selected } }
        | Command.ReviseDefinitions revision -> authority { state.Workload with DefinitionRevision = revision }
        | Command.Select id -> presentation { state.Presentation with Selected = id }
        | Command.Focus id -> presentation { state.Presentation with Focused = id }
        | Command.Camera camera -> presentation { state.Presentation with Camera = camera }

let tryApplyBatch commands state =
    let bounded = commands |> List.truncate (maxCommands + 1)
    if not (validateState state).IsEmpty then state, Some (validateState state)
    elif bounded.Length > maxCommands then state, Some [ "too-many-commands" ]
    else
        let rec loop current remaining =
            match remaining with
            | [] -> current, None
            | command :: tail ->
                match tryApply command current with
                | next, None -> loop next tail
                | _, Some issues -> state, Some issues
        loop state bounded

// Seeded rank fixes the update population independently of input ordering; each ID has its own motion.
let updatedSoldiers percentage workload =
    if not (List.contains percentage updatePercentages) then Error [ "invalid-percentage" ]
    else
        match validate workload with
        | issue :: issues -> Error (issue :: issues)
        | [] ->
            let count = workload.Soldiers.Length * percentage / 100
            let ranked = workload.Soldiers |> List.sortBy (fun s ->
                let rank = s.Id |> Seq.fold (fun value c -> (value * 31 + int c) % 100003) workload.Seed
                rank, s.Id)
            let ranks = ranked |> List.mapi (fun index soldier -> soldier.Id, index) |> Map.ofList
            let ids = ranked |> List.truncate count |> List.map _.Id |> Set.ofList
            let soldiers = workload.Soldiers |> List.map (fun s ->
                if Set.contains s.Id ids then
                    let index = Map.find s.Id ranks
                    { s with Position = { X = s.Position.X + float (1 + index % 7); Y = s.Position.Y + float (1 + index % 5) }
                             FacingDegrees = (s.FacingDegrees + float (3 + index % 11)) % 360.
                             Pose = if index % 2 = 0 then Pose.March else Pose.Kneel }
                else s)
            if workload.AuthorityRevision = System.Int32.MaxValue then Error [ "revision-overflow" ]
            else
                let candidate = { workload with Soldiers = soldiers; AuthorityRevision = workload.AuthorityRevision + 1 }
                match validate candidate with
                | [] -> Ok candidate
                | issues -> Error issues

let churnCommands =
    [ Command.Select(Some "soldier-0000"); Command.Focus(Some "soldier-0000")
      Command.Move("soldier-0000", { X = 12000.; Y = 40. }, 90.)
      Command.ChangePose("soldier-0001", Pose.Kneel)
      Command.ChangeAppearance("soldier-0001", Faction.Blue, 25)
      Command.Remove "soldier-0000"
      Command.Spawn { Id = "soldier-spawn-0001"; Faction = Faction.Amber; Pose = Pose.March; Health = 80
                      Position = { X = 96.; Y = 40. }; FacingDegrees = 15. }
      Command.ReviseDefinitions 2 ]
