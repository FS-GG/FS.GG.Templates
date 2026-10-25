/// Bounded text codec for the synthetic reference only; not a product save format.
module FableGameWorkspaceNamespace.SvgFoundation.LocalSaveReplayCodec

open System
open FS.GG.Game.Core
open FableGameWorkspaceNamespace.SvgFoundation.LocalSaveReplayExample

let maximumCharacters = 32768
let maximumAccepted = 256
let private format = "fsgg.synthetic.fourd.save/1"

let private cellText (cell: FullCell) =
    String.concat ":" [ string cell.A; string cell.B; string cell.C; string cell.D ]

let private textField (value: string) =
    if String.IsNullOrEmpty value || value.Length > 128 || value.Contains '\n' || value.Contains '\r' then
        invalidArg "snapshot" "Invalid synthetic snapshot identity."
    value

/// Decimal strings retain every uint64 bit in .NET and emitted JavaScript.
let encode (snapshot: SessionSnapshot<Payload>) =
    try
        if snapshot.Value.Accepted.Length > maximumAccepted then
            invalidArg "snapshot" "Synthetic save trace exceeds 256 inspections."
        let identity = snapshot.Compatibility
        let trace =
            snapshot.Value.Accepted
            |> List.map (fun (sequence, cell) -> string sequence + "@" + cellText cell)
            |> String.concat ";"
        let value =
            String.concat "\n"
                [ format; textField snapshot.SessionId; string snapshot.Revision
                  string identity.ContractVersion; textField identity.EngineId; textField identity.EngineVersion
                  textField identity.ProfileId; textField identity.SchemaId; string identity.SchemaVersion
                  cellText snapshot.Value.Agent; cellText snapshot.Value.LegalDestination; trace ]
        if value.Length > maximumCharacters then Error "Synthetic save exceeds its character limit."
        else Ok value
    with error -> Error error.Message

let private integer (text: string) =
    let value = Int32.Parse text
    if string value <> text then invalidArg "snapshot" "Noncanonical integer."
    value

let private sequence (text: string) =
    let value = UInt64.Parse text
    if string value <> text then invalidArg "snapshot" "Noncanonical sequence."
    value

let private cell (text: string) : FullCell =
    match text.Split ':' with
    | [| a; b; c; d |] -> { A = integer a; B = integer b; C = integer c; D = integer d }
    | _ -> invalidArg "snapshot" "Expected four signed coordinates."

/// Decode values; SessionRuntime remains the authority for session/schema/revision admission.
let decode (text: string) : Result<SessionSnapshot<Payload>, string> =
    try
        if isNull text || text.Length > maximumCharacters then
            invalidArg "snapshot" "Synthetic save is missing or exceeds its character limit."
        let fields = text.Split '\n'
        if fields.Length <> 12 || fields[0] <> format then
            invalidArg "snapshot" "Unknown synthetic save version or field count."
        let accepted =
            if fields[11] = "" then []
            else
                let entries = fields[11].Split ';'
                if entries.Length > maximumAccepted then
                    invalidArg "snapshot" "Synthetic save trace exceeds 256 inspections."
                entries
                |> Array.map (fun entry ->
                    match entry.Split '@' with
                    | [| order; location |] -> sequence order, cell location
                    | _ -> invalidArg "snapshot" "Malformed inspection trace.")
                |> Array.toList
        Ok
            { SessionId = textField fields[1]
              Revision = sequence fields[2]
              Compatibility =
                { ContractVersion = integer fields[3]
                  EngineId = textField fields[4]; EngineVersion = textField fields[5]
                  ProfileId = textField fields[6]; SchemaId = textField fields[7]
                  SchemaVersion = integer fields[8] }
              Value = { Agent = cell fields[9]; LegalDestination = cell fields[10]; Accepted = accepted } }
    with error -> Error error.Message
