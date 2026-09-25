module FsGgTemplates.ProviderComposition

open System
open System.Text.RegularExpressions

type Provider = {
    Name: string
    ContractVersion: string
    TemplateId: string
    Source: string
    Floor: string option
    File: string
    Line: int
}

type Refusal =
    | EmptySelection
    | InvalidProvider of string
    | DuplicateProvider of string
    | UnorderedProviders
    | UnknownProvider of string
    | MissingFloor of string
    | InvalidFloor of string
    | InvalidRegistryFloor of string
    | RegistryFloorMismatch of string * string * string
    | DifferentProvider of string

let describe = function
    | EmptySelection -> "no providers selected"
    | InvalidProvider name -> $"invalid provider '{name}'"
    | DuplicateProvider name -> $"duplicate provider '{name}'"
    | UnorderedProviders -> "providers must be ordered by name"
    | UnknownProvider name -> $"unknown provider '{name}'"
    | MissingFloor name -> $"provider '{name}' has no minimumFsggSdd.version"
    | InvalidFloor name -> $"provider '{name}' has an invalid minimumFsggSdd.version"
    | InvalidRegistryFloor pin -> $"registry floor '{pin}' is not a version"
    | RegistryFloorMismatch(name, floor, pin) -> $"provider '{name}' floor {floor} != registry pin {pin}"
    | DifferentProvider name -> $"provider '{name}' differs from source descriptor"

let private namePattern = Regex("^[a-z][a-z0-9-]*$", RegexOptions.CultureInvariant)
let private versionPattern = Regex("^\\d+\\.\\d+\\.\\d+(?:[-+].*)?$", RegexOptions.CultureInvariant)

let private validateSet (providers: Provider list) =
    if List.isEmpty providers then Error EmptySelection
    else
        let invalid =
            providers
            |> List.tryFind (fun p ->
                not (namePattern.IsMatch p.Name)
                || String.IsNullOrWhiteSpace p.ContractVersion
                || String.IsNullOrWhiteSpace p.TemplateId
                || String.IsNullOrWhiteSpace p.Source)
        match invalid with
        | Some p -> Error(InvalidProvider p.Name)
        | None ->
            let names = providers |> List.map _.Name
            match names |> List.countBy id |> List.tryFind (fun (_, count) -> count > 1) with
            | Some(name, _) -> Error(DuplicateProvider name)
            | None when names <> List.sort names -> Error UnorderedProviders
            | None ->
                match providers |> List.tryFind (fun p -> p.Floor.IsNone) with
                | Some p -> Error(MissingFloor p.Name)
                | None ->
                    match providers |> List.tryFind (fun p -> not (versionPattern.IsMatch p.Floor.Value)) with
                    | Some p -> Error(InvalidFloor p.Name)
                    | None -> Ok providers

/// Check a requested descriptor against the owner-authored source set. The caller has already
/// parsed the descriptors; this pure step neither reads a registry nor writes a workspace.
let select (known: Provider list) (requested: Provider list) : Result<Provider list, Refusal> =
    // Descriptor files are enumerated by filename, which need not match provider-name order.
    // Only the authored provider sequence inside a requested descriptor has an order contract.
    match validateSet (known |> List.sortBy _.Name), validateSet requested with
    | Error issue, _ -> Error issue
    | _, Error issue -> Error issue
    | Ok source, Ok selection ->
        let sourceByName = source |> List.map (fun p -> p.Name, p) |> Map.ofList
        let rec compare = function
            | [] -> Ok selection
            | item :: rest ->
                match sourceByName.TryFind item.Name with
                | None -> Error(UnknownProvider item.Name)
                | Some original when
                    item.ContractVersion <> original.ContractVersion
                    || item.TemplateId <> original.TemplateId
                    || item.Source <> original.Source
                    || item.Floor <> original.Floor
                    -> Error(DifferentProvider item.Name)
                | Some _ -> compare rest
        compare selection

/// Bind an owner-authored selection to the org registry floor. Every known provider is
/// checked, including those omitted from this particular workspace selection.
let selectAtRegistryFloor (pin: string) (known: Provider list) (requested: Provider list)
    : Result<Provider list, Refusal> =
    if String.IsNullOrWhiteSpace pin || not (versionPattern.IsMatch pin) then Error(InvalidRegistryFloor pin)
    else
        match select known requested with
        | Error issue -> Error issue
        | Ok selection ->
            match known |> List.tryFind (fun provider -> provider.Floor.Value <> pin) with
            | Some provider -> Error(RegistryFloorMismatch(provider.Name, provider.Floor.Value, pin))
            | None -> Ok selection

/// The effective-provider block is an exact text projection of an already validated selection.
let renderEffective (selection: Provider list) =
    [ "# Effective providers — generated; ordered by unique provider name."
      "# Review this block for the current selection; the release narrative remains in PIN HISTORY." ]
    @ (selection
       |> List.mapi (fun index provider ->
           $"# effective[{index + 1}]: name={provider.Name} | template={provider.TemplateId} | source={provider.Source} | contract={provider.ContractVersion}"))
