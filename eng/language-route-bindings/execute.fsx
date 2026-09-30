open System
open System.IO
open System.Diagnostics
open System.Security.Cryptography
open System.Text.Json
open System.Threading
open FS.GG.Coordination.Orchestration.Execution

let pairs = fsi.CommandLineArgs |> Array.skip 1 |> Array.chunkBySize 2
let options = pairs |> Array.map (function | [|k;v|] when k.StartsWith("--") -> k[2..],v | _ -> invalidArg "args" "use --name value") |> Map.ofArray
let need name = options |> Map.tryFind name |> Option.defaultWith (fun () -> invalidArg name "missing")
let full name = need name |> Path.GetFullPath
let bindingPath, sourceRoot, stateRoot = full "binding", full "source-root", full "state-root"
let commandPath = full "command"
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
let policyBytes = gitShow sourceRevision "eng/language-route-bindings/policy.json"
let policySha = SHA256.HashData policyBytes |> Convert.ToHexString |> _.ToLowerInvariant()
let policyDocument = JsonDocument.Parse policyBytes
let trusted = policyDocument.RootElement
if root.GetProperty("schema").GetString() <> "fsgg.language-route-portable-binding/1" then invalidOp "binding-schema-refused"
if root.GetProperty("acceptedNativeExecution").GetBoolean() then invalidOp "source-binding-must-not-preclaim-native-execution"
if root.GetProperty("policySha256").GetString() <> policySha || not(JsonElement.DeepEquals(root.GetProperty("operations"),trusted.GetProperty("operations"))) then invalidOp "binding-policy-mismatch"
let opId = if kind="rust" then "rust-tic-tac-toe-journey" else "go-snake-journey"
let image = root.GetProperty("images").GetProperty(kind)
let op = trusted.GetProperty("operations").GetProperty(opId)
let manifestDigest = image.GetProperty("manifestDigest").GetString()
let imageReference = "localhost/fsgg-language-route@" + manifestDigest
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
let now()=DateTimeOffset.UtcNow
let authority={WorkspaceScope=scope;WorkflowRevision=1UL;FenceGeneration=1UL;ObservedAt=now()}
let commandBytes = File.ReadAllBytes commandPath
let command = PortableWorkspaceContract.parseCommand commandBytes |> Result.defaultWith invalidOp
let canonicalCommand = PortableWorkspaceContract.commandBytes command |> Result.defaultWith invalidOp
if not (canonicalCommand.AsSpan().SequenceEqual(commandBytes.AsSpan())) then invalidOp "portable-command-noncanonical"
if command.SourceRevision<>sourceRevision || command.Operation<>"test" || command.ComponentId<>Some componentId then invalidOp "binding-command-mismatch"
let runner=PortableWorkspacePodmanRunner(runtime):>IPortableProcessRunner
let executor=PortableWorkspaceExecutor.Executor(policy,runner,now)
let cancellation = new CancellationTokenSource()
match options |> Map.tryFind "cancel-after-ms" with
| Some value -> cancellation.CancelAfter(Int32.Parse value)
| None -> ()
let outcome = if options.ContainsKey "recover" then executor.RecoverAsync(profile,command,cancellation.Token).Result else executor.ExecuteAsync(authority,profile,command,cancellation.Token).Result
printfn "%A" outcome
let exitCode =
    match outcome with
    | Completed receipt when receipt.Result.Error.IsNone && receipt.CleanupCompleted -> 0
    | Duplicate receipt when receipt.Result.Error.IsNone && receipt.CleanupCompleted -> 0
    | PendingDuplicate _ -> 3
    | Completed _ -> 4
    | Duplicate _ -> 4
    | Refused _ -> 5
exit exitCode
