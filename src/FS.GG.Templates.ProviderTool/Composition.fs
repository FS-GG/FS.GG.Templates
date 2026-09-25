module FsGgTemplates.ProviderComposition

open System
open System.Text
open System.Text.RegularExpressions

type Parameter = {
    Key: string
    Required: bool
    Default: string option
}

type Provider = {
    Name: string
    ContractVersion: string
    TemplateId: string
    Source: string
    NameParameter: string option
    IdentifierParameter: string option
    Floor: string option
    Parameters: Parameter list
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
    | InvalidParameter of string * string
    | DuplicateParameter of string * string
    | UnknownParameter of string * string
    | MissingRequiredParameter of string * string
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
    | InvalidParameter(name, key) -> $"provider '{name}' has an invalid parameter '{key}'"
    | DuplicateParameter(name, key) -> $"provider '{name}' repeats parameter '{key}'"
    | UnknownParameter(name, key) -> $"provider '{name}' does not declare parameter '{key}'"
    | MissingRequiredParameter(name, key) -> $"provider '{name}' requires parameter '{key}'"
    | InvalidRegistryFloor pin -> $"registry floor '{pin}' is not a version"
    | RegistryFloorMismatch(name, floor, pin) -> $"provider '{name}' floor {floor} != registry pin {pin}"
    | DifferentProvider name -> $"provider '{name}' differs from source descriptor"

let private namePattern = Regex(@"\A[a-z][a-z0-9-]*\z", RegexOptions.CultureInvariant)
let private parameterPattern = Regex(@"\A[A-Za-z][A-Za-z0-9]*\z", RegexOptions.CultureInvariant)
let private versionPattern = Regex(@"\A\d+\.\d+\.\d+(?:[-+].*)?\z", RegexOptions.CultureInvariant)
let private packageSourcePattern =
    Regex(
        @"\A[A-Za-z0-9][A-Za-z0-9._-]*::[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?\z",
        RegexOptions.CultureInvariant)

let private safeEffectiveField (value: string) =
    not (String.IsNullOrWhiteSpace value)
    && String.Equals(value, value.Trim(), StringComparison.Ordinal)
    && (value
        |> Seq.forall (fun character ->
            character <> '|' && character <> '\u2028' && character <> '\u2029'
            && not (Char.IsControl character)))

let private validateSet (providers: Provider list) =
    if List.isEmpty providers then Error EmptySelection
    else
        let invalid =
            providers
            |> List.tryFind (fun p ->
                not (namePattern.IsMatch p.Name)
                || not (safeEffectiveField p.ContractVersion)
                || not (safeEffectiveField p.TemplateId)
                || String.IsNullOrWhiteSpace p.Source
                || not (packageSourcePattern.IsMatch p.Source)
                || (p.NameParameter |> Option.exists (fun value -> not (parameterPattern.IsMatch value)))
                || (p.IdentifierParameter |> Option.exists (fun value -> not (parameterPattern.IsMatch value))))
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
                    | None ->
                        let invalidParameter =
                            providers
                            |> List.tryPick (fun provider ->
                                provider.Parameters
                                |> List.tryFind (fun parameter ->
                                    not (parameterPattern.IsMatch parameter.Key)
                                    || (parameter.Default |> Option.exists String.IsNullOrWhiteSpace))
                                |> Option.map (fun parameter -> InvalidParameter(provider.Name, parameter.Key)))
                        match invalidParameter with
                        | Some issue -> Error issue
                        | None ->
                            let duplicateParameter =
                                providers
                                |> List.tryPick (fun provider ->
                                    provider.Parameters
                                    |> List.countBy _.Key
                                    |> List.tryFind (fun (_, count) -> count > 1)
                                    |> Option.map (fun (key, _) -> DuplicateParameter(provider.Name, key)))
                            match duplicateParameter with
                            | Some issue -> Error issue
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
                    || item.NameParameter <> original.NameParameter
                    || item.IdentifierParameter <> original.IdentifierParameter
                    || item.Floor <> original.Floor
                    || item.Parameters <> original.Parameters
                    -> Error(DifferentProvider item.Name)
                | Some _ -> compare rest
        compare selection

/// Resolve only declared parameter keys, applying defaults in declaration order.
let resolveParameters (provider: Provider) (requested: (string * string) list)
    : Result<(string * string) list, Refusal> =
    match validateSet [ provider ] with
    | Error issue -> Error issue
    | Ok _ ->
        let duplicate = requested |> List.countBy fst |> List.tryFind (fun (_, count) -> count > 1)
        match duplicate with
        | Some(key, _) -> Error(DuplicateParameter(provider.Name, key))
        | None ->
            let known = provider.Parameters |> List.map _.Key |> Set.ofList
            match requested |> List.tryFind (fun (key, _) -> not (known.Contains key)) with
            | Some(key, _) -> Error(UnknownParameter(provider.Name, key))
            | None ->
                let supplied = requested |> Map.ofList
                match provider.Parameters |> List.tryFind (fun parameter ->
                    parameter.Required && not (supplied.ContainsKey parameter.Key)
                    && parameter.Default.IsNone) with
                | Some parameter -> Error(MissingRequiredParameter(provider.Name, parameter.Key))
                | None ->
                    provider.Parameters
                    |> List.choose (fun parameter ->
                        match supplied.TryFind parameter.Key |> Option.orElse parameter.Default with
                        | Some value -> Some(parameter.Key, value)
                        | None -> None)
                    |> Ok

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

/// Exact UTF-8 projection of the Python effective-provider renderer's lines.
let renderEffectiveBytes (trailingNewline: bool) (selection: Provider list) : byte[] =
    let value = selection |> renderEffective |> String.concat "\n"
    Encoding.UTF8.GetBytes(value + (if trailingNewline then "\n" else ""))
