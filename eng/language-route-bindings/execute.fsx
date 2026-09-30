open System
open System.IO
open System.Text.Json
open System.Threading
open FS.GG.Coordination.Orchestration.Execution

let pairs = fsi.CommandLineArgs |> Array.skip 1 |> Array.chunkBySize 2
let options = pairs |> Array.map (function | [|k;v|] when k.StartsWith("--") -> k[2..],v | _ -> invalidArg "args" "use --name value") |> Map.ofArray
let need name = options |> Map.tryFind name |> Option.defaultWith (fun () -> invalidArg name "missing")
let full name = need name |> Path.GetFullPath
let bindingPath, sourceRoot, stateRoot = full "binding", full "source-root", full "state-root"
let kind = need "kind"
if kind <> "rust" && kind <> "go" then invalidArg "kind" "rust or go required"
let podman, git, tar = full "podman", full "git", full "tar"
let storeRoot, runRoot = full "store-root", full "runroot"
let root = JsonDocument.Parse(File.ReadAllBytes bindingPath).RootElement
if root.GetProperty("schema").GetString() <> "fsgg.language-route-portable-binding/1" then invalidOp "binding-schema-refused"
if root.GetProperty("acceptedNativeExecution").GetBoolean() then invalidOp "source-binding-must-not-preclaim-native-execution"
let opId = if kind="rust" then "rust-tic-tac-toe-journey" else "go-snake-journey"
let image = root.GetProperty("images").GetProperty(kind)
let op = root.GetProperty("operations").GetProperty(opId)
let manifestDigest = image.GetProperty("manifestDigest").GetString()
let imageReference = "localhost/fsgg-language-route@" + manifestDigest
let sourceRevision = need "source-revision"
let scope = "fs-gg/templates/language-route/" + kind
let componentId = op.GetProperty("componentId").GetString()
let verificationSha = op.GetProperty("verificationSha256").GetString()
let recipeSha = op.GetProperty("recipeSha256").GetString()
let wrapper = op.GetProperty("arguments").EnumerateArray() |> Seq.head |> fun item -> item.GetString()
let toolchainId,toolchainVersion = if kind="rust" then "rust","1.98.1" else "go","1.27.1"
let routeComponent = { Id=componentId; Language=kind; WorkingDirectory="."; Toolchain={Id=toolchainId;Version=toolchainVersion}; EntryPoints={Build=opId;Test=opId;Lint=None;Artifact=None} }
let profile = { ProfileId="language-route-"+kind+"-v1"; Revision=1UL; WorkspaceScope=scope; SourceRevision=sourceRevision; QualifiedImage=imageReference; Components=[routeComponent]; ProductBuild=opId; ProductTest=opId; ProductJourney=opId; MaximumRuntimeSeconds=120UL; MaximumOutputBytes=262144UL }
let reviewed = { EntryPoint=opId; OperationIdentity="journey"; ComponentId=Some componentId; WorkingDirectory="."; QualifiedImage=imageReference; RequiredToolchains=[(toolchainId,toolchainVersion)]; Executable="/bin/sh"; Arguments=[wrapper]; VerificationIdentity=op.GetProperty("verificationIdentity").GetString(); VerificationPath=op.GetProperty("verificationPath").GetString(); VerificationSha256=verificationSha; RecipeSha256=recipeSha }
let runtime = { GitExecutable=git; TarExecutable=tar; PodmanExecutable=podman; PodmanGlobalArguments=["--storage-driver=vfs";"--root";storeRoot;"--runroot";runRoot]; StateRoot=stateRoot; ContainerPath="/usr/local/bin:/usr/local/go/bin:/usr/bin:/bin"; ContainerUser="32768:32768"; HostEnvironment=Map["HOME",stateRoot;"PATH","/usr/local/bin:/usr/bin:/bin";"LANG","C.UTF-8"]; ContainerEnvironment=Map["HOME","/output/home";"PATH","/usr/local/bin:/usr/local/go/bin:/usr/bin:/bin";"LANG","C.UTF-8"]; MaximumSnapshotBytes=16UL*1024UL*1024UL; TerminationGrace=TimeSpan.FromSeconds 10. }
let policy = { WorkspaceRoot=sourceRoot; WorkspaceScope=scope; SourceRevision=sourceRevision; QualifiedImage=imageReference; MaximumRuntimeSeconds=120UL; MaximumOutputBytes=262144UL; Operations=[reviewed]; Runtime=runtime }
let now()=DateTimeOffset.UtcNow
let authority={WorkspaceScope=scope;WorkflowRevision=1UL;FenceGeneration=1UL;ObservedAt=now()}
let command={CommandId=Guid.Parse(need "command-id");IdempotencyId=need "idempotency-id";WorkspaceScope=scope;ProfileId=profile.ProfileId;ProfileRevision=1UL;SourceRevision=sourceRevision;ExpectedWorkflowRevision=1UL;FenceGeneration=1UL;CausationId=None;Deadline=now().AddSeconds 150.;Operation="journey";ComponentId=Some componentId}
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
