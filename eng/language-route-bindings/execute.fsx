#load "BindingSupport.fsx"

open System
open System.IO
open System.Diagnostics
open System.Collections.Generic
open System.Security.Cryptography
open System.Text.Json
open System.Threading
open FS.GG.Coordination.Orchestration.Execution
open BindingSupport.LanguageRouteBindingSupport

let pairs = fsi.CommandLineArgs |> Array.skip 1 |> Array.chunkBySize 2
let options = pairs |> Array.map (function | [|k;v|] when k.StartsWith("--") -> k[2..],v | _ -> invalidArg "args" "use --name value") |> Map.ofArray
let need name = options |> Map.tryFind name |> Option.defaultWith (fun () -> invalidArg name "missing")
let full name = need name |> Path.GetFullPath
let bindingPath, sourceRoot, stateRoot = full "binding", full "source-root", full "state-root"
let commandPath = full "command"
let outputPath = full "output"
let kind = need "kind"
if kind <> "rust" && kind <> "go" then invalidArg "kind" "rust or go required"
let podman, git, tar = full "podman", full "git", full "tar"
let storeRoot, runRoot = full "store-root", full "runroot"
let bindingDocument = JsonDocument.Parse(File.ReadAllBytes bindingPath)
let root = bindingDocument.RootElement
let sourceRevision = need "source-revision"
let boundSource = root.GetProperty("bindingSource")
if boundSource.GetProperty("revision").GetString() <> sourceRevision then invalidOp "binding-source-revision-mismatch"
let gitShow revision path =
    use child=new Process()
    child.StartInfo<-ProcessStartInfo(git,RedirectStandardOutput=true,RedirectStandardError=true,UseShellExecute=false)
    for argument in ["-C";sourceRoot;"show";revision+":"+path] do child.StartInfo.ArgumentList.Add argument
    if not(child.Start()) then invalidOp "binding-source-git-start-refused"
    use bytes=new MemoryStream()
    child.StandardOutput.BaseStream.CopyTo bytes
    let error=child.StandardError.ReadToEnd()
    if not(child.WaitForExit(30000)) then child.Kill true;invalidOp "binding-source-git-timeout"
    if child.ExitCode<>0 then invalidOp ("binding-source-git-refused:"+error.Trim())
    bytes.ToArray()
let gitTree revision =
    use child=new Process()
    child.StartInfo<-ProcessStartInfo(git,RedirectStandardOutput=true,RedirectStandardError=true,UseShellExecute=false)
    for argument in ["-C";sourceRoot;"rev-parse";revision+"^{tree}"] do child.StartInfo.ArgumentList.Add argument
    if not(child.Start()) then invalidOp "binding-source-git-start-refused"
    let output=child.StandardOutput.ReadToEnd().Trim()
    let error=child.StandardError.ReadToEnd()
    if not(child.WaitForExit(30000)) then child.Kill true;invalidOp "binding-source-git-timeout"
    if child.ExitCode<>0 then invalidOp ("binding-source-git-refused:"+error.Trim())
    output
if gitTree sourceRevision<>boundSource.GetProperty("tree").GetString() then invalidOp "binding-source-tree-mismatch"
let policyBytes = gitShow sourceRevision "eng/language-route-bindings/policy.json"
let policySha = SHA256.HashData policyBytes |> Convert.ToHexString |> _.ToLowerInvariant()
let policyDocument = JsonDocument.Parse policyBytes
let trusted = policyDocument.RootElement
if root.GetProperty("schema").GetString() <> "fsgg.language-route-portable-binding/1" then invalidOp "binding-schema-refused"
if root.GetProperty("acceptedNativeExecution").GetBoolean() then invalidOp "source-binding-must-not-preclaim-native-execution"
if root.GetProperty("policySha256").GetString() <> policySha || not(JsonElement.DeepEquals(root.GetProperty("operations"),trusted.GetProperty("operations"))) then invalidOp "binding-policy-mismatch"
let opId = if kind="rust" then "rust-tic-tac-toe-journey" else "go-snake-journey"
let image = root.GetProperty("images").GetProperty(kind)
let trustedImage = trusted.GetProperty("qualifiedImages").GetProperty(kind)
let op = trusted.GetProperty("operations").GetProperty(opId)
let imageReference = qualifiedImageReference trustedImage image
let scope = "fs-gg/templates/language-route/" + kind
let componentId = op.GetProperty("componentId").GetString()
let verificationSha = op.GetProperty("verificationSha256").GetString()
let recipeSha = op.GetProperty("recipeSha256").GetString()
let wrapper = op.GetProperty("arguments").EnumerateArray() |> Seq.head |> fun item -> item.GetString()
let workingDirectory = op.GetProperty("workingDirectory").GetString()
let wrapperPath = workingDirectory+"/"+wrapper
let committedWrapperSha=gitShow sourceRevision wrapperPath |> SHA256.HashData |> Convert.ToHexString |> _.ToLowerInvariant()
if committedWrapperSha<>op.GetProperty("wrapperSha256").GetString() || committedWrapperSha<>root.GetProperty("wrapperSha256").GetProperty(opId).GetString() then invalidOp "binding-committed-wrapper-mismatch"
let toolchainId,toolchainVersion = if kind="rust" then "rust","1.98.1" else "go","1.27.1"
let routeComponent = { Id=componentId; Language=kind; WorkingDirectory=workingDirectory; Toolchain={Id=toolchainId;Version=toolchainVersion}; EntryPoints={Build=opId;Test=opId;Lint=None;Artifact=None} }
let rawProfile = { ProfileId="language-route-"+kind+"-v1"; Revision=1UL; WorkspaceScope=scope; SourceRevision=sourceRevision; QualifiedImage=imageReference; Components=[routeComponent]; ProductBuild=opId; ProductTest=opId; ProductJourney=opId; MaximumRuntimeSeconds=120UL; MaximumOutputBytes=262144UL }
let profileBytes = PortableWorkspaceContract.profileBytes rawProfile |> Result.defaultWith invalidOp
let profile = PortableWorkspaceContract.parseProfile profileBytes |> Result.defaultWith invalidOp
let reviewed = { EntryPoint=opId; OperationIdentity="test"; ComponentId=Some componentId; WorkingDirectory=workingDirectory; QualifiedImage=imageReference; RequiredToolchains=[(toolchainId,toolchainVersion)]; Executable="/bin/sh"; Arguments=[wrapper]; VerificationIdentity=op.GetProperty("verificationIdentity").GetString(); VerificationPath=op.GetProperty("verificationPath").GetString(); VerificationSha256=verificationSha; RecipeSha256=recipeSha }
let runtime = { GitExecutable=git; TarExecutable=tar; PodmanExecutable=podman; PodmanGlobalArguments=["--storage-driver=vfs";"--root";storeRoot;"--runroot";runRoot]; StateRoot=stateRoot; ContainerPath="/usr/local/bin:/usr/local/go/bin:/usr/bin:/bin"; ContainerUser="32768:32768"; HostEnvironment=Map["HOME",stateRoot;"PATH","/usr/local/bin:/usr/bin:/bin";"LANG","C.UTF-8"]; ContainerEnvironment=Map["HOME","/output/home";"PATH","/usr/local/bin:/usr/local/go/bin:/usr/bin:/bin";"LANG","C.UTF-8"]; MaximumSnapshotBytes=16UL*1024UL*1024UL; TerminationGrace=TimeSpan.FromSeconds 10. }
let policy = { WorkspaceRoot=sourceRoot; WorkspaceScope=scope; SourceRevision=sourceRevision; QualifiedImage=imageReference; MaximumRuntimeSeconds=120UL; MaximumOutputBytes=262144UL; Operations=[reviewed]; Runtime=runtime }
let now()=portableNowFrom DateTimeOffset.UtcNow
let authority={WorkspaceScope=scope;WorkflowRevision=1UL;FenceGeneration=1UL;ObservedAt=now()}
let commandBytes = File.ReadAllBytes commandPath
let command = PortableWorkspaceContract.parseCommand commandBytes |> Result.defaultWith invalidOp
let canonicalCommand = PortableWorkspaceContract.commandBytes command |> Result.defaultWith invalidOp
if not (canonicalCommand.AsSpan().SequenceEqual(commandBytes.AsSpan())) then invalidOp "portable-command-noncanonical"
if command.SourceRevision<>sourceRevision || command.Operation<>"test" || command.ComponentId<>Some componentId then invalidOp "binding-command-mismatch"
let shaBytes (bytes:byte array) = SHA256.HashData bytes |> Convert.ToHexString |> _.ToLowerInvariant()
let commandSha = shaBytes commandBytes
let bindingDigest =
    String.concat "\n" [shaBytes profileBytes;commandSha;recipeSha]
    |> System.Text.Encoding.UTF8.GetBytes
    |> shaBytes
let containerName = "fsgg-portable-"+bindingDigest[..23]
let effectiveProfile, effectiveCommand =
    match options |> Map.tryFind "refusal-probe" with
    | None -> profile, command
    | Some "wrong-toolchain" ->
        let routeComponent = { profile.Components.Head with Toolchain={ profile.Components.Head.Toolchain with Version="0.0.0-refusal-probe" } }
        { profile with Components=[routeComponent] }, command
    | Some "wrong-reference" ->
        { profile with QualifiedImage="localhost/fsgg-language-route-refusal@sha256:"+String.replicate 64 "0" }, command
    | Some "changed-source" ->
        { profile with SourceRevision=String.replicate 40 "0" }, command
    | Some value -> invalidArg "refusal-probe" ("unsupported refusal probe: "+value)
let runner=PortableWorkspacePodmanRunner(runtime):>IPortableProcessRunner
let executor=PortableWorkspaceExecutor.Executor(policy,runner,now)
let cancellation = new CancellationTokenSource()
let inspectRunning () =
    use child=new Process()
    child.StartInfo<-ProcessStartInfo(podman,RedirectStandardOutput=true,RedirectStandardError=true,UseShellExecute=false)
    for argument in ["--storage-driver=vfs";"--root";storeRoot;"--runroot";runRoot;"container";"inspect";"--format";"{{.State.Status}}|{{.Id}}";containerName] do child.StartInfo.ArgumentList.Add argument
    if not(child.Start()) then None
    elif not(child.WaitForExit(2000)) then child.Kill true;None
    elif child.ExitCode<>0 then None
    else
        match child.StandardOutput.ReadToEnd().Trim().Split('|',2) with
        | [|"running";identity|] when identity.Length=64 && identity |> Seq.forall Uri.IsHexDigit -> Some identity
        | _ -> None
let mutable runningCancellationObservation:Dictionary<string,obj> option=None
let mutable cancellationCleanupRecovery=false
let outcome =
    if options.ContainsKey "recover" then executor.RecoverAsync(effectiveProfile,effectiveCommand,cancellation.Token).Result
    else
        match options |> Map.tryFind "cancel-running-timeout-ms" with
        | None -> executor.ExecuteAsync(authority,effectiveProfile,effectiveCommand,cancellation.Token).Result
        | Some value ->
            let timeout=Int32.Parse value
            if timeout<1 || timeout>30000 then invalidArg "cancel-running-timeout-ms" "must be between 1 and 30000"
            let execution=executor.ExecuteAsync(authority,effectiveProfile,effectiveCommand,cancellation.Token)
            let limit=DateTimeOffset.UtcNow.AddMilliseconds(float timeout)
            while runningCancellationObservation.IsNone && not execution.IsCompleted && DateTimeOffset.UtcNow<limit do
                match inspectRunning() with
                | Some identity ->
                    let observedAt=DateTimeOffset.UtcNow
                    cancellation.Cancel()
                    let requestedAt=DateTimeOffset.UtcNow
                    let observation=Dictionary<string,obj>()
                    observation["schema"] <- "fsgg.language-route.running-cancellation/1"
                    observation["commandSha256"] <- commandSha
                    observation["bindingDigest"] <- bindingDigest
                    observation["containerName"] <- containerName
                    observation["containerIdentity"] <- identity.ToLowerInvariant()
                    observation["state"] <- "running"
                    observation["observedAt"] <- observedAt.ToString("O")
                    observation["requestedAt"] <- requestedAt.ToString("O")
                    observation["observationOrdinal"] <- 1
                    observation["requestOrdinal"] <- 2
                    runningCancellationObservation<-Some observation
                | None -> Thread.Sleep 50
            let original=execution.Result
            match runningCancellationObservation,original with
            | Some _,Completed receipt when receipt.TerminationObserved && not receipt.CleanupCompleted ->
                match executor.RecoverAsync(effectiveProfile,effectiveCommand,CancellationToken.None).Result with
                | Duplicate recovered when recovered.CleanupCompleted ->
                    cancellationCleanupRecovery<-true
                    Completed recovered
                | other -> other
            | _ -> original
printfn "%A" outcome
let evidence = Dictionary<string,obj>()
evidence["schema"] <- "fsgg.language-route.hosted-execution/1"
evidence["kind"] <- kind
evidence["mode"] <- (if options.ContainsKey "recover" then "recover" else "execute")
evidence["commandSha256"] <- commandSha
evidence["refusalProbe"] <- (options |> Map.tryFind "refusal-probe" |> Option.toObj)
evidence["runningCancellationObservation"] <- (runningCancellationObservation |> Option.toObj)
evidence["cancellationCleanupRecovery"] <- cancellationCleanupRecovery
let receiptFields disposition (receipt:PortableExecutionReceipt) =
    evidence["disposition"] <- disposition
    evidence["commandId"] <- receipt.Result.CommandId.ToString("D")
    evidence["executionStarted"] <- receipt.ExecutionStarted
    evidence["cleanupCompleted"] <- receipt.CleanupCompleted
    evidence["cancellationRequested"] <- receipt.CancellationRequested
    evidence["terminationObserved"] <- receipt.TerminationObserved
    evidence["qualifiedImage"] <- receipt.QualifiedImage
    evidence["sourceRevision"] <- receipt.SourceRevision
    evidence["sourceTree"] <- Option.toObj receipt.SourceTree
    evidence["snapshotSha256"] <- Option.toObj receipt.SnapshotSha256
    evidence["runtimeIdentity"] <- Option.toObj receipt.RuntimeIdentity
    evidence["containerIdentity"] <- Option.toObj receipt.ContainerIdentity
    evidence["verificationSha256"] <- receipt.VerificationSha256
    evidence["verificationIdentity"] <- receipt.VerificationIdentity
    evidence["verificationOutputSha256"] <-
        (receipt.VerificationOutput |> Option.map (SHA256.HashData >> Convert.ToHexString >> _.ToLowerInvariant()) |> Option.toObj)
    evidence["outputSha256"] <- receipt.OutputSha256
    evidence["errorCode"] <- (receipt.Result.Error |> Option.map _.Code |> Option.toObj)
match outcome with
| Completed receipt -> receiptFields "completed" receipt
| Duplicate receipt -> receiptFields "duplicate" receipt
| PendingDuplicate commandId ->
    evidence["disposition"] <- "pending-duplicate"
    evidence["commandId"] <- commandId.ToString("D")
| Refused reason ->
    evidence["disposition"] <- "refused"
    evidence["reason"] <- reason
let evidenceBytes = JsonSerializer.SerializeToUtf8Bytes(evidence,JsonSerializerOptions(WriteIndented=true))
let evidenceStream = new FileStream(outputPath,FileMode.CreateNew,FileAccess.Write,FileShare.None)
evidenceStream.Write evidenceBytes
evidenceStream.Flush true
evidenceStream.Dispose()
if not (OperatingSystem.IsWindows()) then File.SetUnixFileMode(outputPath,UnixFileMode.UserRead ||| UnixFileMode.UserWrite)
let exitCode =
    match outcome with
    | Completed receipt when receipt.Result.Error.IsNone && receipt.CleanupCompleted -> 0
    | Duplicate receipt when receipt.Result.Error.IsNone && receipt.CleanupCompleted -> 0
    | PendingDuplicate _ -> 3
    | Completed _ -> 4
    | Duplicate _ -> 4
    | Refused _ -> 5
exit exitCode
